"""
본문 이미지(카카오 CDN 등 외부 URL)를 로컬(log_assets/images/)로 옮기고
<img src="...">를 로컬 경로로 바꾸는 스크립트.

배경: 이 글들은 CMS를 거치지 않고 브런치에서 통째로 옮겨올 때 원문의
이미지 URL을 그대로 복사해왔을 뿐이라, 브런치/카카오 서버가 사라지거나
정책을 바꾸면 이 사이트와 무관하게 사진이 깨진다. 커버 이미지는 이미
거의 다 로컬인데 본문 안 사진만 이 상태로 남아있었다.

먼저 확인한 것: 일부 글(134개)은 예전에 이미 다운로드까지는 돼서
log_assets/images/{base}_img_N.jpg 파일이 존재하는데, 본문의 <img src>는
여전히 외부 URL을 가리키고 있었다(연결만 안 됐던 상태). 이런 "고아"
로컬 파일은 캐시에 저장된 실제 크기(scripts/image_dimensions_cache.json)와
대조해서 진짜 같은 사진인지 확인 후 그대로 재사용하고, 없거나 안 맞으면
새로 다운로드한다.

번호가 어긋나면(로컬 파일 개수와 본문 외부 이미지 개수가 다르면) 그
파일은 기존 로컬 파일을 신뢰하지 않고 처음부터 새로 받는다 -- 부분적으로
꼬인 매핑을 억지로 맞추는 것보다 안전하다.
"""
import glob
import io
import json
import os
import re
import urllib.error
import urllib.request

from PIL import Image

MD_DIR = "log_assets/markdown"
IMAGES_DIR = "log_assets/images"
DIM_CACHE_PATH = "scripts/image_dimensions_cache.json"

RAW_IMG_RE = re.compile(r'<img\b([^>]*)>')
SRC_RE = re.compile(r'\bsrc="([^"]+)"')


def is_external(src):
    return src.startswith("//") or src.startswith("http://") or src.startswith("https://")


def normalize_url(src):
    return "https:" + src if src.startswith("//") else src


def guess_ext(url, data=None):
    m = re.search(r"fname=[^&]*\.(jpe?g|png|gif|webp)", url, re.I)
    if m:
        return m.group(1).lower().replace("jpeg", "jpg")
    if data:
        try:
            with Image.open(io.BytesIO(data)) as img:
                fmt = (img.format or "JPEG").lower()
                return {"jpeg": "jpg"}.get(fmt, fmt)
        except Exception:
            pass
    return "jpg"


def download(url):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=20) as resp:
            return resp.read()
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError) as e:
        print(f"    실패: {url} ({e})")
        return None


def find_orphans(base):
    files = glob.glob(os.path.join(IMAGES_DIR, f"{glob.escape(base)}_img_*.*"))

    def idx(f):
        m = re.search(r"_img_(\d+)\.", f)
        return int(m.group(1)) if m else 0

    return sorted(files, key=idx)


def process_file(path, dim_cache, stats):
    base = os.path.basename(path)[:-3]
    with open(path, encoding="utf-8") as f:
        c = f.read()
    if not c.startswith("---"):
        return
    parts = c.split("---", 2)
    if len(parts) < 3:
        return
    fm_text, body = parts[1], parts[2]

    ext_matches = []
    for m in RAW_IMG_RE.finditer(body):
        sm = SRC_RE.search(m.group(1))
        if sm and is_external(sm.group(1)):
            ext_matches.append((m, sm.group(1)))
    if not ext_matches:
        return

    orphans = find_orphans(base)
    use_orphans = len(orphans) == len(ext_matches)
    if use_orphans:
        for local, (_, src) in zip(orphans, ext_matches):
            cached = dim_cache.get(src)
            if cached:
                try:
                    with Image.open(local) as img:
                        if list(img.size) != cached:
                            use_orphans = False
                            break
                except Exception:
                    use_orphans = False
                    break

    replacements = {}  # src -> local web path
    if use_orphans:
        for local, (_, src) in zip(orphans, ext_matches):
            web_path = "/" + local.replace(os.sep, "/")
            replacements[src] = web_path
            stats["reused"] += 1
    else:
        print(f"  {base}: 새로 다운로드 ({len(ext_matches)}장)")
        for i, (_, src) in enumerate(ext_matches, start=1):
            if src in replacements:
                continue
            data = download(normalize_url(src))
            if not data:
                stats["failed"] += 1
                continue
            ext = guess_ext(src, data)
            local_path = os.path.join(IMAGES_DIR, f"{base}_img_{i}.{ext}")
            with open(local_path, "wb") as f:
                f.write(data)
            replacements[src] = "/" + local_path.replace(os.sep, "/")
            stats["downloaded"] += 1

    if not replacements:
        return

    def repl(m):
        attrs = m.group(1)
        sm = SRC_RE.search(attrs)
        if not sm or sm.group(1) not in replacements:
            return m.group(0)
        new_src = replacements[sm.group(1)]
        new_attrs = SRC_RE.sub(f'src="{new_src}"', attrs, count=1)
        return f"<img{new_attrs}>"

    new_body = RAW_IMG_RE.sub(repl, body)
    if new_body != body:
        with open(path, "w", encoding="utf-8") as f:
            f.write("---" + fm_text + "---" + new_body)
        stats["files_changed"] += 1


def main():
    with open(DIM_CACHE_PATH, encoding="utf-8") as f:
        dim_cache = json.load(f)

    stats = {"reused": 0, "downloaded": 0, "failed": 0, "files_changed": 0}
    for path in sorted(glob.glob(f"{MD_DIR}/*.md")):
        process_file(path, dim_cache, stats)

    print()
    print(f"파일 변경: {stats['files_changed']}개")
    print(f"기존 로컬 파일 재사용: {stats['reused']}장")
    print(f"새로 다운로드: {stats['downloaded']}장")
    print(f"실패: {stats['failed']}장")


if __name__ == "__main__":
    main()
