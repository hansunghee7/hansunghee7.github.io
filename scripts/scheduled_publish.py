#!/usr/bin/env python3
"""예약 발행: 예약 스위치를 켠 초안(published: false)을 발행일 시각이 지나면 공개로 바꾼다.

정본 문서: docs/예약_발행.md

동작 요약
---------
log_assets/markdown/*.md 의 front matter 에서 아래 네 조건이 모두 맞는 글만
`published: false` 를 `published: true` 로 바꾼다.
  1. published 가 false  (예약 글은 예약 시각 전까지 노출이 꺼져 있다)
  2. scheduled 가 true   (CMS 의 "예약 발행" 스위치. 없거나 false 면 예약이
     아니므로 절대 안 건드림. 비노출 글과 컨펌 전 초안을 지키는 장치다)
  3. date(발행일)가 날짜+시각 형식이다
  4. 지금 시각 >= date

노출 여부(published)와 예약(scheduled)은 별개다. 예약 스위치가 없는 글은
published 가 false 여도 발행일이 과거든 미래든 영향이 없다.

안전장치 (이 파일이 지키는 것)
------------------------------
* 파일을 바이트 단위로 읽고 쓴다. 바꾸는 곳은 `published:` 줄의 값 한 단어
  (false -> true) 뿐이다. 본문, 다른 front matter 줄, 줄바꿈(CRLF/LF),
  BOM, 끝 개행 유무는 그대로다. YAML 을 파싱해 다시 쓰지 않는다
  (scripts/normalize_new_post.py 와 같은 원칙: 필요한 삽입만 정규식으로).
* scheduled 줄은 지우지 않는다(기록용).
* 지나간 시각으로 건 예약은 공개하지 않는다: 발행일이 그 글의 마지막 저장(git
  커밋) 시각보다 앞이면 경고만 남기고 건너뛴다. git 기록이 없으면(임시 폴더
  시험 등) 이 검사는 생략한다.
* 멱등: published: true 가 된 글은 다음 실행에서 조건 1 에 안 걸려 대상 아님.
* 예약 스위치가 켜졌는데 date 형식이 잘못된 글은 건너뛰고 경고만 남긴다
  (종료 코드 0). 한 글의 오타가 다른 글의 발행을 막으면 안 되기 때문이다.
* 시간대: 표기에 오프셋(+09:00, Z 등)이 있으면 그대로 따르고, 오프셋이 없으면
  한국시간(Asia/Seoul, UTC+9)으로 해석한다. 서버(UTC)의 로컬 시각은 쓰지
  않는다. 한국은 서머타임이 없어 고정 +09:00 이 정확하다(tzdata 불필요).
* 날짜만 쓴 값(2026-09-24)은 "몇 시"인지 모호해서 형식 오류로 취급한다.

사용법
------
  python scripts/scheduled_publish.py                       # 실제 반영
  python scripts/scheduled_publish.py --dry-run             # 무엇을 바꿀지만 출력
  python scripts/scheduled_publish.py --dir <폴더> --now 2026-09-25T00:00:00+09:00 --dry-run
    (--now 는 시뮬레이션용이라 --dry-run 과 함께일 때만 허용 -- 실수로
     "미래 시각"으로 진짜 발행하는 사고를 막는다)

종료 코드: 0 = 정상 종료(대상 0건, 형식 오류 건너뜀 포함), 2 = 사용법 오류
(--now 를 --dry-run 없이 씀, 폴더 없음, 잘못된 --now).
GITHUB_OUTPUT 이 있으면 changed=<바뀐 글 수>, invalid=<형식 오류 수> 를 적는다.
"""
import argparse
import os
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone

DEFAULT_DIR = "log_assets/markdown"
KST = timezone(timedelta(hours=9), "KST")

