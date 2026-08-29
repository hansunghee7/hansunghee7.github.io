r"""
log_assets/images/ 안에서 더 이상 쓰이지 않는 이미지를 찾아 격리 폴더로
옮기는 스크립트. 절대 바로 삭제하지 않는다 -- 옮겨진 파일이 실제로는
쓰이고 있었다는 게 나중에 드러나도 git mv 한 번으로 되돌릴 수 있게 하기
위해서다.

배경 (2026-08-29 사고)
----------------------
이전 정리 작업(커밋 cf70fa1f)은 log_assets/markdown/의 글 본문만 참조
검사 대상으로 삼았다. 그 결과 로고(logo_white.png)와 JSON-LD 구조화
데이터에 쓰이는 캐릭터 이미지(character_black.png)처럼 "블로그 글이
아니라 사이트 템플릿(_includes/, _layouts/)에서만 참조되는 파일"을
고아 파일로 오판해 격리했고, 로고가 깨진 채로 방치됐다가 사장님이
직접 발견했다. 이 스크립트는 그 재발 방지책을 반영한다:

  1. 참조 검사 범위를 markdown 본문뿐 아니라 git이 추적하는 저장소
     전체 텍스트 파일로 넓힌다 (_includes/, _layouts/, JSON-LD, 다른
     스크립트 등 어디서든 파일명이 문자 그대로 등장하면 참조로 인정).
  2. 브랜드 공용 자산(로고·캐릭터 이미지 등)은 이름 패턴으로 한 번 더
     보호한다 -- 저장소 전체 검사에서도 못 찾을 여지(예: JS가 경로를
     동적으로 조합하는 경우)에 대한 이중 안전장치.
  3. 절대 자동으로 삭제하지 않는다. 결과는 quarantine 폴더로 옮기고
     README를 남길 뿐이며, 최종 삭제는 사람이 확인한 뒤 직접 한다.

사용법
------
    python scripts/find_orphan_images.py               # 리포트만 출력 (안전, 기본값)
    python scripts/find_orphan_images.py --quarantine  # 진짜 고아만 격리 폴더로 이동

주의
----
이 스크립트는 "파일명이 텍스트로 어딘가에 등장하는지"만 확인한다.
--quarantine 실행 직후에는 반드시 홈페이지 등 주요 페이지를 실제로 열어
육안으로 깨진 이미지가 없는지 확인할 것.
"""
import argparse
import datetime
import os
import re
import subprocess
import sys

import yaml

MD_DIR = "log_assets/markdown"
IMG_DIR = "log_assets/images"

# 이름 패턴만 봐도 사이트 공용 자산인 것들 -- 저장소 전체 grep에서도 안
# 걸리는 경우에 대비해 이름만으로 한 번 더 보호한다.
PROTECTED_NAME_PATTERNS = [
    re.compile(r'^logo', re.I),
    re.compile(r'^character_', re.I),
    re.compile(r'^favicon', re.I),
    re.compile(r'^apple-touch-icon', re.I),
]

RAW_IMG_RE = re.compile(r'<img\b([^>]*)>')
SRC_RE = re.compile(r'\bsrc="([^"]+)"')


def is_protected(basename):
    return any(p.search(basename) for p in PROTECTED_NAME_PATTERNS)


def load_front_matter(raw):
    if not raw.startswith("---"):
        return None
    parts = raw.split("---", 2)
    if len(parts) < 3:
        return None
    try:
        return yaml.safe_load(parts[1]) or {}
    except Exception:
        return None


def collect_markdown_refs():
    """log_assets/markdown/*.md 의 front matter image + 본문 <img src>에서
    참조하는 이미지 파일명 집합."""
    refs = set()
    for fname in sorted(os.listdir(MD_DIR)):
        if not fname.endswith(".md"):
            continue
        path = os.path.join(MD_DIR, fname)
        with open(path, encoding="utf-8", errors="ignore") as fh:
            raw = fh.read()
        fm = load_front_matter(raw) or {}
        img = fm.get("image") or ""
        if img and not img.startswith(("http://", "https://")):
            refs.add(img.rsplit("/", 1)[-1])
        for m in RAW_IMG_RE.finditer(raw):
            src_m = SRC_RE.search(m.group(1))
            if not src_m:
                continue
            src = src_m.group(1)
            if not src.startswith(("http://", "https://", "//")):
                refs.add(src.rsplit("/", 1)[-1])
    return refs


