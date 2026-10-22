"""매일 옛 이름 스캔 래퍼: name_scan.py(읽기 전용)를 돌려 결과 md·json과 한 줄 요약을 남긴다.

산출물: C:/work/_ops/name_scan/YYYY-MM-DD.md·json(name_scan.py가 직접 씀, 다음날 기준선 비교에 쓰인다),
latest.txt(한 줄 요약, 감시 대장이 갱신 시각을 본다). --no-write를 주면 json이 영영 안 남아
기준선 비교가 매번 "없음"이 되므로(2026-10-22 사고) 반드시 기본 쓰기 경로로 돌린다.
name_scan.py의 종료 코드 1은 '위반 있음'이라 정상 경로다. 그 밖(스캔 자체 실패)만 실패로 본다.
"""
import datetime as dt
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT_DIR = Path("C:/work/_ops/name_scan")


def parse_summary(text):
    """출력 첫 8줄에서 판정과 위반·예정·미확인 수를 뽑는다. 판정 줄이 없으면 None."""
    for line in text.splitlines()[:8]:
        if "판정:" not in line:
            continue
        if "완료 가능" in line:
            return {"verdict": "완료 가능", "violation": 0, "planned": 0, "unverified": 0}
        nums = {}
        for key, ko in (("violation", "위반"), ("planned", "예정"), ("unverified", "미확인")):
            m = re.search(ko + r"\s+(\d+)", line)
            nums[key] = int(m.group(1)) if m else 0
        return {"verdict": "완료 불가", **nums}
    return None


def summary_line(s, today):
    return "%s 판정=%s 위반=%d 예정=%d 미확인=%d" % (today, s["verdict"], s["violation"], s["planned"], s["unverified"])


def main():
    today = dt.date.today().isoformat()
    p = subprocess.run([sys.executable, str(HERE / "name_scan.py")], capture_output=True,
                       timeout=900, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    text = p.stdout.decode("utf-8", errors="replace")
    s = parse_summary(text)
    if p.returncode not in (0, 1) or s is None:
        print("스캔 실패: rc=%s, 판정 줄 %s" % (p.returncode, "없음" if s is None else "있음"))
        return 2
    if not (OUT_DIR / (today + ".json")).exists():
        print("스캔 실패: json 미작성(%s)" % (OUT_DIR / (today + ".json")))
        return 2
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    line = summary_line(s, today)
    (OUT_DIR / "latest.txt").write_text(line + "\n", encoding="utf-8")
    print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
