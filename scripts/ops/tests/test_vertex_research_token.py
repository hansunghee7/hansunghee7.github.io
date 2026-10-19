"""vertex_research.token(): 개인 경로 토큰은 gcloud 기본 계정이 아니라 개인 계정을 명시해 받는다(2026-10-20, 핏 보고).
사고: gcloud 기본 계정이 만료된 회사 계정으로 바뀌어 `gcloud auth print-access-token`이 CalledProcessError로 실패, 회사 Vertex 429와 겹쳐 검색 없는 무료 호출로 떨어졌다."""
import importlib.util
import sys
from pathlib import Path
from unittest import mock

OPS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(OPS))
spec = importlib.util.spec_from_file_location("vr_token", OPS / "vertex_research.py")
vr = importlib.util.module_from_spec(spec)
spec.loader.exec_module(vr)


def test_personal_token_names_the_personal_account():
    with mock.patch.object(vr.subprocess, "run") as run, mock.patch.object(vr.shutil, "which", return_value="gcloud"):
        run.return_value = mock.Mock(stdout="TOK\n")
        assert vr.token() == "TOK"
    cmd = run.call_args[0][0]
    assert cmd[:3] == ["gcloud", "auth", "print-access-token"]
    assert f"--account={vr.PERSONAL_ACCOUNT}" in cmd
    assert vr.PERSONAL_ACCOUNT == "hansunghee7@gmail.com"
