import json
import re
import subprocess
import sys
from pathlib import Path


PATH_RE = re.compile(r"docs/(?:[^\s\"'`<>()[\]{}]+?\.md)")


def main():
    if len(sys.argv) != 3:
        raise SystemExit("usage: card_docs_check.py <cards.json> <repo_dir>")

    cards_path = Path(sys.argv[1])
    repo_dir = Path(sys.argv[2])
    with cards_path.open("r", encoding="utf-8") as stream:
        cards = json.load(stream)

    result = subprocess.run(
        ["git", "-C", str(repo_dir), "-c", "core.quotepath=false", "ls-files", "-z"],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    tracked = set(x for x in result.stdout.split(chr(0)) if x)

    missing = []
    checked = 0
    cards_without_refs = 0
    for card in cards:
        refs = []
        for field in ("title", "do"):
            refs.extend(PATH_RE.findall(card.get(field, "")))
        if not refs:
            cards_without_refs += 1
        for path in refs:
            checked += 1
            if path not in tracked:
                missing.append({"card_id": card["id"], "path": path})

    print(json.dumps({
        "checked": checked,
        "missing": missing,
        "cards_without_refs": cards_without_refs,
    }, ensure_ascii=True))


if __name__ == "__main__":
    main()
