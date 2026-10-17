"""jitu_po.py 개선 반영 안내(fb ship·notified·notice-draft·due) 시험(2026-10-17 노트).

임시 장부 폴더를 JITU_PO_DIR로 주입해 실제 C:/work/_ops/jitu_po는 건드리지 않는다.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

TOOL = Path(__file__).parent / "jitu_po.py"


def run(tmp, *args, ok=True):
    env = dict(os.environ, JITU_PO_DIR=str(tmp), JITU_PO_TODAY="2026-10-17", PYTHONIOENCODING="utf-8")
    env.pop("JITU_PO_KPI_GATE", None)
    p = subprocess.run([sys.executable, "-X", "utf8", str(TOOL), *args], capture_output=True, text=True, stdin=subprocess.DEVNULL,
                       encoding="utf-8", env=env)
    if ok:
        assert p.returncode == 0, p.stderr
    return p


def rows(tmp):
    return [json.loads(x) for x in (Path(tmp) / "feedback.jsonl").read_text(encoding="utf-8").splitlines() if x.strip()]


def ship(tmp, fid="F-1"):
    return run(tmp, "fb", "ship", fid, "--pr", "123", "--pr", "124", "--shipped", "2026-10-16",
               "--notice-what", "검색 결과가 없을 때 쓸 수 있는 문서 목록을 보여 줘요",
               "--notice-before", "https://example.com/before.png", "--notice-after", "https://example.com/after.png",
               "--notice-next", "문서 이름을 몰라도 낱말로 찾아보세요")


def test_add_customer_saved(tmp_path):
    run(tmp_path, "fb", "add", "--source", "면담", "--text", "로딩 문구를 못 찾았어요", "--customer", "고객1")
    assert rows(tmp_path)[0]["customer"] == "고객1"
    run(tmp_path, "fb", "add", "--source", "면담", "--text", "x", "--customer", "내부")
    run(tmp_path, "fb", "add", "--source", "면담", "--text", "y", "--customer", "신규가입자")
    assert [r["customer"] for r in rows(tmp_path)] == ["고객1", "내부", "신규가입자"]


def test_add_rejects_real_name_like(tmp_path):
    for bad in ("홍길동", "주식회사가나", "Acme Corp", "고객", "고객1 홍길동"):
        p = run(tmp_path, "fb", "add", "--source", "면담", "--text", "t", "--customer", bad, ok=False)
        assert p.returncode != 0 and "별칭" in p.stderr
    assert not (tmp_path / "feedback.jsonl").exists()


def test_add_and_list_output_unchanged(tmp_path):
    p = run(tmp_path, "feedback", "add", "--source", "면담", "--who", "jay", "--text", "안내 문구 톤이 궁금해요")
    assert p.stdout.strip() == "F-1 수집 (state=new, 하루 안에 분류)"
    r = rows(tmp_path)[0]
    assert set(r) == {"id", "date", "source", "who", "text", "state", "kind", "action", "reply", "updated"}
    p = run(tmp_path, "feedback", "list")
    assert p.stdout.strip() == "F-1 [new] 2026-10-17 면담/jay - | 안내 문구 톤이 궁금해요 | 조치: -"


def test_ship_fills_fields(tmp_path):
    run(tmp_path, "fb", "add", "--source", "면담", "--text", "t", "--customer", "고객2")
    ship(tmp_path)
    r = rows(tmp_path)[0]
    assert r["prs"] == [123, 124]
    assert r["shipped"] == "2026-10-16"
    assert r["notice"]["what"].startswith("검색 결과가")
    assert r["notice"]["before"].endswith("before.png") and r["notice"]["after"].endswith("after.png")
    assert r["notice"]["next"].startswith("문서 이름을")
    assert "notified" not in r


def test_ship_rejects_bad_date(tmp_path):
    run(tmp_path, "fb", "add", "--source", "면담", "--text", "t")
    p = run(tmp_path, "fb", "ship", "F-1", "--pr", "1", "--shipped", "10/16", "--notice-what", "a",
            "--notice-next", "b", ok=False)
    assert p.returncode != 0


def test_due_shows_unnotified_then_clears(tmp_path):
    run(tmp_path, "kpi", "add", "--active", "1", "--views", "1", "--cites", "0", "--misses", "0", "--feedback", "0",
        "--customers", "1")
    run(tmp_path, "fb", "add", "--source", "면담", "--text", "로딩 문구를 못 찾았어요", "--customer", "고객1")
    run(tmp_path, "fb", "triage", "F-1", "--kind", "버그", "--state", "backlog")
    before = run(tmp_path, "due").stdout
    assert "개선 반영 안내" not in before
    ship(tmp_path)
    p = run(tmp_path, "due").stdout
    assert "개선 반영 안내(배포됐는데 안내 안 함): F-1 배포 2026-10-16, 안내 안 함(고객1)" in p
    assert p.splitlines()[0].startswith("🔁 지투 루프 점검: 기한 지난 것 ")
    run(tmp_path, "fb", "notified", "F-1", "--date", "2026-10-17")
    assert rows(tmp_path)[0]["notified"] == "2026-10-17"
    assert "개선 반영 안내" not in run(tmp_path, "due").stdout


def test_notified_requires_ship(tmp_path):
    run(tmp_path, "fb", "add", "--source", "면담", "--text", "t")
    p = run(tmp_path, "fb", "notified", "F-1", "--date", "2026-10-17", ok=False)
    assert p.returncode != 0 and "ship" in p.stderr


def test_notice_draft_has_all_parts(tmp_path):
    run(tmp_path, "fb", "add", "--source", "면담", "--text", "로딩 문구를 못 찾았어요", "--customer", "고객1")
    ship(tmp_path)
    out = run(tmp_path, "fb", "notice-draft", "F-1").stdout
    assert "제목: " in out
    assert '"로딩 문구를 못 찾았어요"' in out
    assert "바뀐 것: 검색 결과가 없을 때 쓸 수 있는 문서 목록을 보여 줘요 (2026-10-16 반영)" in out
    assert "바뀌기 전: https://example.com/before.png" in out and "바뀐 뒤: https://example.com/after.png" in out
    assert "다음에 이렇게 해 보세요: 문서 이름을 몰라도 낱말로 찾아보세요" in out
    assert "답해 주세요" in out
    assert "{" not in out and "```" not in out and "\u2014" not in out
    assert "발송은 하지 않습니다" in out


def test_notice_draft_without_screens_and_quote(tmp_path):
    run(tmp_path, "fb", "add", "--source", "면담", "--text", "내부 설명")
    run(tmp_path, "fb", "ship", "F-1", "--pr", "7", "--shipped", "2026-10-16", "--notice-what", "a", "--notice-next", "b")
    out = run(tmp_path, "fb", "notice-draft", "F-1", "--quote", "버튼이 안 보여요").stdout
    assert '"버튼이 안 보여요"' in out and "내부 설명" not in out
    assert "화면 사진은 따로 없어요" in out


def test_notice_draft_requires_ship(tmp_path):
    run(tmp_path, "fb", "add", "--source", "면담", "--text", "t")
    assert run(tmp_path, "fb", "notice-draft", "F-1", ok=False).returncode != 0


def test_old_rows_compatible(tmp_path):
    old = {"id": "F-1", "date": "2026-10-06", "source": "면담", "who": "jay", "text": "t", "state": "replied",
           "kind": "버그", "action": "a", "reply": "r", "updated": "2026-10-15"}
    (tmp_path / "feedback.jsonl").write_text(json.dumps(old, ensure_ascii=False) + "\n", encoding="utf-8")
    run(tmp_path, "fb", "list")
    assert "개선 반영 안내" not in run(tmp_path, "due").stdout
    ship(tmp_path)
    assert rows(tmp_path)[0]["who"] == "jay" and rows(tmp_path)[0]["prs"] == [123, 124]


def test_pr_repo_form_saved_and_shown(tmp_path):
    run(tmp_path, "fb", "add", "--source", "면담", "--text", "t", "--customer", "고객2")
    run(tmp_path, "fb", "ship", "F-1", "--pr", "carvit.ai#37", "--pr", "saegim#667", "--pr", "simplifier-saegim#668",
        "--pr", "site#12", "--pr", "55", "--shipped", "2026-10-16", "--notice-what", "a", "--notice-next", "b")
    assert rows(tmp_path)[0]["prs"] == ["carvit.ai#37", "saegim#667", "saegim#668", "site#12", 55]
    due = run(tmp_path, "due").stdout
    assert "PR carvit.ai#37, saegim#667, saegim#668, site#12, #55" in due
    draft = run(tmp_path, "fb", "notice-draft", "F-1").stdout
    assert "PR carvit.ai#37, saegim#667, saegim#668, site#12, #55" in draft


def test_pr_repo_form_rejected(tmp_path):
    run(tmp_path, "fb", "add", "--source", "면담", "--text", "t")
    for bad in ("other#3", "carvit.ai#", "abc", "carvit.ai#x1"):
        p = run(tmp_path, "fb", "ship", "F-1", "--pr", bad, "--shipped", "2026-10-16", "--notice-what", "a",
                "--notice-next", "b", ok=False)
        assert p.returncode != 0 and "허용 저장소" in p.stderr and "site=hansunghee7.github.io" in p.stderr
    assert "prs" not in rows(tmp_path)[0]


def test_template_missing_message(tmp_path):
    import shutil
    tool_dir = tmp_path / "solo"
    tool_dir.mkdir()
    shutil.copy(TOOL, tool_dir / "jitu_po.py")
    data = tmp_path / "data"
    run(data, "fb", "add", "--source", "면담", "--text", "t")
    run(data, "fb", "ship", "F-1", "--pr", "1", "--shipped", "2026-10-16", "--notice-what", "a", "--notice-next", "b")
    env = dict(os.environ, JITU_PO_DIR=str(data), JITU_PO_TODAY="2026-10-17", PYTHONIOENCODING="utf-8")
    for k in ("JITU_PO_TEMPLATE", "JITU_PO_NOTICE_TEMPLATE"):
        env.pop(k, None)
    p = subprocess.run([sys.executable, "-X", "utf8", str(tool_dir / "jitu_po.py"), "fb", "notice-draft", "F-1"],
                       capture_output=True, text=True, encoding="utf-8", env=env, cwd=str(tmp_path), stdin=subprocess.DEVNULL)
    assert p.returncode == 1
    assert "틀 파일을 찾지 못했습니다:" in p.stderr and "JITU_PO_TEMPLATE로 경로를 지정하세요." in p.stderr
    assert "Traceback" not in p.stderr
    # 환경변수로 지정하면 찾는다
    env["JITU_PO_TEMPLATE"] = str(TOOL.parent.parent.parent / "docs" / "mailcopy" / "개선_반영_안내_틀.md")
    p = subprocess.run([sys.executable, "-X", "utf8", str(tool_dir / "jitu_po.py"), "fb", "notice-draft", "F-1"],
                       capture_output=True, text=True, encoding="utf-8", env=env, cwd=str(tmp_path), stdin=subprocess.DEVNULL)
    assert p.returncode == 0 and "제목: " in p.stdout
