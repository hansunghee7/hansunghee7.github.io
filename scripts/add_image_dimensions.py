"""
본문 이미지(<img>, markdown ![]())에 width/height 속성을 채워 넣는 스크립트.

왜 필요한가: width/height가 없으면 브라우저가 이미지를 다 받기 전까지 실제
크기를 몰라서, 이미지가 로드되는 순간 그 아래 본문이 밀리는 레이아웃
시프트(CLS)가 생긴다. width/height 속성이 있으면(반응형 CSS로 실제
렌더링 크기는 달라져도) 브라우저가 그 비율로 자리를 미리 확보해서 이
문제가 없어진다.

동작:
  1. 모든 마크다운 파일 본문에서 이미지 src를 모은다.
  2. 로컬 이미지는 파일에서 바로 크기를 읽는다.
  3. 외부(카카오 CDN) 이미지는 다운로드해서 크기만 읽고 저장은 안 한다
     (로컬로 옮기는 건 별도 프로젝트로 미뤄둔 상태 -- 여기서는 CLS만 고침).
     결과는 scripts/image_dimensions_cache.json에 캐싱해서 재실행 시
     이미 아는 이미지는 다시 안 받는다.
  4. width/height를 이미 가진 <img>는 건드리지 않는다(멱등성).
  5. 아직 markdown ![]() 문법인 이미지(연재 웹툰 카테고리)는 raw HTML
     <img>로 바꾸면서 width/height를 넣는다. loading="lazy"는 안 붙인다
     -- 그건 별도 이유(스와이프 뷰어 우선순위 로딩과의 충돌 우려)로
     웹툰 카테고리에서 의도적으로 뺀 것이라 여기서 되살리지 않는다.

의존성: Pillow (pip install pillow) -- 이미지 바이트에서 크기를 읽는 데만 쓴다.
"""
import concurrent.futures
import glob
import html
import io
import json
import os
import re
import urllib.error
import urllib.request

from PIL import Image

MD_DIR = "log_assets/markdown"
CACHE_PATH = "scripts/image_dimensions_cache.json"

RAW_IMG_RE = re.compile(r'<img\b([^>]*)>')
MD_IMG_RE = re.compile(r'!\[([^\]]*)\]\(([^)\s]+)\)')
SRC_RE = re.compile(r'\bsrc="([^"]+)"')
ALT_RE = re.compile(r'\balt="([^"]*)"')
HAS_WIDTH_RE = re.compile(r'\bwidth="')


def collect_srcs():
    srcs = set()
    for path in glob.glob(f"{MD_DIR}/*.md"):
        with open(path, encoding="utf-8") as f:
            c = f.read()
        body = c.split("---", 2)[-1] if c.startswith("---") else c
        for m in RAW_IMG_RE.finditer(body):
            sm = SRC_RE.search(m.group(1))
            if sm:
                srcs.add(sm.group(1))
        for m in MD_IMG_RE.finditer(body):
            srcs.add(m.group(2))
    return srcs


def normalize_url(src):
    if src.startswith("//"):
        return "https:" + src
    return src


def fetch_dimensions(src):
    if src.startswith("/") and not src.startswith("//"):
        local_path = src.lstrip("/")
        try:
            with Image.open(local_path) as img:
                return list(img.size)
        except Exception as e:
            print(f"  경고: 로컬 이미지 크기 읽기 실패({local_path}): {e}")
            return None

    url = normalize_url(src)
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = resp.read()
        with Image.open(io.BytesIO(data)) as img:
            return list(img.size)
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError, Exception) as e:
        print(f"  경고: 외부 이미지 크기 읽기 실패({src}): {e}")
        return None


def build_cache(srcs, cache):
    todo = [s for s in srcs if s not in cache]
    print(f"캐시에 없는 이미지 {len(todo)}개, 가져오는 중...")
    done = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as ex:
        futures = {ex.submit(fetch_dimensions, s): s for s in todo}
        for fut in concurrent.futures.as_completed(futures):
            src = futures[fut]
            dims = fut.result()
            cache[src] = dims  # None이면 실패로 기록, 다음 실행에서 재시도 안 함
            done += 1
            if done % 50 == 0:
                print(f"  {done}/{len(todo)}")
                with open(CACHE_PATH, "w", encoding="utf-8") as f:
                    json.dump(cache, f, ensure_ascii=False, indent=0)
    with open(CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=0)
    print(f"  완료: {done}/{len(todo)}")


def apply_dimensions_to_body(body, cache):
    def repl_raw(m):
        attrs = m.group(1)
        if HAS_WIDTH_RE.search(attrs):
            return m.group(0)
        sm = SRC_RE.search(attrs)
        if not sm:
            return m.group(0)
        dims = cache.get(sm.group(1))
        if not dims:
            return m.group(0)
        w, h = dims
        return f'<img width="{w}" height="{h}"{attrs}>'

    body = RAW_IMG_RE.sub(repl_raw, body)

    def repl_md(m):
        alt, src = m.group(1), m.group(2)
        dims = cache.get(src)
        if not dims:
            return m.group(0)
        w, h = dims
        esc_alt = html.escape(alt, quote=True)
        return f'<img width="{w}" height="{h}" src="{src}" alt="{esc_alt}">'

    body = MD_IMG_RE.sub(repl_md, body)
    return body


def main():
    srcs = collect_srcs()
    print(f"본문에서 발견한 이미지 src: {len(srcs)}개")

    cache = {}
    if os.path.exists(CACHE_PATH):
        with open(CACHE_PATH, encoding="utf-8") as f:
            cache = json.load(f)

    build_cache(srcs, cache)

    changed_files = 0
    for path in glob.glob(f"{MD_DIR}/*.md"):
        with open(path, encoding="utf-8") as f:
            c = f.read()
        if not c.startswith("---"):
            continue
        parts = c.split("---", 2)
        if len(parts) < 3:
            continue
        fm_text, body = parts[1], parts[2]
        new_body = apply_dimensions_to_body(body, cache)
        if new_body != body:
            with open(path, "w", encoding="utf-8") as f:
                f.write("---" + fm_text + "---" + new_body)
            changed_files += 1

    print(f"width/height 추가된 파일: {changed_files}개")
    ok = sum(1 for v in cache.values() if v)
    fail = sum(1 for v in cache.values() if not v)
    print(f"캐시 상태: 성공 {ok}개, 실패(깨진 링크 등) {fail}개")


if __name__ == "__main__":
    main()
