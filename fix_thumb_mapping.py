import os
import re
import urllib.parse
import yaml
import json
from collections import defaultdict


def pure_text(t):
    return re.sub(r'[^가-힣a-zA-Z0-9]', '', t)


def _terms(raw):
    out = set()
    for t in str(raw or '').split(','):
        t = t.strip().lower()
        if t:
            out.add(t)
    return out


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


def resolve_cover(base):
    m = re.match(r'^(\d{3})_(.*)$', base)
    if not m:
        return None
    pid, title_part = m.group(1), m.group(2)
    target = pure_text(title_part)

    # 1) global EXACT pure-text match is the only trustworthy signal -- a
    # naive same-ID or prefix-based fuzzy match is unsafe here because many
    # posts share a long common title prefix (e.g. "내가 나를 기획한다면 ...편")
    # and only differ in a short suffix, which fools prefix-similarity scoring.
    globals_ = cover_by_pure.get(target, [])
    if len(globals_) == 1:
        return globals_[0]
    if len(globals_) > 1:
        # genuine duplicate title across IDs (e.g. a repeated post): prefer
        # the candidate whose id also belongs to a sibling md file sharing
        # this exact title, else the numerically closest id, else lowest.
        sibling_ids = set(re.match(r'^(\d{3})_', b).group(1) for b in pure_to_bases.get(target, []))
        for f in globals_:
            fid = re.match(r'^(\d{3})_', f).group(1)
            if fid in sibling_ids:
                return f
        def dist(f):
            fid = re.match(r'^(\d{3})_', f).group(1)
            return abs(int(fid) - int(pid))
        return sorted(globals_, key=dist)[0]

    # 2) no exact match anywhere: fall back to whatever exists under the
    # same numeric id, purely as a last resort (better than the default logo).
    same_id = cover_by_id.get(pid, [])
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

# --- front matter의 image가 최우선 (CMS가 쓰는 값이 곧 정답) ---
# 위 mapping은 브런치에서 긁어온 이미지 파일명에 글 제목이 들어있다는 전제로
# "제목이 비슷한 이미지"를 추측하는 로직이다. 이제 모든 글의 front matter에
# image 경로가 명시돼 있으므로 그쪽이 우선이어야 한다. 안 그러면 CMS에서
# 커버 이미지를 바꿔도 이 스크립트가 옛 추측값으로 되돌려버린다(실제로
# 이미지 파일명을 바꾸자 엉뚱한 글의 이미지가 붙는 사고가 났다).
def _quote_path(p):
    return '/'.join(urllib.parse.quote(seg) if seg else seg for seg in p.split('/'))


fm_image_by_base = {}
for _fname in md_files:
    with open(os.path.join('log_assets/markdown', _fname), encoding='utf-8', errors='ignore') as _f:
        _raw = _f.read()
    if not _raw.startswith('---'):
        continue
    _parts = _raw.split('---', 2)
    if len(_parts) < 3:
        continue
    try:
        _fm = yaml.safe_load(_parts[1]) or {}
    except Exception:
        continue
    _img = _fm.get('image')
    if _img:
        fm_image_by_base[_fname[:-3]] = _img


def resolve_image_url(base):
    """카드/posts.json에 쓸 최종 이미지 URL. front matter > 제목추측 > 기본로고."""
    raw = fm_image_by_base.get(base)
    if raw:
        if raw.startswith('http://') or raw.startswith('https://'):
            return raw
        return _quote_path(raw)
    cover = mapping.get(base)
    if cover:
        return '/log_assets/images/' + urllib.parse.quote(cover)
    return None


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
    new_url = resolve_image_url(base)
    if not new_url:
        mismatches.append(base)
        return m.group(0)
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

    if frontmatter.get('published') is False:
        continue

    category = (frontmatter.get('category') or '').strip()
    title = frontmatter.get('title', base)
    date_string = frontmatter.get('date_string', '')

    url = '/log_assets/markdown/' + urllib.parse.quote(base) + '.html'

    image = resolve_image_url(base) or '/log_assets/images/logo_white.png'

    posts.append({
        'id': pid,
        'title': title,
        'category': category,
        'date': date_string,
        'url': url,
        'image': image,
        '_kw': _terms(frontmatter.get('keywords')),
        '_about': _terms(frontmatter.get('about')),
    })

posts.sort(key=lambda p: p['id'])

# --- 연관글: "같은 카테고리 + 랜덤" 대신 keywords/about 겹침으로 실제
# 주제가 가까운 글을 고른다. keywords 0.7 : about 0.3으로 가중치를 둔다
# -- about은 "코치S 웹툰, 스타트업 코칭 사례"처럼 같은 시리즈/카테고리
# 안에서 거의 동일한 문구를 재사용해 그 자체로는 변별력이 약하고, keywords가
# 글마다 훨씬 구체적이고 고유해서 실제 겹침 여부의 신호로 더 믿을 만하다.
# 겹치는 키워드가 없으면 같은 카테고리로 채워 넣어 빈 추천을 막는다.
def _jaccard(a, b):
    if not a or not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union else 0.0


def _similarity(p, q):
    # 0.6/0.4로 keywords를 조금 더 신뢰하되(about은 시리즈 안에서 거의
    # 동일 문구가 반복돼 변별력이 약함), 지나치게 keywords 쪽으로 쏠리면
    # 짧은 키워드 목록에서 흔한 단어 하나만 겹쳐도 점수가 튀는 역효과가
    # 있어(직접 확인함) 0.7/0.3까지는 가지 않았다. 최적 비율은 데이터
    # 없이는 확정할 수 없는 영역이라, 위에서 붙인 클릭 추적이 쌓이면
    # 그 결과로 다시 조정할 것.
    return 0.6 * _jaccard(p['_kw'], q['_kw']) + 0.4 * _jaccard(p['_about'], q['_about'])


posts_by_id = {p['id']: p for p in posts}

for p in posts:
    scored = []
    for q in posts:
        if q['id'] == p['id']:
            continue
        score = _similarity(p, q)
        if p['category'] and q['category'] == p['category']:
            score += 0.05  # 동점일 때 같은 카테고리를 살짝 우대
        scored.append((score, q['id']))
    scored.sort(key=lambda x: (-x[0], x[1]))
    related = [qid for score, qid in scored if score > 0][:4]
    if len(related) < 4:
        # 겹치는 키워드가 부족해 4개를 못 채우면, 0점짜리 중에서도 이미
        # 점수순으로 정렬된 scored에서 같은 카테고리인 것부터 채운다
        # (예전엔 파일 순서 그대로라 사실상 무작위 채움과 다를 게 없었다).
        fallback = [qid for score, qid in scored
                    if qid not in related and posts_by_id[qid]['category'] == p['category']]
        related += fallback[:4 - len(related)]
    p['related'] = related

for p in posts:
    del p['_kw']
    del p['_about']

os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
with open(OUT_PATH, 'w', encoding='utf-8') as f:
    json.dump(posts, f, ensure_ascii=False, indent=0)

print('wrote', len(posts), 'posts to', OUT_PATH)

# expose mapping for the homepage-widget patch step
with open('.mapping_debug.json', 'w', encoding='utf-8') as f:
    json.dump(mapping, f, ensure_ascii=False)
