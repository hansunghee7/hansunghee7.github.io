import datetime
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path


def classify(path):
    lowered = path.lower()
    if "tstate" in lowered or ".jsonl" in lowered or "_state" in lowered or ".log" in lowered or "h_send/" in lowered:
        return "runtime"
    if lowered.startswith("docs/") and lowered.endswith(".md"):
        return "doc"
    return "unknown"


def main():
    if len(sys.argv) != 3:
        print("usage: dirty_snapshot.py <repository> <archive>")
        return 2
    repository = Path(sys.argv[1]).resolve()
    archive = Path(sys.argv[2]).resolve()
    pattern_path = Path(__file__).resolve().parent / "patterns.txt"
    try:
        patterns = [re.compile(line) for line in pattern_path.read_text(encoding="ascii").splitlines() if line]
    except (OSError, re.error) as exc:
        print("cannot load patterns: " + str(exc))
        return 2
    result = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=all"],
        cwd=str(repository), capture_output=True, text=True, encoding="utf-8", errors="surrogateescape",
    )
    if result.returncode:
        print("git status failed: " + result.stderr.strip())
        return 2
    date = datetime.date.today().isoformat()
    destination = archive / date
    entries = []
    for line in result.stdout.splitlines():
        if len(line) < 4:
            continue
        status, raw_path = line[:2], line[3:]
        if raw_path.startswith('"'):
            try:
                raw_path = json.loads(raw_path)
            except json.JSONDecodeError:
                pass
        relative = raw_path.replace("\\", "/")
        source = repository / Path(raw_path)
        category = classify(relative)
        if not source.is_file():
            action = "missing"
        else:
            content = source.read_bytes().decode("latin-1")
            if any(pattern.search(content) for pattern in patterns):
                action = "blocked"
            else:
                target = destination / Path(raw_path)
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)
                action = "copied"
        entries.append({"path": relative, "status": status, "class": category, "action": action})
    counts = {
        "files": len(entries),
        "copied": sum(item["action"] == "copied" for item in entries),
        "blocked": sum(item["action"] == "blocked" for item in entries),
        "missing": sum(item["action"] == "missing" for item in entries),
    }
    destination.mkdir(parents=True, exist_ok=True)
    (destination / "dirty_report.json").write_text(
        json.dumps({"files": entries, "counts": counts}, ensure_ascii=True, indent=2) + "\n",
        encoding="ascii",
    )
    print(json.dumps(counts, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
