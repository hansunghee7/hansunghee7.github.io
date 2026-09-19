#!/usr/bin/env python3
# mailbox_courier.py - 우편함 배달원 (정책 개정판, 2026-09-20 사장님 결정)
# 정책:
#   1) 신솔라 텔레그램(사장님 폰)에는 "사장님이 결정하거나 확인할 일이 있는" 우편만 보낸다.
#      = 받는이가 사장님이고 '요청:' 줄이 있는 우편. 요청이 없으면 우편함에만 둔다.
#   2) 에이전트끼리의 우편(받는이가 사장님이 아닌 것)은 별도 '에이전트 채널'로 보낸다.
#      사장님은 모니터링만 한다. 환경변수 TELEGRAM_AGENT_CHAT_ID가 없으면 아무 데도 안 보낸다.
#   3) '긴급' 표시는 발송 조건이 아니다. 요약 알림("N건 쌓임")은 없앴다(반복 발송 결함의 원인).
#   4) 시험은 폰에 나가지 않는다: --dry-run, 또는 --mailbox-dir/--state-file 지정(시험 모드)에서는
#      --really-send를 주지 않는 한 실제 발송을 하지 않는다.
#   5) 개정 첫 실행은 기존 우편을 전부 "이미 처리"로 표시하고 아무것도 보내지 않는다(폭주 방지).
#   6) 발송 직후 상태를 저장한다(같은 우편 중복 발송 방지).
# 이전 판: mailbox_courier.py.bak_0920_policy

import argparse
import os
import sys
import json
import subprocess
import requests
from pathlib import Path
from datetime import datetime, date, time as dt_time, timedelta

# UTF-8 출력 강제
sys.stdout.reconfigure(encoding='utf-8')

# 설정
DEFAULT_MAILBOX_DIR = Path(r"C:\work\solar-bible\mailbox")
STATE_FILE = Path(r"C:\Users\PC\AppData\Local\hermes\mailbox_courier_state.json")
SOLAR_BIBLE_ROOT = Path(r"C:\work\solar-bible")
ENV_FILE = Path(r"C:\Users\PC\AppData\Local\hermes\.env")

# 하루 상한
DAILY_LIMIT = 20
EVENING_SUMMARY_TIME = dt_time(21, 0)  # 한국 시간 21:00


