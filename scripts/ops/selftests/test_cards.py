import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path


def main():
    script = Path(__file__).resolve().parent.parent / "card_docs_check.py"
    with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as temp:
        repo = Path(temp) / "repo"
        repo.mkdir()
        subprocess.run(["git", "init", str(repo)], check=True, capture_output=True)
        subprocess.run(
            ["git", "-C", str(repo), "config", "user.email", "tester-local"],
            check=True,
        )
        subprocess.run(
            ["git", "-C", str(repo), "config", "user.name", "Test"], check=True
        )
        docs = repo / "docs"
        docs.mkdir()
        (docs / "a.md").write_text("test\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(repo), "add", "docs/a.md"], check=True)
        subprocess.run(["git", "-C", str(repo), "commit", "-m", "add docs"], check=True, capture_output=True)

        cards = [
            {"id": "1", "title": "", "do": "Read docs/a.md"},
            {"id": "2", "title": "", "do": "Read docs/zzz.md"},
            {"id": "3", "title": "No reference", "do": ""},
        ]
        cards_file = Path(temp) / "cards.json"
        cards_file.write_text(json.dumps(cards), encoding="utf-8")
        run = subprocess.run(
            [sys.executable, str(script), str(cards_file), str(repo)],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        actual = json.loads(run.stdout)
        expected = {
            "checked": 2,
            "missing": [{"card_id": "2", "path": "docs/zzz.md"}],
            "cards_without_refs": 1,
        }
        if actual != expected:
            raise AssertionError("expected %r, got %r" % (expected, actual))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print("TEST FAIL: %s" % exc)
        raise SystemExit(1)
    print("TEST PASS")
