import re
import glob
import sys

DRY_RUN = '--apply' not in sys.argv

files = sorted(glob.glob('log_assets/markdown/*.md'))

# Matches a leftover OG-card remnant:
#   [**TITLE**
#   (blank line)
#   description line (single line)
# A block is protected (left untouched) if the description line itself, or
# the very next non-blank line after it, contains a real markdown link
# "](" -- that indicates genuine functional content (a form link, a map
# link, a real embed) rather than pure scraped-preview cruft.
BLOCK_RE = re.compile(
    r'\[\*\*[^\n]*?\*\*[ \t]*\n[ \t]*\n(?![ \t]*\n)([^\n]*)\n'
)


def next_nonblank_line(content, pos):
    rest = content[pos:]
    for line in rest.split('\n'):
        if line.strip() == '':
            continue
        return line
    return ''


def find_removable_matches(content):
    removable = []
    for m in BLOCK_RE.finditer(content):
        desc_line = m.group(1)
        if '](' in desc_line:
            continue
        peek = next_nonblank_line(content, m.end())
        if '](' in peek:
            continue
        removable.append(m)
    return removable


def strip_remnants(content):
    removable = find_removable_matches(content)
    for m in reversed(removable):
        content = content[:m.start()] + content[m.end():]
    return content


total_removed = 0
files_changed = 0
report = []

for path in files:
    with open(path, encoding='utf-8') as f:
        content = f.read()

    matches = find_removable_matches(content)
    if matches:
        files_changed += 1
        total_removed += len(matches)
        report.append((path, len(matches), [m.group(0) for m in matches]))
        if not DRY_RUN:
            new_content = strip_remnants(content)
            with open(path, 'w', encoding='utf-8') as f:
                f.write(new_content)

print('files changed:', files_changed)
print('blocks removed:', total_removed)
print('mode:', 'DRY RUN (pass --apply to write)' if DRY_RUN else 'APPLIED')

out_path = 'strip_og_remnants_report.txt'
with open(out_path, 'w', encoding='utf-8') as f:
    for path, n, blocks in report:
        f.write(f'=== {path} ({n} block(s)) ===\n')
        for b in blocks:
            f.write(repr(b) + '\n')
        f.write('\n')
print('report written to', out_path)