PUBLISHED_RE = re.compile(r"^published:[ \t]*(?P<val>[^\r\n]*?)[ \t]*$", re.I)
SCHEDULED_RE = re.compile(r"^scheduled:[ \t]*(?P<val>[^\r\n]*?)[ \t]*$", re.I)
DATE_RE = re.compile(r"^date:[ \t]*(?P<val>[^\r\n]*?)[ \t]*$", re.I)
# 2026-09-24T10:00 / 2026-09-24 10:00:00 / ...T10:00:00.5 + 선택적 오프셋
TS_RE = re.compile(
    r"^(?P<y>\d{4})-(?P<mo>\d{2})-(?P<d>\d{2})[T ](?P<h>\d{2}):(?P<mi>\d{2})"
    r"(?::(?P<s>\d{2})(?:\.\d+)?)?"
    r"(?P<tz>Z|z|[+-]\d{2}:?\d{2})?$"
)


LINE_RE = re.compile(r"[^\r\n]*(?:\r\n|\n|\r)|[^\r\n]+")


class BadFormat(Exception):
    pass


def is_true_value(raw):
    """scheduled 값이 켜짐(true)인가. 따옴표와 줄 끝 주석은 허용, 그 외(false, 빈 값, null)는 꺼짐."""
    val = re.split(r"\s+#", raw.strip(), maxsplit=1)[0].strip().strip("\"'").strip()
    return val.lower() == "true"


def parse_publish_at(raw):
    """발행일(date) 문자열 -> timezone-aware datetime. 형식이 틀리면 BadFormat."""
    val = raw.strip()
    # YAML 따옴표('...' 또는 "...") 벗기기. 줄 끝 주석(" # ...")은 따옴표 밖일 때만.
    if len(val) >= 2 and val[0] in "\"'":
        q = val[0]
        end = val.find(q, 1)
        if end == -1:
            raise BadFormat(f"따옴표가 닫히지 않음: {raw!r}")
        rest = val[end + 1 :].strip()
        if rest and not rest.startswith("#"):
            raise BadFormat(f"따옴표 뒤에 다른 내용이 있음: {raw!r}")
        val = val[1:end].strip()
    else:
        val = re.split(r"\s+#", val, maxsplit=1)[0].strip()
    if not val:
        raise BadFormat("발행일(date) 값이 비어 있음")
    m = TS_RE.match(val)
    if not m:
        raise BadFormat(
            f"형식이 ISO 8601 날짜+시각이 아님: {raw!r} "
            "(예: 2026-09-24T10:00:00+09:00, 날짜만 쓰면 안 됨)"
        )
    tz = m.group("tz")
    if tz is None:
        tzinfo = KST  # 오프셋이 없으면 한국시간
    elif tz in ("Z", "z"):
        tzinfo = timezone.utc
    else:
        sign = 1 if tz[0] == "+" else -1
        digits = tz[1:].replace(":", "")
        hh, mm = int(digits[:2]), int(digits[2:])
        if hh > 23 or mm > 59:
            raise BadFormat(f"시간대 오프셋이 이상함: {tz!r}")
        tzinfo = timezone(sign * timedelta(hours=hh, minutes=mm))
    try:
        return datetime(
            int(m.group("y")), int(m.group("mo")), int(m.group("d")),
            int(m.group("h")), int(m.group("mi")), int(m.group("s") or 0),
            tzinfo=tzinfo,
        )
    except ValueError as e:  # 2026-13-45 같은 존재하지 않는 날짜/시각
        raise BadFormat(f"존재하지 않는 날짜/시각: {raw!r} ({e})")


def split_front_matter(text):
    """(fm_start, fm_end) 문자 위치를 돌려준다. front matter 가 없으면 None.

    fm_start = 첫 `---` 줄 다음 위치, fm_end = 닫는 `---` 줄이 시작하는 위치.
    이 구간의 줄들만 검사·수정한다.
    """
    body = text[1:] if text.startswith("\ufeff") else text
    offset = 1 if text.startswith("\ufeff") else 0
    m = re.match(r"---[ \t]*\r?\n", body)
    if not m:
        return None
    start = m.end()
    for line in re.finditer(r"^---[ \t]*(?:\r?\n|$)", body[start:], re.M):
        return offset + start, offset + start + line.start()
    return None


