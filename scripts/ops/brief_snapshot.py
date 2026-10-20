#!/usr/bin/env python3
"""모닝 브리핑용 '사장님 오늘' 스냅샷을 만들어 비공개 저장소에 올린다(2026-10-18 마야, 사장님 '추천대로 진행').

왜: 06:00 브리핑 루틴은 클라우드에서 돌아 운영 DB·로컬 산출물에 손이 닿지 않는다. 그래서 로컬이 05:40에
필요한 값만 JSON으로 뽑아 simplifier-cxo-db/brief_snapshot/YYYY-MM-DD.json 으로(briefs/ 밖: briefs/** push는 메일 발송을 일으킨다) push하고, 루틴은 그 파일을 읽는다.
비밀값·고객 데이터는 넣지 않는다(제목·상태·날짜·집계 숫자만).

담는 것
  deadlines   : 운영 DB tasks 표 section='act'·status='대기'·decider='사장님'의 마감(source_date) 14일 안, 가까운 순
  boss_open   : section='open'·status='사장님' 결정 대기 건수와 오래된 3건
  grants      : 지원사업 표(section='grant') 상태별 건수 + 준비중·지원함·대기 건
  carvit      : C:/work/_ops/saegim_usage 최신 파일의 서버 정상 요청(어제·7일 합)

사용: python scripts/ops/brief_snapshot.py [--no-push] [--out 경로]
"""
import argparse
import collections
import datetime as dt
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.stdout.reconfigure(encoding="utf-8")
import opsdb  # noqa: E402

KST = dt.timezone(dt.timedelta(hours=9))
CXO = Path("C:/work/simplifier-cxo-db")
USAGE = Path("C:/work/_ops/saegim_usage")
NW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def tasks(**where):
    w = {k: f"eq.{v}" for k, v in where.items()}
    return opsdb.select("tasks", "owner,section,no,title,status,next_action,source_date", where=w, limit=500)


def deadlines(today):
    out = []
    for r in tasks(section="act", status="대기", decider="사장님"):
        try:
            d = dt.date.fromisoformat((r["source_date"] or "")[:10])
        except ValueError:
            continue
        if (d - today).days <= 14:
            out.append({"date": d.isoformat(), "days_left": (d - today).days, "who": r["owner"], "title": r["title"][:80]})
    return sorted(out, key=lambda x: x["date"])[:6]


def boss_open():
    rows = sorted(tasks(section="open", status="사장님"), key=lambda r: r["source_date"] or "")
    return {"count": len(rows), "oldest": [{"who": r["owner"], "title": r["title"][:80]} for r in rows[:3]]}


def grants():
    rows = tasks(section="grant")
    by = collections.Counter(r["status"] for r in rows)
    live = [{"no": r["no"], "title": r["title"][:60], "status": r["status"], "next": (r["next_action"] or "")[:60]}
            for r in rows if r["status"] in ("준비중", "지원함", "대기")]
    return {"by_status": dict(by), "live": live}


def carvit():
    files = sorted(USAGE.glob("*.json"))
    if not files:
        return None
    d = json.loads(files[-1].read_text(encoding="utf-8"))
    ok = d.get("requests_by_class", {}).get("2xx", {})
    days = sorted(ok)[-7:]
    return {"collected_at": d.get("collected_at"), "requests_2xx_last_day": {days[-1]: ok[days[-1]]} if days else {},
            "requests_2xx_7d": int(sum(ok[k] for k in days)), "errors_5xx_30d": d.get("errors_5xx_30d")}


def push(path, day, cxo=None):
    """main이 아닌 브랜치에서는 pull·commit·push를 하지 않는다(2026-10-20: 다른 브랜치에 커밋이 섞이고 push 거절로 종료 1).

    산출 파일은 이미 로컬에 써 둔 뒤라 파일은 항상 갱신된다. 반환: 0 성공, 1 가드 거절.
    """
    cxo = Path(cxo) if cxo else CXO
    git = ["git", "-C", str(cxo)]
    cur = subprocess.run(git + ["branch", "--show-current"], stdin=subprocess.DEVNULL, creationflags=NW, capture_output=True, text=True).stdout.strip()
    if cur != "main":
        print(f"push 건너뜀: {cxo} 가 main이 아니라 '{cur or '(detached)'}' 브랜치입니다. 산출 파일은 로컬에 저장됨. 폴더를 main으로 돌린 뒤 다시 실행하세요.", file=sys.stderr)
        return 1
    subprocess.run(git + ["pull", "-q", "--rebase", "origin", "main"], stdin=subprocess.DEVNULL, capture_output=True, creationflags=NW, check=False)
    subprocess.run(git + ["add", str(path)], stdin=subprocess.DEVNULL, capture_output=True, creationflags=NW, check=True)
    if subprocess.run(git + ["diff", "--cached", "--quiet"], stdin=subprocess.DEVNULL, capture_output=True, creationflags=NW).returncode == 0:
        print("변경 없음")
        return 0
    subprocess.run(git + ["commit", "-qm", f"briefs: {day} 사장님 오늘 스냅샷"], stdin=subprocess.DEVNULL, capture_output=True, creationflags=NW, check=True)
    subprocess.run(git + ["push", "-q", "origin", "HEAD:main"], stdin=subprocess.DEVNULL, capture_output=True, creationflags=NW, check=True)
    print("push 완료")
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-push", action="store_true")
    ap.add_argument("--out")
    a = ap.parse_args()
    now = dt.datetime.now(KST)
    snap = {"generated_at": now.isoformat(timespec="seconds"), "deadlines": deadlines(now.date()),
            "boss_open": boss_open(), "grants": grants(), "carvit": carvit()}
    path = Path(a.out) if a.out else CXO / "brief_snapshot" / f"{now:%Y-%m-%d}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(snap, ensure_ascii=False, indent=1), encoding="utf-8")
    print(path, f"마감 {len(snap['deadlines'])} · 결정대기 {snap['boss_open']['count']} · 진행 지원사업 {len(snap['grants']['live'])}")
    if not a.no_push and not a.out:
        return push(path, f"{now:%Y-%m-%d}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
