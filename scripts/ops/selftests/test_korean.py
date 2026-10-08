# regression: Korean doc file names must be matched (git quotes non-ASCII paths unless core.quotepath=false)
import json, os, subprocess, sys, tempfile, shutil, stat
here = os.path.dirname(os.path.abspath(__file__))
d = tempfile.mkdtemp()
try:
    os.makedirs(os.path.join(d, "docs"))
    open(os.path.join(d, "docs", "\uac00\ub098.md"), "w", encoding="utf-8").write("x")
    for c in (["init", "-q"], ["add", "-A"], ["-c", "user.name=t", "-c", "user.email=t@l", "commit", "-qm", "i"]):
        subprocess.run(["git", "-C", d] + c, check=True, capture_output=True)
    cards = os.path.join(d, "c.json")
    json.dump([{"id": "k", "title": "t", "do": "docs/\uac00\ub098.md \ucc38\uc870"}], open(cards, "w", encoding="utf-8"))
    out = subprocess.run([sys.executable, os.path.join(os.path.dirname(here), "card_docs_check.py"), cards, d], capture_output=True, text=True, encoding="utf-8").stdout
    r = json.loads(out)
    print("TEST PASS" if r["checked"] == 1 and not r["missing"] else "TEST FAIL(korean path flagged missing)")
finally:
    shutil.rmtree(d, onerror=lambda f, p, e: (os.chmod(p, stat.S_IWRITE), f(p)))