def repo_wide_reference_exists(basename):
    """markdown 본문 밖(템플릿·include·layout·JSON-LD·다른 스크립트 등)에서
    이 파일명을 문자 그대로 참조하는 곳이 있는지 저장소 전체에서 확인한다."""
    try:
        result = subprocess.run(
            ["git", "grep", "-Fq", "--", basename],
            capture_output=True,
        )
        return result.returncode == 0
    except FileNotFoundError:
        return True  # git이 없으면 안전한 쪽으로: "참조됨"으로 간주해 건드리지 않음


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--quarantine", action="store_true",
        help="진짜 고아로 확인된 파일을 격리 폴더로 실제로 옮긴다 (기본은 리포트만 출력)",
    )
    args = parser.parse_args()

    if not os.path.isdir(MD_DIR) or not os.path.isdir(IMG_DIR):
        print("markdown/images 폴더가 없어 건너뜁니다")
        return 0

    md_refs = collect_markdown_refs()
    on_disk = sorted(os.listdir(IMG_DIR))

    candidates = [f for f in on_disk if f not in md_refs]
    print("이미지 {}개 중 블로그 글 본문에서 안 쓰이는 후보 {}개".format(len(on_disk), len(candidates)))

    protected, repo_referenced, true_orphans = [], [], []
    for f in candidates:
        if is_protected(f):
            protected.append(f)
        elif repo_wide_reference_exists(f):
            repo_referenced.append(f)
        else:
            true_orphans.append(f)

    if protected:
        print("\n이름 패턴으로 보호됨 (건드리지 않음): {}개".format(len(protected)))
        for f in protected:
            print("  - " + f)

    if repo_referenced:
        print("\n블로그 글 밖(템플릿/include/JSON-LD 등)에서 참조됨 -- 건드리지 않음: {}개".format(len(repo_referenced)))
        for f in repo_referenced:
            print("  - " + f)

    print("\n진짜 고아로 보이는 파일: {}개".format(len(true_orphans)))
    for f in true_orphans:
        print("  - " + f)

    if not true_orphans:
        return 0

    if not args.quarantine:
        print("\n--quarantine 옵션 없이 실행해서 리포트만 출력했습니다. 실제로 옮기려면 --quarantine으로 다시 실행하세요.")
        return 0

    today = datetime.date.today().isoformat()
    q_dir = "{}_quarantine_{}".format(IMG_DIR, today)
    os.makedirs(q_dir, exist_ok=True)
    for f in true_orphans:
        os.rename(os.path.join(IMG_DIR, f), os.path.join(q_dir, f))
    readme_path = os.path.join(q_dir, "README.md")
    with open(readme_path, "w", encoding="utf-8") as fh:
        fh.write(
            "# 격리된 이미지 ({})\n\n".format(today)
            + "이 폴더의 {}개 파일은 scripts/find_orphan_images.py가 저장소 전체".format(len(true_orphans))
            + "(블로그 글 본문 + 템플릿/include/JSON-LD/스크립트 등)에서 참조를 찾지\n"
            + "못한 이미지입니다. 이름 패턴 기반 보호 목록(로고·캐릭터·파비콘 등)에도\n"
            + "걸리지 않았습니다.\n\n"
            + "**삭제 전 확인 방법**: 각 파일명 앞부분으로 log_assets/markdown/에서\n"
            + "같은 글을 찾아 실제로 그 이미지가 필요 없는지 확인하세요. 필요 없는 게\n"
            + "확실해지면 이 폴더째로 지우면 됩니다.\n"
        )
    print("\n{}개 파일을 {}로 격리했습니다. 최종 삭제는 사람이 직접 확인 후 하세요.".format(len(true_orphans), q_dir))
    print("주의: 격리 직후 홈페이지 등 주요 페이지를 실제로 열어 육안으로 깨진 곳이 없는지 확인하세요.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
