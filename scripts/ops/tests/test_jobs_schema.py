"""감시 대장(jobs.toml, jobs_goosolar.toml) 칸 검사.

watch.py가 항목 종류(kind)별로 꺼내 쓰는 칸(job["..."])을 기준으로, 빠지면 감시가 죽거나 조용히 기본값으로 도는 항목을 찾는다.
- 오류(ERROR): 빠지면 점검이 실패하거나 감시가 항목을 못 본다. 시험이 실패한다.
- 주의(WARN): 기본값으로 도는 것(owner 없음 등). 목록만 출력하고 시험은 통과한다.
사용: python3 scripts/ops/tests/test_jobs_schema.py   (문제 목록 출력, 오류가 있으면 종료 코드 1)
"""
import re
import sys
import tomllib
import unittest
from pathlib import Path

OPS = Path(__file__).resolve().parent.parent
LEDGERS = ("jobs.toml", "jobs_goosolar.toml")
# watch.py의 check_* 함수가 job["..."]로 직접 꺼내는 칸(없으면 KeyError -> "점검 자체가 실패")
REQUIRED = {
    "hermes_cron": ("period_min",),  # 없으면 1440분으로 조용히 돈다(감시가 사실상 꺼짐)
    "gh_workflow": ("repo", "workflow"),
    "tcp": (),  # port 또는 ports 중 하나(아래에서 따로 검사)
    "http": ("url",),
    "cmd": ("cmd",),
    "file_age": ("path", "max_age_min"),
    "git_file_lines": ("repo", "path", "warn_over", "fail_over"),
    "git_file_age": ("repo", "path", "max_age_days"),
    "pc": ("check",),
}
PC_CHECKS = {"disk_free", "defender", "firewall", "ports"}
INT_KEYS = ("period_min", "every_min", "max_age_min", "max_age_days", "timeout", "fail_after", "stuck_min")


def find_problems(jobs):
    """(오류 목록, 주의 목록)을 돌려준다. 순수 함수."""
    errors, warns = [], []
    seen_id, seen_hermes_name = {}, {}
    for i, j in enumerate(jobs, 1):
        jid = j.get("id") or f"#{i}"
        for k in ("id", "kind", "name"):
            if not str(j.get(k) or "").strip():
                errors.append(f"{jid}: 공통 칸 '{k}' 비어 있음")
        kind = j.get("kind")
        if j.get("id"):
            if j["id"] in seen_id:
                errors.append(f"{jid}: id 중복(앞의 항목 #{seen_id[j['id']]})")
            seen_id[j["id"]] = i
        if kind not in REQUIRED:
            errors.append(f"{jid}: 알 수 없는 kind '{kind}' (watch.py는 pc 점검으로 넘겨 KeyError가 난다)")
            continue
        for k in REQUIRED[kind]:
            if k not in j or j[k] in ("", None, []):
                errors.append(f"{jid}: {kind}에 필수 칸 '{k}' 없음")
        if kind == "tcp" and not (j.get("port") or j.get("ports")):
            errors.append(f"{jid}: tcp에 port 또는 ports 없음")
        if kind == "pc" and j.get("check") and j["check"] not in PC_CHECKS:
            errors.append(f"{jid}: pc 점검 '{j['check']}'는 watch.py가 모른다({sorted(PC_CHECKS)})")
        if kind == "cmd":
            c = j.get("cmd")
            if not (isinstance(c, list) and c and all(isinstance(x, str) and x for x in c)):
                errors.append(f"{jid}: cmd는 비어 있지 않은 문자열 배열이어야 함")
            elif any(re.search(r"[A-Za-z]:\\\\", x) for x in c):
                warns.append(f"{jid}: cmd 경로에 겹 역슬래시(C:\\\\...)가 있다(TOML에서 \\\\\\\\로 적은 흔적)")
        if kind == "hermes_cron":
            nm = j.get("name")
            if nm in seen_hermes_name:
                errors.append(f"{jid}: 헤르메스 크론 이름 '{nm}' 중복(감시는 이름으로 찾는다)")
            seen_hermes_name[nm] = i
        for k in INT_KEYS:
            if k in j and (isinstance(j[k], bool) or not isinstance(j[k], (int, float)) or j[k] <= 0):
                errors.append(f"{jid}: '{k}'는 양수여야 함(현재 {j[k]!r})")
        if j.get("severity") not in (None, "warn"):
            errors.append(f"{jid}: severity는 'warn'만 허용(현재 {j['severity']!r})")
        if "owner" not in j:
            warns.append(f"{jid}: owner 미지정")  # watch.py는 기본값 '탐'으로 알림에 표시한다
        if not j.get("note"):
            warns.append(f"{jid}: note 없음(왜 등록했는지 근거가 대장에 없음)")
    return errors, warns


def load(name):
    return tomllib.loads((OPS / name).read_text(encoding="utf-8"))["job"]


class FindProblemsUnit(unittest.TestCase):
    """검사 함수 자체의 시험: 나쁜 입력은 잡고 좋은 입력은 통과시킨다."""

    def test_catches_bad(self):
        bad = [
            {"id": "a", "kind": "cmd", "name": "x"},  # cmd 없음
            {"id": "a", "kind": "cmd", "name": "y", "cmd": ["python"]},  # id 중복
            {"id": "b", "kind": "file_age", "name": "z", "path": "/p"},  # max_age_min 없음
            {"id": "c", "kind": "tcp", "name": "t"},  # port 없음
            {"id": "d", "kind": "pc", "name": "p", "check": "nope"},
            {"id": "e", "kind": "weird", "name": "w"},
            {"id": "f", "kind": "hermes_cron", "name": "h", "period_min": 0},
            {"id": "", "kind": "cmd", "name": "n", "cmd": ["x"]},
        ]
        errors, _ = find_problems(bad)
        text = "\n".join(errors)
        for needle in ("cmd에 필수 칸 'cmd'", "id 중복", "'max_age_min'", "port 또는 ports", "'nope'", "알 수 없는 kind", "양수", "공통 칸 'id'"):
            self.assertIn(needle, text)

    def test_passes_good(self):
        good = [
            {"id": "a", "kind": "cmd", "name": "x", "cmd": ["python", "a.py"], "owner": "탐", "note": "n"},
            {"id": "b", "kind": "tcp", "name": "t", "ports": [22], "owner": "탐", "note": "n"},
            {"id": "c", "kind": "hermes_cron", "name": "h", "period_min": 10, "owner": "탐", "note": "n"},
        ]
        self.assertEqual(find_problems(good), ([], []))


class LedgerSchema(unittest.TestCase):
    def test_ledgers_have_no_errors(self):
        for name in LEDGERS:
            errors, _ = find_problems(load(name))
            self.assertEqual(errors, [], f"{name}: " + "; ".join(errors))


if __name__ == "__main__":
    for name in LEDGERS:
        errors, warns = find_problems(load(name))
        owner = [w for w in warns if w.endswith("owner 미지정")]
        others = [w for w in warns if w not in owner]
        print(f"== {name}: 오류 {len(errors)}건, 주의 {len(others)}건, owner 미지정 {len(owner)}건(기본값 탐)")
        for e in errors:
            print("  ERROR", e)
        for w in others:
            print("  WARN ", w)
    unittest.main(argv=[sys.argv[0]], verbosity=1)
