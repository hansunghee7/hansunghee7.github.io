"""paid-runner-gate: 유료(깃허브 실행기) 전환·실행만 막고 무료 배포는 통과."""
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("prg", os.path.join(HERE, "paid-runner-gate.py"))
prg = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prg)


class PaidRunnerGateTest(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        wf = os.path.join(self.d, ".github", "workflows")
        os.makedirs(wf)
        with open(os.path.join(wf, "deploy-cloud-run.yml"), "w", encoding="utf-8") as f:
            f.write("jobs:\n  deploy:\n    runs-on: ${{ fromJSON(vars.SAEGIM_DEPLOY_RUNNER || '[\"self-hosted\",\"saegim-test\"]') }}\n")
        with open(os.path.join(wf, "reseed-guides.yml"), "w", encoding="utf-8") as f:
            f.write("jobs:\n  a:\n    runs-on: ubuntu-latest\n")
        prg.SAEGIM = self.d

    def _run(self, cmd):
        env = {**os.environ, "SAEGIM_CHECKOUT": self.d, "PAID_RUNNER_LOG": os.path.join(self.d, "log.jsonl")}
        p = subprocess.run([sys.executable, os.path.join(HERE, "paid-runner-gate.py")],
                           input=json.dumps({"tool_input": {"command": cmd}}).encode("utf-8"),
                           capture_output=True, env=env)
        return p.returncode, p.stderr.decode("utf-8")

    def test_free_deploy_passes(self):
        self.assertEqual(self._run("gh workflow run deploy-cloud-run.yml -R hansunghee7/simplifier-saegim --ref main")[0], 0)
        self.assertEqual(self._run("gh variable set SAEGIM_DEPLOY_RUNNER -R x --body '[\"self-hosted\",\"saegim-test\"]'")[0], 0)
        self.assertEqual(self._run("gh run list -R hansunghee7/simplifier-saegim")[0], 0)

    def test_switch_to_hosted_blocked(self):
        code, err = self._run("gh variable set SAEGIM_DEPLOY_RUNNER -R hansunghee7/simplifier-saegim --body '\"ubuntu-latest\"'")
        self.assertEqual(code, 2)
        self.assertIn("사장님 컨펌", err)
        self.assertEqual(self._run("gh variable set SAEGIM_CI_RUNNER --body '[\"ubuntu-latest\"]'")[0], 2)

    def test_hosted_workflow_run_blocked(self):
        self.assertEqual(self._run("gh workflow run reseed-guides.yml -R hansunghee7/simplifier-saegim")[0], 2)

    def test_confirm_marker_passes_and_logs(self):
        code, _ = self._run("gh workflow run reseed-guides.yml -R hansunghee7/simplifier-saegim # 사장님컨펌: 10/18 가이드 재시드 진행하세요")
        self.assertEqual(code, 0)
        with open(os.path.join(self.d, "log.jsonl"), encoding="utf-8") as f:
            self.assertIn("가이드 재시드", f.read())

    def test_other_repo_workflow_not_checked(self):
        self.assertEqual(self._run("gh workflow run reseed-guides.yml -R hansunghee7/other-repo")[0], 0)


if __name__ == "__main__":
    unittest.main()
