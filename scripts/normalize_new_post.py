"""
CMS(Decap CMS)로 새로 커밋된 log_assets/markdown/*.md 파일을 기존 글과 같은
형태로 맞춰주는 스크립트.

CMS는 제목/카테고리/날짜/본문만 채운 "날것" 파일을 커밋한다. 여기서 채워야
하는 것 두 가지:
  1. 파일명 앞자리 3자리 순번 (001_, 002_, ... 화별 정렬 등 여러 스크립트의
     전제 조건이라 반드시 있어야 함)
  2. date_string ("Aug 12. 2026" 형식) -- date 필드에서 자동 파생

(예전엔 CAT_LINK_SCRIPT 블록도 여기서 넣었다 -- 커버 위 카테고리 알약을
누르면 /log.html?cat=...로 이동하게 하는 스크립트였는데, 그 알약 자체가
GNB를 새로 만들면서 진짜 <a href> 링크(.log-nav-category)로 대체돼
".cover-category-pill"이라는 타겟이 사라졌다. 그 뒤로 이 스크립트는
querySelector가 항상 null을 반환해 아무 일도 안 하는 채로 글마다 20줄씩
찍히고 있었다 -- 594개 파일에서 일괄 제거했고, 이제 새 글에도 안 넣는다.

CATEGORY_NAV_START/END 마커도 마찬가지 이유로 더 이상 안 넣는다 --
예전엔 sync_all.py가 이 마커 사이에 이전글/다음글 HTML을 직접 써넣었는데,
지금은 prev_url/prev_title/next_url/next_title을 front matter에만 쓰고
렌더링은 _includes/post_nav.html이 담당해서 본문에 아무 것도 안 남는다.)

핵심 안전장치: 이미 이 두 가지가 갖춰진 파일은 "단 1바이트도" 건드리지
않는다. YAML을 파싱해서 다시 dump하는 방식은 따옴표 스타일이 달라져
필요 없는 전체 재작성을 일으키므로 쓰지 않는다 -- front matter/본문 원문
문자열에 필요한 삽입만 하고, 그 외에는 원본 텍스트를 그대로 이어붙인다.
"""
import os
import re
import sys
import yaml
from datetime import datetime

MD_DIR = "log_assets/markdown"
IMAGES_DIR = "log_assets/images"
ID_RE = re.compile(r"^(\d{3})_")
INVALID_FILENAME_CHARS = re.compile(r'[\\/:*?"<>|]')

MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def format_date_string(date_val):
    if isinstance(date_val, str):
        try:
            date_val = datetime.strptime(date_val[:10], "%Y-%m-%d").date()
        except ValueError:
            return None
    if not hasattr(date_val, "month"):
        return None
    return f"{MONTHS[date_val.month - 1]} {date_val.day}. {date_val.year}"


def next_available_id(used_ids):
    n = (max(used_ids) if used_ids else 0) + 1
    used_ids.add(n)
    return n


def process_one(path, used_ids):
    """returns (changed: bool, new_path_or_None)"""
    with open(path, "r", encoding="utf-8", errors="ignore") as fh:
        raw = fh.read()

    if not raw.startswith("---"):
        return False, None
    parts = raw.split("---", 2)
    if len(parts) < 3:
        return False, None

    fm_text, body = parts[1], parts[2]
    try:
        fm = yaml.safe_load(fm_text) or {}
    except Exception:
        return False, None

    # 비공개(published: false) 글은 실제로 빌드되지 않는 초안이라 sync_all.py도
    # 이전글/다음글 대상에서 제외한다. 여기서도 손대지 않는다 -- 어차피 안 쓰일
    # 카테고리 링크 스크립트를 넣어봐야 불필요한 변경만 생긴다.
    if fm.get("published") is False:
        return False, None

    changed = False
    new_fm_text = fm_text
    new_body = body

    # 1) date_string 자동 파생 -- 원문 front matter 텍스트에 한 줄만 삽입
    if not fm.get("date_string") and fm.get("date"):
        ds = format_date_string(fm["date"])
        if ds:
            line = f"date_string: '{ds}'"
            if re.search(r"^date:.*$", new_fm_text, re.M):
                new_fm_text = re.sub(r"(^date:.*$)", r"\1\n" + line, new_fm_text, count=1, flags=re.M)
            else:
                new_fm_text = new_fm_text.rstrip("\n") + "\n" + line + "\n"
            changed = True

    fname = os.path.basename(path)
    target_fname = fname
    if not ID_RE.match(fname):
        new_id = next_available_id(used_ids)
        title = fm.get("title", fname.rsplit(".", 1)[0])
        safe_title = INVALID_FILENAME_CHARS.sub("", title).strip()
        target_fname = f"{new_id:03d}_{safe_title}.md"
        if os.path.exists(os.path.join(os.path.dirname(path), target_fname)):
            target_fname = fname  # 충돌 시 이번 실행에서는 리네임 보류
        else:
            changed = True

    if not changed:
        return False, None

    new_raw = "---" + new_fm_text + "---" + new_body
    target_path = os.path.join(os.path.dirname(path), target_fname)
    with open(target_path, "w", encoding="utf-8") as fh:
        fh.write(new_raw)
    if target_path != path:
        os.remove(path)
    return True, (target_fname if target_fname != fname else None)


def process():
    if not os.path.isdir(MD_DIR):
        print(f"{MD_DIR} not found, nothing to do")
        return 0

    fnames = sorted(f for f in os.listdir(MD_DIR) if f.endswith(".md"))
    used_ids = set()
    for f in fnames:
        m = ID_RE.match(f)
        if m:
            used_ids.add(int(m.group(1)))
    # 이미지 폴더에는 대응하는 글이 없는 번호가 남아있을 수 있다(예전 브런치
    # 동기화 과정에서 생긴 고아 이미지). 새 글 번호가 그런 이미지 번호와
    # 겹치면 fix_thumb_mapping.py의 "동일 ID" 폴백이 엉뚱한 이미지를
    # 새 글에 붙일 수 있으므로, 이미지 쪽 번호도 같이 피해서 고른다.
    if os.path.isdir(IMAGES_DIR):
        for f in os.listdir(IMAGES_DIR):
            m = ID_RE.match(f)
            if m:
                used_ids.add(int(m.group(1)))

    changed_count = 0
    renamed = []
    for fname in fnames:
        path = os.path.join(MD_DIR, fname)
        changed, new_name = process_one(path, used_ids)
        if changed:
            changed_count += 1
            if new_name:
                renamed.append((fname, new_name))

    if renamed:
        print(f"renamed {len(renamed)} file(s):")
        for old, new in renamed:
            print(f"  {old} -> {new}")
    print(f"changed {changed_count} file(s) of {len(fnames)} total")
    return 0


if __name__ == "__main__":
    sys.exit(process())
