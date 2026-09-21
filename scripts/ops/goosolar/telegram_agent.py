import asyncio
import logging
import os
import socket
import subprocess
import time

from dotenv import load_dotenv
from openai import OpenAI
from telegram import Update
from telegram.error import NetworkError
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters

load_dotenv()

# 로그는 journalctl -u hermes-agent 에서 본다. 수신·차단·WoL 결과를 한 줄씩 남긴다.
logging.basicConfig(format="%(asctime)s %(levelname)s %(message)s", level=logging.INFO)
logging.getLogger("httpx").setLevel(logging.WARNING)  # 토큰이 든 URL이 로그에 찍히지 않게
log = logging.getLogger("goosolar")

SHIN_PC_MAC = "74:56:3C:7B:D6:51"
SHIN_PC_IP = os.getenv("SHIN_PC_IP", "100.67.79.19")   # Tailscale 고정 주소(유선 주소는 DHCP로 바뀌어 .33이 틀어짐). 깨어남 확인에 쓴다
SHIN_PC_PORTS = (22, 11434)                            # 윈도우가 ping을 막아 둬서 포트 응답으로 켜짐을 판단
BROADCASTS = ("255.255.255.255", "172.30.1.255")
WOL_PORTS = (9, 7)
WAKE_WAIT_SEC = 240

# 허용 사용자(텔레그램 숫자 ID, 쉼표 구분). 비어 있으면 아무도 명령할 수 없다(닫힌 기본값).
ALLOWED = {u.strip() for u in os.getenv("TELEGRAM_ALLOWED_USERS", "").split(",") if u.strip()}

client = OpenAI(
    api_key=os.getenv("GROQ_API_KEY"),
    base_url="https://api.groq.com/openai/v1"
)


def get_best_model():
    try:
        available_models = [m.id for m in client.models.list().data]
        # 대화용이 아닌 모델(음성, 프롬프트 가드, 세이프가드)은 뺀다. 2026-09-21: 예전 목록 순서 방식이 prompt-guard를 골라 대화가 깨질 수 있었다.
        skip = ("orpheus", "whisper", "guard", "safeguard", "allam")
        safe_models = [m for m in available_models if not any(x in m for x in skip)]
        preferred = ["llama-3.3-70b-versatile", "openai/gpt-oss-120b", "openai/gpt-oss-20b", "qwen/qwen3.8-27b",
                     "llama-3.1-8b-instant", "groq/compound-mini"]
        for candidate in preferred:
            if candidate in safe_models:
                return candidate
        return safe_models[0] if safe_models else "llama-3.1-8b-instant"
    except Exception:
        return "llama-3.1-8b-instant"


SELECTED_MODEL = get_best_model()


def magic_packet(mac):
    raw = bytes.fromhex(mac.replace(":", "").replace("-", ""))
    return b"\xff" * 6 + raw * 16


def send_magic_packets(mac=SHIN_PC_MAC, rounds=3):
    """마법 패킷을 대역 브로드캐스트 2곳 x 포트 2개 x 3회 보낸다. 보낸 개수와 실패 개수를 돌려준다."""
    pkt = magic_packet(mac)
    sent = failed = 0
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        for i in range(rounds):
            for addr in BROADCASTS:
                for port in WOL_PORTS:
                    try:
                        s.sendto(pkt, (addr, port))
                        sent += 1
                    except OSError as e:
                        failed += 1
                        log.warning("WoL 전송 실패 %s:%s %s", addr, port, e)
            if i < rounds - 1:
                time.sleep(1)
    return sent, failed


def shin_pc_is_up(timeout=1.5):
    for port in SHIN_PC_PORTS:
        try:
            with socket.create_connection((SHIN_PC_IP, port), timeout=timeout):
                return True
        except OSError:
            continue
    return False


def get_real_system_specs():
    try:
        cpu_info = subprocess.check_output("lscpu | grep 'Model name\\|CPU(s):'", shell=True, text=True).strip()
        mem_info = subprocess.check_output("free -h", shell=True, text=True).strip()
        disk_info = subprocess.check_output("df -h /", shell=True, text=True).strip()
        os_info = subprocess.check_output("uname -srm", shell=True, text=True).strip()
        return f"[구PC 실제 서버 정보]\n- OS: {os_info}\n- CPU:\n{cpu_info}\n- RAM:\n{mem_info}\n- SSD:\n{disk_info}"
    except Exception as e:
        return f"정보 조회 실패: {e}"


def is_allowed(update: Update):
    user = update.effective_user
    uid = str(user.id) if user else "?"
    if uid in ALLOWED:
        return True
    log.warning("차단: 허용되지 않은 사용자 id=%s 글=%r", uid, (update.message.text if update.message else "")[:40])
    return False