def last_commit_time(path):
    """그 글 파일을 마지막으로 저장(커밋)한 시각. git 기록이 없으면 None(검사 생략)."""
    try:
        r = subprocess.run(
            ["git", "-C", os.path.dirname(os.path.abspath(path)), "log", "-1",
             "--format=%cI", "--", os.path.basename(path)],
            capture_output=True, encoding="utf-8", timeout=30,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    out = r.stdout.strip()
    if r.returncode != 0 or not out:
        return None
    try:
        return datetime.fromisoformat(out)
    except ValueError:
        return None


def process_text(text, now, saved_at=None):
    """(new_text, status, detail).

    saved_at: 그 글을 마지막으로 저장한 시각(없으면 None). 예약 시각이 저장 시각보다
    앞이면 "지나간 시각으로 건 예약"이라 공개하지 않고 경고한다(규칙: 지나간
    날짜·시간은 예약 불가).

    status: 'publish' | 'future' | 'not_scheduled' | 'already_public' |
            'no_front_matter' | 'invalid'
    """
    span = split_front_matter(text)
    if span is None:
        return text, "no_front_matter", "front matter 없음"
    fm_start, fm_end = span
    fm = text[fm_start:fm_end]

    pub_lines = []  # (줄 시작 위치(fm 기준), 줄 텍스트(개행 제외))
    sched_lines = []
    date_lines = []
    pos = 0
    for line in LINE_RE.findall(fm):
        stripped = line.rstrip("\r\n")
        if PUBLISHED_RE.match(stripped):
            pub_lines.append((pos, stripped))
        elif SCHEDULED_RE.match(stripped):
            sched_lines.append((pos, stripped))
        elif DATE_RE.match(stripped):
            date_lines.append((pos, stripped))
        pos += len(line)

    # 예약 스위치가 없거나 true 가 아님 -> 비노출 글, 컨펌 전 초안, 예약과 무관한
    # 글. published/date 가 어떻든 절대 안 건드림.
    if not any(is_true_value(SCHEDULED_RE.match(l).group("val")) for _, l in sched_lines):
        return text, "not_scheduled", ""
    if len(pub_lines) != 1 or len(sched_lines) != 1 or len(date_lines) != 1:
        return text, "invalid", (
            f"published 줄 {len(pub_lines)}개 / scheduled 줄 {len(sched_lines)}개 / "
            f"date 줄 {len(date_lines)}개 (각각 정확히 1개여야 함)"
        )

    pub_pos, pub_line = pub_lines[0]
    pval = PUBLISHED_RE.match(pub_line).group("val")
    if pval.lower() == "true":
        return text, "already_public", ""
    if pval.lower() != "false":
        return text, "invalid", f"published 값이 true/false 가 아님: {pval!r}"

    try:
        at = parse_publish_at(DATE_RE.match(date_lines[0][1]).group("val"))
    except BadFormat as e:
        return text, "invalid", str(e)

    if now < at:
        return text, "future", at.isoformat()
    if saved_at is not None and at <= saved_at:
        return text, "invalid", (
            f"예약 시각({at.isoformat()})이 마지막 저장 시각({saved_at.isoformat()})보다 앞이라 "
            "예약으로 인정하지 않음(지나간 시각은 예약할 수 없음). 발행일을 미래 시각으로 고쳐 다시 저장하세요"
        )

    # published: false 의 'false' 한 단어만 'true' 로. 줄 앞뒤 공백/개행은 그대로.
    line_start = fm_start + pub_pos
    m = re.match(r"^(published:[ \t]*)false", pub_line, re.I)
    key_end = line_start + len(m.group(1))
    new_text = text[:key_end] + "true" + text[key_end + len("false") :]
    return new_text, "publish", at.isoformat()


def read_text(path):
    with open(path, "rb") as f:
        raw = f.read()
    return raw.decode("utf-8")  # 잘못된 바이트면 UnicodeDecodeError -> 호출부에서 경고


def write_text(path, text):
    with open(path, "wb") as f:  # newline 변환 없이 바이트 그대로
        f.write(text.encode("utf-8"))


def parse_now(value):
    if not value:
        return datetime.now(timezone.utc)
    try:
        dt = parse_publish_at(value)
    except BadFormat as e:
        print(f"--now 값이 잘못됨: {e}", file=sys.stderr)
        sys.exit(2)
    return dt


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--dir", default=DEFAULT_DIR, help="글 폴더 (기본 log_assets/markdown)")
    ap.add_argument("--dry-run", action="store_true", help="바꿀 내용만 출력하고 파일은 안 씀")
    ap.add_argument("--now", default="", help="시뮬레이션용 현재 시각(ISO 8601). --dry-run 과 함께만 허용")
    args = ap.parse_args(argv)

    if args.now and not args.dry_run:
        print("--now 는 --dry-run 과 함께만 쓸 수 있습니다(실수로 미래 시각 발행 방지).", file=sys.stderr)
        return 2
    if not os.path.isdir(args.dir):
        print(f"폴더가 없습니다: {args.dir}", file=sys.stderr)
        return 2

    now = parse_now(args.now)
    print(f"기준 시각: {now.astimezone(KST).isoformat()} (KST) / {now.astimezone(timezone.utc).isoformat()} (UTC)")
    print(f"대상 폴더: {args.dir} / 모드: {'DRY-RUN (파일 안 씀)' if args.dry_run else '실제 반영'}")

    counts = {}
    changed = []
    invalid = []
    for name in sorted(os.listdir(args.dir)):
        if not name.lower().endswith(".md"):
            continue
        path = os.path.join(args.dir, name)
        try:
            text = read_text(path)
        except (OSError, UnicodeDecodeError) as e:
            counts["invalid"] = counts.get("invalid", 0) + 1
            invalid.append((name, f"파일을 읽을 수 없음: {e}"))
            continue
        # git 조회는 공개 직전 후보에만 필요하지만, 글이 수백 편이라 매번 부르면 느리므로
        # 예약 스위치가 켜진 글일 때만 조회한다.
        saved_at = last_commit_time(path) if re.search(r"^scheduled:[ \t]*[\"']?true", text, re.I | re.M) else None
        new_text, status, detail = process_text(text, now, saved_at)
        counts[status] = counts.get(status, 0) + 1
        if status == "invalid":
            invalid.append((name, detail))
        elif status == "future":
            print(f"  대기: {name} (발행일={detail})")
        elif status == "publish":
            changed.append(name)
            if args.dry_run:
                print(f"  [DRY-RUN] 공개 예정: {name} (발행일={detail})")
            else:
                write_text(path, new_text)
                print(f"  공개 처리: {name} (발행일={detail})")

    for name, why in invalid:
        # GitHub Actions 로그에서 노란 경고로 보이게 ::warning:: 형식 사용
        print(f"::warning file={args.dir}/{name}::예약 발행 건너뜀: {why}")

    print("--- 요약 ---")
    print(f"공개 {'예정' if args.dry_run else '처리'}: {len(changed)}건")
    print(f"미래(대기): {counts.get('future', 0)}건")
    print(f"형식 오류로 건너뜀: {len(invalid)}건")
    print(f"예약 아님(안 건드림): {counts.get('not_scheduled', 0)}건 / 이미 공개(예약 스위치 켜짐): {counts.get('already_public', 0)}건")
    if invalid:
        print("형식 오류 목록: " + ", ".join(n for n, _ in invalid))

    out = os.environ.get("GITHUB_OUTPUT")
    if out:
        with open(out, "a", encoding="utf-8") as f:
            f.write(f"changed={0 if args.dry_run else len(changed)}\n")
            f.write(f"invalid={len(invalid)}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
