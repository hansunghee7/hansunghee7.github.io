"""ledger_gate.sh·ledger_row.py 시험(2026-10-19, 비티·덱스 업무대장 관문)."""
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

OPS = Path(__file__).resolve().parents[1]
GATE = OPS / "ledger_gate.sh"
BASH = shutil.which("bash")
sys.path.insert(0, str(OPS))
import ledger_row  # noqa: E402

LEDGER = ledger_row.LEDGER


@pytest.fixture
def docs(tmp_path):
    d = tmp_path / "docs"
    d.mkdir()
    (d / f"비티_{LEDGER}.md").write_text("# 비티\n\n### [진행] BT3: 기존 과제\n다음 행동: x\n", encoding="utf-8")
    (d / f"덱스_{LEDGER}.md").write_text("# 덱스\n\n### [대기] DX2: 기존 과제\n다음 행동: y\n", encoding="utf-8")
    return d


def gate(docs, agent, card_text, tmp_path, **env):
    if not BASH:
        pytest.skip("bash 없음")
    card = tmp_path / "card.md"
    card.write_text(card_text, encoding="utf-8")
    e = dict(os.environ, LEDGER_DOCS_DIR=docs.as_posix(), LEDGER_GATE_LOG=(tmp_path / "bypass.log").as_posix())
    e.pop("LEDGER_GATE", None)
    e.update(env)
    script = f'source "{GATE.as_posix()}"; ledger_gate {agent} "{card.as_posix()}"'
    return subprocess.run([BASH, "-c", script], env=e, capture_output=True, text=True, stdin=subprocess.DEVNULL, encoding="utf-8", timeout=30)


def test_missing_line_blocks(docs, tmp_path):
    r = gate(docs, "bt", "# 질문만 있음\n", tmp_path)
    assert r.returncode == 4 and "ledger_row.py" in r.stderr


def test_id_not_in_ledger_blocks(docs, tmp_path):
    r = gate(docs, "bt", f"{LEDGER}: BT9\n# 질문\n", tmp_path)
    assert r.returncode == 4 and "BT9" in r.stderr


def test_existing_row_passes(docs, tmp_path):
    assert gate(docs, "bt", f"{LEDGER}: BT3\n# 질문\n", tmp_path).returncode == 0
    assert gate(docs, "dex", f"- {LEDGER} : DX2\n# 카드\n", tmp_path).returncode == 0


def test_wrong_agent_prefix_blocks(docs, tmp_path):
    r = gate(docs, "dex", f"{LEDGER}: BT3\n", tmp_path)
    assert r.returncode == 4


def test_bypass_is_logged(docs, tmp_path):
    r = gate(docs, "bt", "# 없음\n", tmp_path, LEDGER_GATE="off")
    assert r.returncode == 0
    assert "bt" in (tmp_path / "bypass.log").read_text(encoding="utf-8")


def test_row_add_numbers_and_gate_accepts(docs, tmp_path):
    rid = ledger_row.add_row("bt", "새 과제", "다음에 할 일", docs=docs)
    assert rid == "BT4"
    assert gate(docs, "bt", f"{LEDGER}: {rid}\n", tmp_path).returncode == 0
    assert ledger_row.add_row("dex", "또 하나", "z", docs=docs) == "DX3"
