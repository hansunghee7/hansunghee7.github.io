# -*- coding: utf-8 -*-
"""회의록 브리핑 발행기(마야 2026-10-22, 마야#228).

입력: 대본(md), 회의 날짜(YYYYMMDD), 회의명(한글), 회의록 문서 ID
처리: GPU 자리 신청 -> 마야 목소리(CosyVoice 3, Aoede, 110%) 생성 -> 파일명 `날짜_회의명_ID6.mp3`
      -> 팟캐스트 briefing 시리즈 등록 -> 텔레그램 전송 -> GPU 반납
대본 쓰기와 드라이브 회의록 읽기·제목 변경은 클로드 세션(예약 작업)이 맡고, 이 스크립트는 소리와 전달만 한다.
회의록 원문은 저장하지 않는다. 대본에는 인사 관련 내용을 넣지 않는다(탐-슈퍼글로벌#57).
"""
import argparse
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
TTS_PY = Path("C:/work/_ops/cosyvoice_test/venv/Scripts/python.exe")
TTS = Path("C:/work/_ops/maya_voice_lab/maya_tts.py")
OUT_ROOT = Path("C:/work/_ops/maya_briefs/meeting_auto")
NOWIN = subprocess.CREATE_NO_WINDOW


def run(cmd, **kw):
    return subprocess.run(cmd, creationflags=NOWIN, capture_output=True, text=True, encoding="utf-8", errors="replace", **kw)


def safe_name(title: str) -> str:
    t = re.sub(r"[\\/:*?\"<>|\s]+", "", title)
    return t[:40]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("script", help="브리핑 대본 md")
    ap.add_argument("--date", required=True, help="회의 날짜 YYYYMMDD")
    ap.add_argument("--title", required=True, help="회의명(한글)")
    ap.add_argument("--doc-id", required=True, help="드라이브 회의록 문서 ID")
    ap.add_argument("--no-publish", action="store_true", help="음성만 만들고 팟캐스트·텔레그램은 건너뜀(시험용)")
    a = ap.parse_args()

    script = Path(a.script)
    if not script.exists() or script.stat().st_size < 200:
        sys.exit("대본이 없거나 너무 짧음")
    name = f"{a.date}_{safe_name(a.title)}_{a.doc_id[:6]}.mp3"
    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    mp3 = OUT_ROOT / name

    g = run([sys.executable, str(REPO / "scripts/ops/gpu_gate.py"), "need", "4", "--who", "마야", "--note", "회의 브리핑 자동"], cwd=REPO)
    print("gpu:", g.stdout.strip().splitlines()[-1] if g.stdout.strip() else g.stderr.strip()[:200])
    try:
        r = run([str(TTS_PY), str(TTS), str(script), str(mp3)])
        tail = (r.stdout + r.stderr).strip().splitlines()[-1:] or [""]
        print("tts:", tail[0][:200])
        if r.returncode != 0 or not mp3.exists():
            sys.exit("음성 생성 실패")
    finally:
        run([sys.executable, str(REPO / "scripts/ops/gpu_gate.py"), "release", "--who", "마야"], cwd=REPO)

    d = run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(mp3)])
    sec = int(float(d.stdout.strip() or 0))
    print(f"mp3: {mp3} ({sec // 60}분 {sec % 60}초)")
    if a.no_publish:
        return
    run([sys.executable, str(REPO / "scripts/ops/podcast_feed.py"), "--show", "briefing", "add",
         "--title", f"회의 브리핑: {a.title}", "--desc", f"{a.date} 회의 요약({sec // 60}분 {sec % 60}초)", str(mp3)], cwd=REPO)
    t = run([sys.executable, str(REPO / "scripts/ops/tg_boss.py"), "doc", str(mp3), "--persona", "마야",
             "--caption", f"회의 브리핑 | {a.date} {a.title} ({sec // 60}분 {sec % 60}초)"], cwd=REPO)
    print("telegram:", (t.stdout + t.stderr).strip().splitlines()[-1:])


if __name__ == "__main__":
    main()
