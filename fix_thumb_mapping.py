import os
import re
import urllib.parse
import yaml
import json
from collections import defaultdict


def pure_text(t):
    return re.sub(r'[^가-힣a-zA-Z0-9]', '', t)


images = os.listdir('log_assets/images')
cover_by_id = defaultdict(list)   # id -> [(title_part, filename)]
cover_by_pure = defaultdict(list)  # pure_text(title) -> [filename]
for f in images:
    m = re.match(r'^(\d{3})_(.*)_cover\.jpg$', f)
    if m:
        pid, title_part = m.group(1), m.group(2)
        cover_by_id[pid].append((title_part, f))
        cover_by_pure[pure_text(title_part)].append(f)

md_files = [f for f in os.listdir('log_assets/markdown') if f.endswith('.md')]

# base_name -> pure_text(title_part), used for sibling disambiguation
md_pure_by_base = {}
pure_to_bases = defaultdict(list)
for fname in md_files:
    base = fname[:-3]
    m = re.match(r'^(\d{3})_(.*)$', base)
    title_part = m.group(2) if m else base
    p = pure_text(title_part)
    md_pure_by_base[base] = p
    pure_to_bases[p].append(base)


def score_candidate(target_pure, cand_pure):
    if cand_pure == target_pure:
        return 9999
    return len(os.path.commonprefix([target_pure, cand_pure]))


def resolve_cover(base):
    m = re.match(r'^(\d{3})_(.*)$', base)
    if not m:
        return None
    pid, title_part = m.group(1), m.group(2)
    target = pure_text(title_part)

    # 1) same-ID candidates
    same_id = cover_by_id.get(pid, [])
    if same_id:
        if len(same_id) == 1:
            cand_pure = pure_text(same_id[0][0])
            # accept only if it's a reasonable match, else fall through to global search
            if cand_pure == target or (len(target) > 0 and score_candidate(target, cand_pure) >= max(4, len(target) * 0.6)):
                return same_id[0][1]
        else:
            best, best_score = None, -1
            for cand_title, fname in same_id:
                s = score_candidate(target, pure_text(cand_title))
                if s > best_score:
                    best_score, best = s, fname
            if best_score == 9999 or best_score >= max(4, len(target) * 0.6):
                return best

    # 2) global pure-text search
    globals_ = cover_by_pure.get(target, [])
    if len(globals_) == 1:
        return globals_[0]
    if len(globals_) > 1:
        # prefer a candidate whose id also belongs to a sibling md file sharing this exact title
        sibling_ids = set(re.match(r'^(\d{3})_', b).group(1) for b in pure_to_bases.get(target, []))
        for f in globals_:
            fid = re.match(r'^(\d{3})_', f).group(1)
            if fid in sibling_ids:
                return f
        return sorted(globals_)[0]

    # 3) fall back to same-ID single candidate even if match was weak, better than nothing
    if same_id:
        return same_id[0][1]

    return None


mapping = {}
unmatched = []
for fname in md_files:
    base = fname[:-3]
    cover = resolve_cover(base)
    if cover:
        mapping[base] = cover
    else:
        unmatched.append(base)

print('mapping built for', len(mapping), 'of', len(md_files), 'posts; unmatched:', len(unmatched))
for u in unmatched[:20]:
    print('  unmatched:', u)

# --- Patch log.html card thumbnails, matched by exact href base name ---
with open('log.html', encoding='utf-8') as f:
    content = f.read()

card_re = re.compile(
    r'<a href="/log_assets/markdown/([^"]+)\.html" class="card-item"([^>]*)>'
    r'<div class="card-thumb-wrap"><div class="card-thumb" style="background-image: url\(\'([^\']*)\'\);"></div></div>'
)

total = 0
changed = 0
mismatches = []


def repl(m):
    global total, changed
    encoded_base, attrs, old_url = m.group(1), m.group(2), m.group(3)
    base = urllib.parse.unquote(encoded_base)
    total += 1
    cover = mapping.get(base)
    if not cover:
        mismatches.append(base)
        return m.group(0)
    new_url = '/log_assets/images/' + urllib.parse.quote(cover)
    if new_url != old_url:
        changed += 1
    return (
        '<a href="/log_assets/markdown/' + encoded_base + '.html" class="card-item"' + attrs + '>'
        '<div class="card-thumb-wrap"><div class="card-thumb" style="background-image: url(\'' + new_url + '\');"></div></div>'
    )


new_content = card_re.sub(repl, content)
print('cards processed:', total, 'changed vs previous:', changed, 'mismatches:', len(mismatches))

with open('log.html', 'w', encoding='utf-8') as f:
    f.write(new_content)

print('log.html updated')

# --- Write posts.json using the same corrected mapping ---
MD_DIR = 'log_assets/markdown'
OUT_PATH = 'assets/data/posts.json'

posts = []
for fname in md_files:
    base = fname[:-3]
    idm = re.match(r'^(\d+)_', fname)
    if not idm:
        continue
    pid = int(idm.group(1))

    with open(os.path.join(MD_DIR, fname), encoding='utf-8', errors='ignore') as f:
        fcontent = f.read()

    frontmatter = {}
    if fcontent.startswith('---'):
        parts = fcontent.split('---', 2)
        if len(parts) >= 3:
            try:
                frontmatter = yaml.safe_load(parts[1]) or {}
            except Exception:
                pass

    category = (frontmatter.get('category') or '').strip()
    title = frontmatter.get('title', base)
    date_string = frontmatter.get('date_string', '')

    url = '/log_assets/markdown/' + urllib.parse.quote(base) + '.html'

    cover = mapping.get(base)
    if cover:
        image = '/log_assets/images/' + urllib.parse.quote(cover)
    else:
        image = '/log_assets/images/logo_white.png'

    posts.append({
        'id': pid,
        'title': title,
        'category': category,
        'date': date_string,
        'url': url,
        'image': image,
    })

posts.sort(key=lambda p: p['id'])

os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
with open(OUT_PATH, 'w', encoding='utf-8') as f:
    json.dump(posts, f, ensure_ascii=False, indent=0)

print('wrote', len(posts), 'posts to', OUT_PATH)

# expose mapping for the homepage-widget patch step
with open('.mapping_debug.json', 'w', encoding='utf-8') as f:
    json.dump(mapping, f, ensure_ascii=False)