def load_env():
    """환경변수 파일에서 TELEGRAM_BOT_TOKEN, TELEGRAM_ALLOWED_USERS 읽기"""
    env_vars = {}
    try:
        with ENV_FILE.open('r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    value = value.strip().strip('"\'')
                    env_vars[key.strip()] = value
    except OSError:
        pass
    return env_vars


def norm_key(x):
    return str(x).replace('\\\\', '/').replace('\\', '/')


def load_state():
    """상태 파일 로드 (발송 이력 + 날짜별 카운트).
    새 형식: {notified_files: [...], daily_counts: {YYYY-MM-DD: N}}
    구 형식(목록): [...] → 집합 변환.
    구 형식(사전): {path: true} → 키 집합 변환.
    """
    if STATE_FILE.exists():
        try:
            with STATE_FILE.open('r', encoding='utf-8') as f:
                data = json.load(f)
            # 새 형식: dict + 'notified_files' 키
            if isinstance(data, dict) and 'notified_files' in data:
                return data
            # 구 형식(목록): JSON 배열
            if isinstance(data, list):
                return {
                    'notified_files': [norm_key(x) for x in data],
                    'daily_counts': {}
                }
            # 구 형식(사전): {path: true} 형태
            if isinstance(data, dict):
                return {
                    'notified_files': set(data.keys()),
                    'daily_counts': {}
                }
            return {
                'notified_files': set(),
                'daily_counts': {}
            }
        except (json.JSONDecodeError, OSError):
            return {'notified_files': set(), 'daily_counts': {}}
    return {'notified_files': set(), 'daily_counts': {}}


def save_state(state):
    """상태 파일 저장"""
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with STATE_FILE.open('w', encoding='utf-8') as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def run_git_pull():
    """git pull --ff-only 실행 (실패해도 계속)"""
    try:
        result = subprocess.run(
            ['git', 'pull', '--ff-only'],
            cwd=SOLAR_BIBLE_ROOT,
            capture_output=True,
            text=True,
            timeout=30
        )
    except (subprocess.TimeoutExpired, OSError, FileNotFoundError):
        pass


def extract_metadata_and_body(filepath):
    """파일에서 메타데이터와 본문 추출. 받는이, 보낸이, 제목, 본문 첫 줄, 요청 반환.
    받는이 판정은 '받는이:' 헤더 우선, 없으면 첫 # 제목줄 앞의 맥락으로 추정."""
    try:
        with filepath.open('r', encoding='utf-8') as f:
            lines = f.readlines()
    except OSError:
        return None, None, None, None, None

    recipient = None
    sender = None
    subject = None
    body_start = 0
    saw_meta = False

    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith('받는이:'):
            recipient = stripped[4:].strip()
        elif stripped.startswith('보낸이:'):
            sender = stripped[4:].strip()
        elif stripped.startswith('제목:'):
            subject = stripped[3:].strip()
        elif stripped.startswith('# ') and subject is None:
            subject = stripped[2:].strip()
        elif stripped.startswith('긴급:'):
            saw_meta = True
        elif saw_meta and stripped == '':
            body_start = i + 1
            break
        elif stripped == '---':
            body_start = i + 1
            break

    ask = ''
    for ln in lines[:body_start]:
        if ln.strip().startswith('요청:'):
            ask = ln.strip()[3:].strip()

    body_lines = [ln for ln in lines[body_start:] if ln.strip()]
    body_first = body_lines[0].strip() if body_lines else ''

    # 받는이가 명시되지 않았으면 파일 경로에서 추정 (폴더명)
    if not recipient:
        try:
            rel = filepath.relative_to(DEFAULT_MAILBOX_DIR)
            parts = rel.parts
            if len(parts) >= 2:
                recipient = parts[0]  # 첫 폴더명 = 받는이
        except ValueError:
            pass

    return recipient, sender, subject, body_first, ask


def has_urgent_flag(filepath):
    """본문에 '긴급: 예' 줄이 있는지 확인"""
    try:
        with filepath.open('r', encoding='utf-8') as f:
            for line in f:
                if line.strip() == '긴급: 예':
                    return True
    except OSError:
        pass
    return False


def shorten(text, limit):
    """단어(공백)나 문장부호 경계에서 자르고 줄임표를 붙인다."""
    text = text.strip()
    if len(text) <= limit:
        return text
    cut = text[:limit]
    for sep in ('. ', '! ', '? ', ', ', ' '):
        i = cut.rfind(sep)
        if i >= limit // 2:
            cut = cut[:i + (0 if sep == ' ' else 1)]
            break
    return cut.rstrip(' ,.') + '…'


def clean_subject(subject):
    """제목 끝의 마침표 중복 정리. 이미 끝이 '.'이면 하나 남김."""
    if subject and subject.endswith('.'):
        return subject.rstrip('.') + '.'
    return subject


AGENT_DAILY_LIMIT = 60          # 에이전트 채널 하루 상한(모니터링 폭주 방지)
BOSS_DAILY_LIMIT = 10           # 신솔라 채널 하루 상한
BASELINE_ID = 'policy_20260920'  # 개정 첫 실행 표시(기존 우편을 조용히 처리)


def build_message_for_boss(sender, subject, body_first, ask):
    """신솔라(사장님 폰)용. 사장님이 할 일이 있을 때만 쓴다.
    📬 탐 → 사장님 | 제목
    <무엇에 대한 것인지: 본문 첫 줄>
    👉 <사장님이 할 일>
    """
    lines = [f"📬 {sender} → 사장님 | {clean_subject(subject)}"]
    if body_first:
        lines.append(shorten(body_first, 120))
    lines.append(f"👉 {ask}")
    return "\n".join(lines)


def build_message_agent(sender, recipient, subject, body_first):
    """에이전트 채널용(모니터링). 무엇에 대한 것인지 본문 첫 줄을 붙인다."""
    lines = [f"📨 {sender} → {recipient} | {clean_subject(subject)}"]
    if body_first:
        lines.append(shorten(body_first, 120))
    return "\n".join(lines)


def send_telegram(token, chat_id, text):
    """Telegram Bot API sendMessage 직접 호출"""
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    try:
        resp = requests.post(url, json={'chat_id': chat_id, 'text': text}, timeout=10)
        return resp.json()
    except requests.RequestException as e:
        return {'ok': False, 'error': str(e)}


def get_today_str():
    """한국 시간 기준 오늘 날짜. 이 PC의 시계는 KST다."""
    return datetime.now().strftime('%Y-%m-%d')


def _count(state, key):
    return state.setdefault('daily_counts', {}).get(key, 0)


def _inc(state, key):
    c = state.setdefault('daily_counts', {})
    c[key] = c.get(key, 0) + 1


def main():
    parser = argparse.ArgumentParser(description='mailbox_courier (정책 개정판)')
    parser.add_argument('--dry-run', action='store_true',
                        help='실제 발송 없이 출력만. 상태 파일도 쓰지 않음.')
    parser.add_argument('--mailbox-dir', type=str, default=None, help='시험용 우편함 폴더')
    parser.add_argument('--state-file', type=str, default=None, help='시험용 상태 파일')
    parser.add_argument('--really-send', action='store_true',
                        help='시험 모드에서도 실제 텔레그램 발송(사용하지 말 것)')
    args = parser.parse_args()
    dry_run = args.dry_run

    env = load_env()
    token = env.get('TELEGRAM_BOT_TOKEN', '')
    boss_chat = env.get('TELEGRAM_ALLOWED_USERS', '').split(',')[0].strip()
    agent_chat = env.get('TELEGRAM_AGENT_CHAT_ID', '').strip()
    if os.environ.get('COURIER_TEST_AGENT_CHAT'):
        agent_chat = os.environ['COURIER_TEST_AGENT_CHAT']   # 시험 전용(출력만 됨)

    mailbox_dir_env = os.environ.get('MAILBOX_DIR') or args.mailbox_dir
    test_mode = bool(mailbox_dir_env or args.state_file)
    live = (not dry_run) and (not test_mode or args.really_send)
    if live and (not token or not boss_chat):
        print("[WARN] TELEGRAM_BOT_TOKEN 또는 TELEGRAM_ALLOWED_USERS 없음. 발송 건너뜀.")
        return 0
    if dry_run:
        print("[DRY-RUN] 실제 발송·상태 기록 없음.")
    elif test_mode and not args.really_send:
        print("[TEST] 시험 모드: 실제 발송 없음(출력만). 상태 파일만 지정한 곳에 기록.")

    mailbox_dir = Path(mailbox_dir_env) if mailbox_dir_env else DEFAULT_MAILBOX_DIR
    if not mailbox_dir_env:
        run_git_pull()

    global STATE_FILE
    if args.state_file:
        STATE_FILE = Path(args.state_file)

    state = load_state()
    notified = set(state.get('notified_files', []))
    today = get_today_str()
    boss_key, agent_key = f"boss_{today}", f"agent_{today}"

    def persist():
        if not dry_run:
            state['notified_files'] = sorted(notified)
            save_state(state)

    # 개정 첫 실행: 기존 우편을 전부 조용히 처리하고 끝낸다(폭주 방지).
    if state.get('baseline') != BASELINE_ID:
        existing = [norm_key(p.relative_to(mailbox_dir)) for p in mailbox_dir.rglob('*.md')]
        notified.update(existing)
        state['baseline'] = BASELINE_ID
        persist()
        print(f"[INFO] 개정 첫 실행: 기존 우편 {len(existing)}건을 발송 없이 처리 표시함.")
        return 0

    sent_boss = sent_agent = held = 0
    for md_file in sorted(mailbox_dir.rglob('*.md')):
        rel_path = norm_key(md_file.relative_to(mailbox_dir))
        if rel_path in notified:
            continue
        recipient, sender, subject, body_first, ask = extract_metadata_and_body(md_file)
        if not all([recipient, sender, subject]):
            continue

        if recipient == '사장님':
            if not ask:
                notified.add(rel_path)          # 사장님이 할 일이 없으면 폰에 안 보낸다
                held += 1
                continue
            if _count(state, boss_key) >= BOSS_DAILY_LIMIT:
                continue                        # 상한: 다음 날 다시 시도
            msg = build_message_for_boss(sender, subject, body_first, ask)
            chat, key = boss_chat, boss_key
        else:
            if not agent_chat:
                notified.add(rel_path)          # 에이전트 채널 미설정: 어디에도 안 보낸다
                held += 1
                continue
            if _count(state, agent_key) >= AGENT_DAILY_LIMIT:
                notice_key = f"agent_cap_notice_{today}"
                if not state.setdefault('daily_counts', {}).get(notice_key):
                    state['daily_counts'][notice_key] = True
                    if live:
                        send_telegram(token, agent_chat,
                                      f"📨 오늘 에이전트 소통이 {AGENT_DAILY_LIMIT}건을 넘었습니다. 나머지는 우편함에서 확인하세요.")
                notified.add(rel_path)
                held += 1
                continue
            msg = build_message_agent(sender, recipient, subject, body_first)
            chat, key = agent_chat, agent_key

        if not live:
            where = '사장님(신솔라)' if chat == boss_chat else '에이전트 채널'
            print(f"[{'DRY-RUN' if dry_run else 'TEST'}] 발송 예정 → {where}: {rel_path}")
            print("  " + msg.replace("\n", "\n  "))
            notified.add(rel_path)
            _inc(state, key)
            continue
        result = send_telegram(token, chat, msg)
        if result.get('ok'):
            notified.add(rel_path)
            _inc(state, key)
            persist()                            # 발송 직후 저장
            if chat == boss_chat:
                sent_boss += 1
            else:
                sent_agent += 1
        else:
            print(f"[ERROR] 발송 실패: {rel_path} → {result.get('description') or result.get('error')}")

    persist()
    print(f"[INFO] 신솔라 {sent_boss}건, 에이전트 채널 {sent_agent}건 발송, 폰 미발송 처리 {held}건.")
    return 0


if __name__ == '__main__':
    sys.exit(main())
