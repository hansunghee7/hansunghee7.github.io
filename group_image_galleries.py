import re
import glob
import sys

DRY_RUN = '--apply' not in sys.argv

IMG_LINE_RE = re.compile(r'^!\[([^\]]*)\]\(([^)]+)\)\s*$')
CATEGORY_RE = re.compile(r"^category:\s*['\"]?(.*?)['\"]?\s*$", re.MULTILINE)
WEBTOON_CATS = {'코치S', '잉크드인대 기획학과', '잉크드인대'}
MAX_PER_ROW = 3


def get_category(content):
    m = CATEGORY_RE.search(content)
    return m.group(1) if m else None


def find_groups(lines):
    """Return list of (start_idx, end_idx_exclusive, [(alt, url), ...]) for
    runs of >=2 consecutive image lines (allowing a single blank line between)."""
    groups = []
    i = 0
    while i < len(lines):
        m = IMG_LINE_RE.match(lines[i].strip())
        if m:
            start = i
            imgs = [(m.group(1), m.group(2))]
            k = i + 1
            while k < len(lines):
                if lines[k].strip() == '':
                    if k + 1 < len(lines):
                        m2 = IMG_LINE_RE.match(lines[k + 1].strip())
                        if m2:
                            imgs.append((m2.group(1), m2.group(2)))
                            k += 2
                            continue
                    break
                else:
                    m2 = IMG_LINE_RE.match(lines[k].strip())
                    if m2:
                        imgs.append((m2.group(1), m2.group(2)))
                        k += 1
                        continue
                    break
            end = k
            if len(imgs) >= 2:
                groups.append((start, end, imgs))
            i = end if end > i else i + 1
        else:
            i += 1
    return groups


def chunk(imgs, size):
    return [imgs[i:i + size] for i in range(0, len(imgs), size)]


def build_gallery_html(imgs):
    rows = chunk(imgs, MAX_PER_ROW)
    blocks = []
    for row in rows:
        inner = '\n'.join(
            f'  <img src="{url}" alt="{alt}">' for alt, url in row
        )
        blocks.append(f'<div class="img-gallery">\n{inner}\n</div>')
    return '\n\n'.join(blocks)


total_files = 0
total_groups = 0
samples = []

for path in sorted(glob.glob('log_assets/markdown/*.md')):
    with open(path, encoding='utf-8') as f:
        content = f.read()

    cat = get_category(content)
    if cat in WEBTOON_CATS:
        continue

    lines = content.split('\n')
    groups = find_groups(lines)
    if not groups:
        continue

    total_files += 1
    total_groups += len(groups)

    # rebuild file from the back so earlier indices stay valid
    for start, end, imgs in reversed(groups):
        replacement = build_gallery_html(imgs).split('\n')
        lines[start:end] = replacement

    new_content = '\n'.join(lines)
    if len(samples) < 5:
        samples.append((path, len(groups)))

    if not DRY_RUN:
        with open(path, 'w', encoding='utf-8') as f:
            f.write(new_content)

print('files affected:', total_files)
print('groups converted:', total_groups)
print('mode:', 'DRY RUN (pass --apply to write)' if DRY_RUN else 'APPLIED')
print('samples:', samples)
