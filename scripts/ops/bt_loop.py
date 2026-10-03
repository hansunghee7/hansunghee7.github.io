"""비티(Antigravity) 상시 검토 루프 (2026-10-01, N71, 사장님 지시).

큐(C:/work/_ops/bt/queue.md)에서 상태 `대기`인 첫 항목을 골라 비티(구PC agy)에게 검토를 맡기고,
답을 replies/에 저장한 뒤 큐 항목을 `비티답변`으로 바꾸고 탐에게 우편을 보낸다.
- 횟수 제한 없음(사장님 2026-10-02: "7일 2회 제한을 두지 말고 쓰세요, 지식 상승을 주 2일로 한정할 필요 없다").
  한 번 실행에 `대기` 항목을 모두(최대 10건) 보낸다. 실제 실패(한도 문구·빈 답)가 나면 그때만 24시간 쉰다.
- 답은 가설이다. 채택·반려 판정은 탐 세션이 실측으로 한다(무료 엔진은 판정하지 않는다, CLAUDE.md).
- 고객 정보·비밀값·가격·전략은 대상 파일에 넣지 않는다(큐에 올리기 전 탐이 확인).
사용: python bt_loop.py [--dry-run] [--force]   (스케줄러는 pythonw로 숨김 실행)
"""
import json, re, subprocess, sys, time
from datetime import datetime, timedelta
from pathlib import Path

BASE = Path("C:/work/_ops/bt")
QUEUE = BASE / "queue.md"
STATE = BASE / "state.json"
LAST_RUN = BASE / "last_run"
MAILBOX = Path("C:/work/solar-bible/mailbox/mailbox.py")
MAX_PER_7D, MIN_GAP_H, BACKOFF_H = 2, 36, 24
NOWIN = 0x08000000  # CREATE_NO_WINDOW

PREAMBLE = (
    "너는 심플리파이어의 독립 2차 검증자(비티)다. 아래 '검토 대상'을 보안·설계 관점에서 검토하고 한국어로 답한다.\n"
    "규칙: ① 반증 가능한 구체적 지적만(막연한 칭찬·일반론 금지) ② 각 지적에 대상의 어느 절·문장인지 짚고, 심각도(높음/중간/낮음)와 고치는 방법 한 줄 ③ 확신이 낮은 것은 '가설'이라고 표시 "
    "④ 지적이 없으면 없다고 쓴다 ⑤ 다른 파일은 수정하지 말고 답변 본문만 출력한다.\n"
)


QUOTA = Path(__file__).resolve().parent / "quota.py"
# 모델 순서(사장님 결정 10/3): 비티가 있는 이유는 다양성이라 제미나이 먼저, 한도가 막히면 Sonnet으로 자동 전환.
ORDER = [("비티", ""), ("비티-sonnet", "--model claude-sonnet-4-6")]


def load_state():
    if STATE.exists():
        return json.loads(STATE.read_text(encoding="utf-8"))
    return {"calls": [], "next_allowed": None}


def parse_queue(text):
    items = []
    for m in re.finditer(r"^### (B\d+) \[(.+?)\] (.*)$", text, re.M):
        items.append({"id": m.group(1), "status": m.group(2), "title": m.group(3), "start": m.start(), "head_end": m.end()})
    for i, it in enumerate(items):
        it["end"] = items[i + 1]["start"] if i + 1 < len(items) else len(text)
        body = text[it["head_end"]:it["end"]]
        it["body"] = body
        t = re.search(r"^- 대상: (.+)$", body, re.M)
        q = re.search(r"^- 질문: (.+)$", body, re.M)
        it["target"] = t.group(1).strip() if t else None
        it["question"] = q.group(1).strip() if q else None
    return items