async def wake_and_report(update: Update):
    """신PC를 깨우고, 켜졌는지 최대 4분 확인해 결과를 같은 대화창에 알린다(AI 호출 없음)."""
    if await asyncio.to_thread(shin_pc_is_up):
        log.info("WoL 요청: 신PC는 이미 켜져 있음")
        await update.message.reply_text("이미 켜져 있습니다. 신PC가 응답 중이라 부팅 패킷은 보내지 않았습니다.")
        return
    sent, failed = await asyncio.to_thread(send_magic_packets)
    log.info("WoL 패킷 전송 sent=%s failed=%s", sent, failed)
    if sent == 0:
        await update.message.reply_text(f"❌ 부팅 패킷을 하나도 못 보냈습니다(실패 {failed}건). 구PC 네트워크를 확인해야 합니다.")
        return
    await update.message.reply_text(
        f"⚡ 신PC로 부팅 패킷 {sent}개를 보냈습니다. 최대 {WAKE_WAIT_SEC // 60}분 동안 켜졌는지 확인하고 결과를 알려드립니다.")
    start = time.time()
    while time.time() - start < WAKE_WAIT_SEC:
        await asyncio.sleep(10)
        if await asyncio.to_thread(shin_pc_is_up):
            took = int(time.time() - start)
            log.info("WoL 성공: 신PC 응답 확인, %s초", took)
            await update.message.reply_text(f"✅ 신PC가 깨어났습니다(약 {took}초). 헤르메스가 뜨기까지 1~2분 더 걸릴 수 있습니다.")
            return
    log.warning("WoL 실패: %s초 안에 신PC 응답 없음", WAKE_WAIT_SEC)
    await update.message.reply_text(
        f"❌ 패킷은 보냈지만 {WAKE_WAIT_SEC // 60}분 안에 신PC가 응답하지 않았습니다. "
        "신PC 쪽 설정(메인보드 BIOS, 랜카드 절전)을 확인해야 합니다. 전원 버튼으로 직접 켠 뒤 탐에게 '켜지기 실패'라고 알려 주세요.")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update):
        return
    await update.message.reply_text(
        "안녕하세요! 구솔라 AI 헤르메스 에이전트입니다.\n\n"
        "- /wol : 신PC 전원 켜기(켜졌는지 확인까지)\n- /status : 신PC 켜짐 여부와 구PC 상태\n- 일반 대화: 구PC 제어 및 안내")


async def wol_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update):
        return
    log.info("/wol 수신 id=%s", update.effective_user.id)
    await wake_and_report(update)


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update):
        return
    up = await asyncio.to_thread(shin_pc_is_up)
    uptime = subprocess.run("uptime -p", shell=True, capture_output=True, text=True).stdout.strip()
    await update.message.reply_text(f"신PC: {'켜져 있음 🟢' if up else '꺼져 있음(응답 없음) ⚪'}\n구PC: 정상 가동 ({uptime})")


def normalize(text):
    return text.replace(" ", "").lower()


# 대상 낱말(신pc/신피시) + 켜기 동사가 한 문장에 있으면 깨운다. 2026-09-21 아침 "신pc 전원 켜줘"가
# 옛 봇의 붙어 있는 문구 일치("신pc 켜")에 안 걸려 AI 답변으로 빠진 사고의 수정. "꺼"는 켜기가 아니므로 제외.
TARGET_WORDS = ("신pc", "신피시", "신컴")
WAKE_VERBS = ("켜", "켤", "부팅", "깨워", "깨우", "기동")
STATE_WORDS = ("켜져", "켜졌", "켜진", "켜있", "켜 있")  # "켜져 있어?"는 상태 질문이라 깨우지 않는다(정규화 전 글자로 검사)


def wants_wake(text):
    t = normalize(text)
    if t.startswith("/") or any(w in t for w in STATE_WORDS):
        return False
    return (any(w in t for w in TARGET_WORDS) and any(v in t for v in WAKE_VERBS)) or "컴퓨터켜" in t


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update):
        return
    user_text = update.message.text
    log.info("메시지 수신 id=%s 글=%r", update.effective_user.id, user_text[:40])

    # 키워드 기반 즉시 WoL 실행 (AI 호출 없음). 띄어쓰기·대소문자는 무시한다.
    if wants_wake(user_text):
        await wake_and_report(update)
        return

    real_specs = get_real_system_specs()
    system_prompt = f"""너는 우분투 서버 관리를 돕는 AI 헤르메스 에이전트야.
아래 제공된 [구PC 실제 서버 정보]를 바탕으로 사용자에게 친절하게 답변하라.

{real_specs}"""

    try:
        response = client.chat.completions.create(
            model=SELECTED_MODEL,
            temperature=0.2,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_text}
            ]
        )
        reply = response.choices[0].message.content
        await update.message.reply_text(reply)
    except Exception:
        # AI API 오류 발생 시에도 시스템 구동 정보를 직접 출력
        await update.message.reply_text(f"⚠️ AI 연동에 일시적 지연이 발생했습니다.\n\n[구PC 직접 조회 사양]\n{real_specs}")


async def on_error(update, context: ContextTypes.DEFAULT_TYPE):
    # 텔레그램 통신이 잠깐 끊기는 것은 자동 재시도되므로 한 줄만 남긴다(전체 트레이스백 생략).
    if isinstance(context.error, NetworkError):
        log.warning("텔레그램 통신 일시 오류(자동 재시도): %s", type(context.error).__name__)
    else:
        log.error("처리 중 오류: %r", context.error)


if __name__ == '__main__':
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not ALLOWED:
        log.warning("TELEGRAM_ALLOWED_USERS가 비어 있어 모든 명령이 차단됩니다")
    app = ApplicationBuilder().token(token).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("wol", wol_command))
    app.add_handler(CommandHandler("status", status_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_error_handler(on_error)

    log.info("구솔라 텔레그램 에이전트 가동 중... (연동 모델: %s, 허용 사용자 %d명)", SELECTED_MODEL, len(ALLOWED))
    app.run_polling()
