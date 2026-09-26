"""헤르메스(또는 다른 에이전트)에게 위임한 뒤 회신을 기다릴 때 쓰는 공용 감시 스크립트.

왜: 우편함은 "받는 쪽이 새 세션을 열 때만" 자동으로 보여준다(session-start 훅). 이미 떠 있는
세션에게는 아무도 찔러주지 않고, 헤르메스는 Claude 세션이 아니라 SendMessage로 깨울 수도 없다.
그래서 위임 직후 이 스크립트를 Monitor 도구로 백그라운드에 띄워두면, 새 우편이 도착하는 순간
이벤트로 알림을 받는다(수동으로 몇 분마다 mailbox.py read를 다시 부르지 않아도 됨).

비용: 이 스크립트 자체는 로컬 파일 존재 여부만 주기적으로 확인하는 순수 파이썬 프로세스라
Claude API를 전혀 안 부른다(토큰 0). 토큰은 실제로 새 줄을 출력해 Monitor 이벤트가 될 때와,
Monitor가 만료돼 재무장할 때만 아주 조금 든다.

사용(사장님·모든 페르소나 공통): 위임 우편(`mailbox.py send`)을 보낸 직후,
    python scripts/ops/watch_mailbox_reply.py --persona 탐 --keyword 헤르메스,구PC,goosolar
를 Monitor 도구의 command로 띄운다(직접 bash로 실행 후 방치하지 않는다 - run_in_background는
완료 시에만 알리므로, 이벤트마다 알림받으려면 Monitor를 쓴다). --keyword는 발신자·주제로 보이는
낱말을 쉼표로 나열(파일명에 포함되면 그 낱말로 표시), 비우면 전부 새 우편이라고만 알린다.

참고: hermes-delegate 스킬, CLAUDE.md id:b7f1.
"""
import argparse, glob, os, sys, time


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--persona", required=True, help="우편함 폴더 이름 (예: 탐, 지투, 노트, 핏, 마야)")
    ap.add_argument("--mailbox-root", default=r"C:\work\solar-bible\mailbox")
    ap.add_argument("--keyword", default="", help="쉼표로 구분된 낱말, 파일명에 있으면 강조 표시(없으면 전부 표시)")
    ap.add_argument("--interval", type=float, default=15.0, help="확인 주기(초)")
    ap.add_argument("--timeout", type=float, default=3600 * 3, help="이 시간(초) 넘게 새 우편 없으면 스스로 멈춤")
    ap.add_argument("--since", type=float, default=None, help="이 시각(epoch) 이후 파일만 봄, 기본은 지금부터")
    a = ap.parse_args()

    sys.stdout.reconfigure(encoding="utf-8")
    inbox = os.path.join(a.mailbox_root, a.persona)
    since = a.since if a.since is not None else time.time()
    keywords = [k for k in a.keyword.split(",") if k]

    print(f"[watch] {inbox} 폴더를 {a.interval:.0f}초 간격으로 지켜봅니다.", flush=True)
    start = time.time()
    seen = set(glob.glob(os.path.join(inbox, "*.md")))

    while time.time() - start < a.timeout:
        time.sleep(a.interval)
        now = set(glob.glob(os.path.join(inbox, "*.md")))
        new = now - seen
        for f in sorted(new):
            try:
                mtime = os.path.getmtime(f)
            except OSError:
                continue
            if mtime < since:
                continue
            name = os.path.basename(f)
            hit = [k for k in keywords if k.lower() in name.lower()]
            if hit:
                print(f"[watch] 새 우편 도착({'/'.join(hit)}로 보임): {name}", flush=True)
            elif not keywords:
                print(f"[watch] 새 우편 도착: {name}", flush=True)
            else:
                print(f"[watch] 새 우편 도착(발신 미상, 키워드 불일치): {name}", flush=True)
        seen = now

    print(f"[watch] 타임아웃({a.timeout:.0f}초), 감시 종료", flush=True)


if __name__ == "__main__":
    main()