def main():
    dry, force = "--dry-run" in sys.argv, "--force" in sys.argv
    now = datetime.now()
    st = load_state()
    if not force:
        if st.get("next_allowed") and now < datetime.fromisoformat(st["next_allowed"]):
            print("skip: 쉬는 중 until", st["next_allowed"]); LAST_RUN.write_text(now.strftime("%F %T") + " skip-backoff\n"); return 0
    text = QUEUE.read_text(encoding="utf-8")
    pending = [i for i in parse_queue(text) if i["status"] == "대기"]
    if not pending:
        print("skip: 대기 항목 없음"); LAST_RUN.write_text(now.strftime("%F %T") + " skip-empty\n"); return 0
    it = pending[0]
    if not it["target"] or not it["question"]:
        print("error: 항목 %s에 대상/질문 줄이 없음" % it["id"]); return 2
    target = (BASE / it["target"]).read_text(encoding="utf-8")[:40000]
    prompt = PREAMBLE + "\n=== 검토 대상 ===\n" + target + "\n\n=== 질문 ===\n" + it["question"] + "\n"
    if dry:
        print("dry-run: %s %s (%d bytes 프롬프트)" % (it["id"], it["title"], len(prompt.encode("utf-8")))); return 0
    # 한도 관문(10/3 사장님 지시 "한도는 탐이 관리") + 페일오버: 제미나이가 막혔거나 한도 오류가 나면 Sonnet으로.
    out, rc, POOL = "", 99, None
    for pool, marg in ORDER:
        q = subprocess.run([sys.executable, str(QUOTA), "check", pool, "--who", "탐"], capture_output=True, text=True, encoding="utf-8", creationflags=NOWIN)
        if q.returncode != 0:
            continue
        cmd = ["ssh", "-o", "ConnectTimeout=15", "-o", "BatchMode=yes", "goosolar",
               'cd ~/carvit-pass/ag-test && timeout 280 ~/.local/bin/agy %s -p "$(cat)"' % marg]
        t0 = datetime.now()
        hit = None
        try:
            r = subprocess.run(cmd, input=prompt, capture_output=True, text=True, encoding="utf-8", timeout=330, creationflags=NOWIN)
            out, rc = r.stdout, r.returncode
            hit = re.search(r"Individual quota reached.*", r.stderr or "")
        except subprocess.TimeoutExpired:
            out, rc = "", 124
        try:  # 한도 대장(quota.py)이 세도록 호출 기록을 남긴다(10/3: 이 루프만 기록이 빠져 있었음)
            calls = Path("C:/work/_ops/agent_calls.csv")
            new_file = not calls.exists()
            with calls.open("a", encoding="utf-8") as f:
                if new_file:
                    f.write("time,who,sec,rc,out_bytes,limit_hit" + chr(10))
                f.write("%s,%s,%d,%s,%d,0%s" % (t0.strftime("%F %T"), pool, int((datetime.now() - t0).total_seconds()), rc, len(out.encode("utf-8")), chr(10)))
        except OSError:
            pass
        if hit:  # 한도 오류는 stderr에만 나온다. 대장에 막힘을 적고 다음 모델로
            subprocess.run([sys.executable, str(QUOTA), "hit", pool, hit.group(0)], creationflags=NOWIN)
            continue
        POOL = pool
        break
    if POOL is None and rc == 99:
        print("skip: 모든 모델이 한도 관문에서 멈춤"); LAST_RUN.write_text(now.strftime("%F %T") + " skip-quota" + chr(10)); return 0
    bad = rc != 0 or len(out.strip()) < 300 or (len(out.strip()) < 1500 and re.search(r"quota|rate.?limit|429|exhaust", out, re.I))  # 긴 정상 답에 "한도"가 나오는 오탐 방지(10/1 B3)
    if bad:
        st["next_allowed"] = (now + timedelta(hours=BACKOFF_H)).isoformat()
        STATE.write_text(json.dumps(st, ensure_ascii=False, indent=1), encoding="utf-8")
        LAST_RUN.write_text(now.strftime("%F %T") + " fail rc=%s\n" % rc)
        print("fail: rc=%s, 출력 %d자, %d시간 쉼" % (rc, len(out), BACKOFF_H)); return 1
    rep = BASE / "replies" / ("%s_%s.md" % (it["id"], now.strftime("%Y%m%d")))
    rep.write_text("# %s %s: 비티 답(가설, 탐 실측 전)\n\n- 질문: %s\n- 시각: %s\n- 모델 풀: %s\n\n---\n\n%s\n" % (it["id"], it["title"], it["question"], now.strftime("%F %T"), POOL, out), encoding="utf-8")
    new_body = it["body"].replace("- 비티답변:", "- 비티답변: replies/%s" % rep.name, 1) if "- 비티답변:" in it["body"] else it["body"].rstrip("\n") + "\n- 비티답변: replies/%s\n\n" % rep.name
    text = text[:it["start"]] + "### %s [비티답변] %s" % (it["id"], it["title"]) + new_body + text[it["end"]:]
    QUEUE.write_text(text, encoding="utf-8")
    st["calls"] = [c for c in st["calls"] if now - datetime.fromisoformat(c) < timedelta(days=7)] + [now.isoformat()]
    st["next_allowed"] = None
    STATE.write_text(json.dumps(st, ensure_ascii=False, indent=1), encoding="utf-8")
    LAST_RUN.write_text(now.strftime("%F %T") + " ok %s\n" % it["id"])
    if MAILBOX.exists():
        subprocess.run([sys.executable, str(MAILBOX), "send", "탐", "비티 답 도착: %s %s" % (it["id"], it["title"]), "--from", "탐",
                        "--body", "비티 검토 답이 %s에 저장됨. 탐 세션이 실측해 채택/반려를 큐에 기록한다." % rep], creationflags=NOWIN, capture_output=True)
    print("ok: %s -> %s (%d자)" % (it["id"], rep, len(out))); return 0


if __name__ == "__main__":
    rc = 0
    for _ in range(10):  # 대기 항목을 다 보낼 때까지(실패·빈 큐·dry-run이면 멈춤)
        rc = main()
        if rc != 0 or "--dry-run" in sys.argv or " ok " not in (LAST_RUN.read_text(encoding="utf-8") if LAST_RUN.exists() else ""):
            break
    sys.exit(rc)
