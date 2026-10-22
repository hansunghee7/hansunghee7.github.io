#!/usr/bin/env python3
"""옛 이름 흔적 3층 스캐너 (읽기 전용). 설계: C:/work/_ops/saegim_removal/scanner_design.md + scanner_design_rev.md(개정 우선)
[옛이름 허용: 옛 이름 스캐너라 검색 패턴을 인용해야 함]

목적: 옛 이름이 히스토리 밖 어디에 남았는지 숫자로 재서 소거 완료 여부를 판정한다.
층 1 = 3개 저장소 파일(내용·이름·브랜치·태그), 층 2 = 이 PC 실행 환경(이름만), 층 3 = GitHub·GCP 이름(읽기 호출만).
분류 여섯 가지: 히스토리(제외) / 설명(허용, 고정 파일만) / 예정(기한 있음, 지나면 위반) / 외부제약 / 미확인 / 위반.
완료 = 위반 0, 예정 0, 미확인 0. 종료 코드는 위반 기준(1이면 위반 있음).
값은 읽어 저장하지 않는다: 환경변수 값, 프로세스 명령줄 인자, 비밀 값, 환경 파일, 금고 폴더 내용 모두 수집 금지.

사용:
  python scripts/ops/name_scan.py                  3층 전부 실행, 결과를 출력 폴더에 YYYY-MM-DD.json/.md 로 쓴다
  python scripts/ops/name_scan.py --layers 1,2     일부 층만
  python scripts/ops/name_scan.py --out DIR --repos PATH [PATH...] --no-write
"""
import argparse
import csv
import datetime as dt
import fnmatch
import io
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
import unicodedata
from pathlib import Path

VERSION = "1.1.0"
HERE = Path(__file__).resolve().parent
CONFIG_PATH = HERE / "name_scan_config.json"
NEEDLE = "saegim|새김"
PATTERN = re.compile(NEEDLE, re.IGNORECASE)
PATTERN_NFD = re.compile(unicodedata.normalize("NFD", NEEDLE), re.IGNORECASE)
CATEGORIES = ("history", "explain", "planned", "external", "unverified", "violation")
CAT_KO = {"history": "히스토리", "explain": "설명", "planned": "예정", "external": "외부제약", "unverified": "미확인", "violation": "위반"}
KIND_KO = {"content": "내용 적중", "path": "파일·폴더 이름 적중", "branch": "브랜치 이름", "tag": "태그 이름", "ratchet": "허용목록 증가",
           "remote_file": "원격 PC 파일 적중", "remote_cron": "원격 PC 크론 적중"}
LAYER_KO = {0: "설정", 1: "층1 파일", 2: "층2 실행환경", 3: "층3 외부서비스"}

# ---------------------------------------------------------------- 읽기 전용 호출 관문
# 허용 명령은 "정확한 형태"만 통과한다(전체 argv 검증). 쓰기 낱말 금지 목록은 값 자리의 우회를 막는 보조 장치다.
FORBIDDEN_WORDS = {
    "delete", "create", "edit", "set", "remove", "rename", "transfer", "archive", "unarchive", "add", "update", "push",
    "merge", "run", "disable", "enable", "deploy", "destroy", "import", "upload", "revoke", "reset", "login", "logout",
    "write", "patch", "put", "post", "cancel", "rerun", "fork", "clone", "sync", "close", "reopen", "lock", "unlock",
    "start", "stop", "restart", "apply", "replace", "grant", "bind", "unbind", "attach", "detach", "submit", "trigger",
    "install", "uninstall", "access", "versions", "rotate", "reauth", "checkout", "commit", "fetch", "pull", "clean",
    "gc", "prune", "tag-delete", "config",
}
# 프로세스는 이름과 실행 파일 경로만(명령줄 인자 수집 금지), 환경변수는 이름(Keys)만.
PS_PROCESSES = "Get-CimInstance Win32_Process | Select-Object Name,ExecutablePath | ConvertTo-Json -Compress"
PS_ENV_NAMES = (
    "$o=[ordered]@{user=@([Environment]::GetEnvironmentVariables('User').Keys);"
    "machine=@([Environment]::GetEnvironmentVariables('Machine').Keys)}; $o | ConvertTo-Json -Compress"
)
PS_ALLOWED = {PS_PROCESSES, PS_ENV_NAMES}
PS_HEAD = ["powershell", "-NoProfile", "-NonInteractive", "-Command"]
GIT_EXACT = [
    ["git", "ls-files", "-z"],
    ["git", "ls-files", "--others", "--exclude-standard", "-z"],
    ["git", "for-each-ref", "--format=%(refname:short)", "refs/heads"],
    ["git", "for-each-ref", "--format=%(refname:short)", "refs/remotes"],
    ["git", "for-each-ref", "--format=%(refname:short)", "refs/tags"],
]
_GET = r"(?i)GET"  # gh api 의 --method/-X 는 GET만
_JQ = r"\.\[\]\.name"
_REPO = r"[\w.-]+/[\w.-]+"
# 명령 접두어 -> (허용 옵션 {옵션: 값 정규식 또는 None(값 없음)}, 위치 인자 정규식 목록)
GH_GCLOUD_SPECS = {
    ("gh", "repo", "list"): ({"--limit": r"\d{1,4}", "--json": r"name", "--jq": _JQ}, [r"[\w.-]+"]),
    ("gh", "variable", "list"): ({"-R": _REPO, "--json": r"name", "--jq": _JQ}, []),
    ("gh", "secret", "list"): ({"-R": _REPO, "--json": r"name", "--jq": _JQ}, []),
    ("gh", "api"): ({"--jq": _JQ, "--method": _GET, "-X": _GET}, [r"repos/[\w.-]+/[\w.-]+(?:/[\w./-]+)?"]),
    ("gcloud", "projects", "list"): ({"--format": r"value\([\w.]+\)", "--quiet": None}, []),
    ("gcloud", "run", "services", "list"): ({"--project": r"[\w.:-]+", "--format": r"value\([\w.]+\)", "--quiet": None}, []),
    ("gcloud", "iam", "service-accounts", "list"): ({"--project": r"[\w.:-]+", "--format": r"value\([\w.]+\)", "--quiet": None}, []),
    ("gcloud", "secrets", "list"): ({"--project": r"[\w.:-]+", "--format": r"value\([\w.]+\)", "--quiet": None}, []),
}


# 구PC(원격) 읽기: 고정 형태의 ssh만. 원격 명령은 개수·파일 경로만 내보내고 내용 줄은 내보내지 않는다.
# [옛이름 허용: 스캐너가 검색 패턴 자체를 원격 명령에 인용해야 함]
SSH_HEAD = ["ssh", "-o", "ConnectTimeout=8", "-o", "BatchMode=yes"]
REMOTE_CRON_SCRIPT = "crontab -l 2>/dev/null | grep -Eic 'saegim|새김'"
REMOTE_FILES_RX = (r"grep -rIcE 'saegim\|새김' (?:\$HOME/[\w./*-]+ )+--exclude-dir=\.git --exclude-dir=node_modules --exclude-dir=__pycache__ "
                   r"--exclude-dir=backup --exclude='\*\.log' --exclude='\*\.bak\*' 2>/dev/null \| grep -v ':0\$'")


def remote_files_script(roots):
    return ("grep -rIcE 'saegim|새김' " + " ".join(roots) + " --exclude-dir=.git --exclude-dir=node_modules --exclude-dir=__pycache__ "
            "--exclude-dir=backup --exclude='*.log' --exclude='*.bak*' 2>/dev/null | grep -v ':0$'")


class ForbiddenCommand(Exception):
    pass


def _exe(token):
    b = os.path.basename(token).lower()
    for ext in (".exe", ".cmd", ".bat"):
        if b.endswith(ext):
            b = b[: -len(ext)]
    return b


def _check_opts(rest, spec, pos_res):
    """옵션은 spec에 있는 것만, 각 한 번씩, 값 정규식 전체 일치. 위치 인자는 pos_res 순서대로."""
    seen, pos, i = set(), [], 0
    while i < len(rest):
        t = rest[i]
        if t.startswith("-"):
            key, eq, val = t.partition("=") if t.startswith("--") else (t, "", "")
            if key not in spec or key in seen:
                raise ForbiddenCommand("허용되지 않은 옵션: " + key)
            seen.add(key)
            rx = spec[key]
            if rx is None:
                if eq:
                    raise ForbiddenCommand("값 없는 옵션에 값: " + key)
            else:
                if not eq:
                    i += 1
                    if i >= len(rest):
                        raise ForbiddenCommand("옵션 값 없음: " + key)
                    val = rest[i]
                if not re.fullmatch(rx, val):
                    raise ForbiddenCommand("허용되지 않은 옵션 값: %s %s" % (key, val[:30]))
            if val.lower() in FORBIDDEN_WORDS:
                raise ForbiddenCommand("쓰기 낱말: " + val)
        else:
            pos.append(t)
        i += 1
    if len(pos) != len(pos_res) or not all(re.fullmatch(r, p) for r, p in zip(pos_res, pos)):
        raise ForbiddenCommand("허용되지 않은 위치 인자")
    for p in pos:
        if p.lower() in FORBIDDEN_WORDS:
            raise ForbiddenCommand("쓰기 낱말: " + p)


def check_readonly(argv):
    """전체 argv가 허용된 정확한 형태일 때만 통과. 아니면 ForbiddenCommand."""
    if not argv:
        raise ForbiddenCommand("빈 명령")
    tokens = [_exe(argv[0])] + [str(a) for a in argv[1:]]
    if tokens[0] == "git":
        # 서브명령 앞 전역 옵션(-c, --exec-path 등)·추가 인자 모두 정확 일치로 거부된다
        if tokens not in GIT_EXACT:
            raise ForbiddenCommand("허용되지 않은 git 호출")
        return
    if tokens[0] == "powershell":
        if len(tokens) != 5 or tokens[:4] != PS_HEAD or tokens[4] not in PS_ALLOWED:
            raise ForbiddenCommand("허용되지 않은 파워셸 호출")
        return
    if tokens[0] == "ssh":
        if len(tokens) != 7 or tokens[:5] != SSH_HEAD or not re.fullmatch(r"[\w.-]+", tokens[5]):
            raise ForbiddenCommand("허용되지 않은 ssh 호출")
        if tokens[6] != REMOTE_CRON_SCRIPT and not re.fullmatch(REMOTE_FILES_RX, tokens[6]):
            raise ForbiddenCommand("허용되지 않은 원격 명령")
        return
    if tokens[0] == "schtasks":
        if [t.lower() for t in tokens] != ["schtasks", "/query", "/fo", "csv", "/nh"]:
            raise ForbiddenCommand("schtasks는 /query /fo csv /nh 만 허용")
        return
    for prefix, (spec, pos_res) in GH_GCLOUD_SPECS.items():
        if tuple(t.lower() for t in tokens[: len(prefix)]) == prefix:
            _check_opts(tokens[len(prefix):], spec, pos_res)
            return
    raise ForbiddenCommand("허용 목록에 없는 명령: " + " ".join(tokens[:3]))


def default_runner(argv, timeout, cwd=None):
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    env = dict(os.environ, CLOUDSDK_CORE_DISABLE_PROMPTS="1", GH_PROMPT_DISABLED="1", GIT_TERMINAL_PROMPT="0")
    exe = shutil.which(argv[0])
    cmd = [exe or argv[0]] + list(argv[1:])
    p = subprocess.run(cmd, cwd=cwd, capture_output=True, timeout=timeout, stdin=subprocess.DEVNULL, creationflags=flags, env=env)
    return p.returncode, p.stdout, p.stderr


def run_cmd(argv, timeout=30, cwd=None, runner=None):
    """관문을 통과한 읽기 전용 명령만 실행한다. (returncode, stdout bytes, stderr bytes)"""
    check_readonly(argv)
    return (runner or default_runner)(argv, timeout, cwd)


def dec(b):
    if isinstance(b, str):
        return b
    try:
        return b.decode("utf-8")
    except UnicodeDecodeError:
        return b.decode("cp949", "replace")


def short_reason(err):
    """stderr 원문은 저장하지 않는다. 분류 코드만 돌려준다: 인증 필요 / 없음(404) / 시간 초과 / 기타."""
    low = dec(err or b"").lower()
    if re.search(r"reauth|auth|login|credential|\b401\b|\b403\b|permission denied", low):
        return "인증 필요"
    if re.search(r"\b404\b|not found|does not exist|no such", low):
        return "없음(404)"
    if "timed out" in low or "timeout" in low:
        return "시간 초과"
    return "기타"


def error_code(exc):
    """예외 메시지 원문 대신 분류 코드만 쓴다."""
    if isinstance(exc, subprocess.TimeoutExpired):
        return "시간 초과"
    if isinstance(exc, FileNotFoundError):
        return "없음(404)"
    if isinstance(exc, ForbiddenCommand):
        return "차단됨(읽기 전용 관문)"
    return "기타"


# ---------------------------------------------------------------- 패턴·설정
def matches(s):
    """NFC·NFD 두 형태 모두에서 찾는다."""
    return bool(PATTERN.search(unicodedata.normalize("NFC", s)) or PATTERN_NFD.search(unicodedata.normalize("NFD", s)))


def load_config(path=None):
    return json.loads(Path(path or CONFIG_PATH).read_text(encoding="utf-8"))


def today_str():
    return dt.date.today().isoformat()


def rule_active(rule, today):
    return not rule.get("expires") or rule["expires"] >= today


def check_out_dir(out_dir, repos):
    """출력 폴더가 스캔 대상 저장소 안이거나 겹치면 거부한다."""
    o = os.path.normcase(os.path.realpath(str(out_dir)))
    for r in repos:
        rp = os.path.normcase(os.path.realpath(str(r)))
        if o == rp or o.startswith(rp + os.sep) or rp.startswith(o + os.sep):
            raise SystemExit("출력 폴더가 스캔 대상 저장소와 겹쳐 거부한다: " + os.path.basename(rp))


def assert_clean_path(p):
    if matches(str(p)):
        raise SystemExit("출력 경로에 옛 이름이 들어 있어 쓰지 않는다: " + str(p))


# ---------------------------------------------------------------- 수집기 공통
def new_result(layer, name):
    return {"layer": layer, "collector": name, "findings": [], "unverified": [], "ok": 0, "fail": 0, "stats": {}}


def add_unverified(res, what, reason):
    res["unverified"].append({"layer": res["layer"], "what": what, "reason": reason})
    res["fail"] += 1


def finding(layer, kind, subject, repo=None, count=1, **extra):
    f = {"layer": layer, "kind": kind, "subject": subject, "repo": repo, "count": count}
    f.update(extra)
    return f


def run_collectors(collectors, timeout):
    """collectors: [(layer, name, fn)]. 각자 독립 타임아웃(데몬 스레드), 하나가 실패·정지해도 나머지는 계속한다."""
    slots = []
    for layer, name, fn in collectors:
        slot = {"layer": layer, "name": name, "res": None, "err": None, "done": threading.Event()}

        def work(fn=fn, slot=slot):
            try:
                slot["res"] = fn()
            except BaseException as e:  # noqa: BLE001 수집기 하나의 실패가 전체를 막지 않는다
                slot["err"] = error_code(e)
            finally:
                slot["done"].set()

        t = threading.Thread(target=work, daemon=True)
        slot["thread"] = t
        t.start()
        slots.append(slot)
    deadline = time.monotonic() + timeout
    out = []
    for s in slots:
        s["done"].wait(max(0.0, deadline - time.monotonic()))
        if s["done"].is_set() and s["res"] is not None:
            out.append(s["res"])
            continue
        res = new_result(s["layer"], s["name"])
        add_unverified(res, s["name"], s["err"] or "시간 초과(%ss)" % timeout)
        res["crashed"] = True
        out.append(res)
    return out


# ---------------------------------------------------------------- 층 1: 파일
def is_secret_path(rel):
    parts = rel.replace("\\", "/").split("/")
    if any("vault" in p.lower() for p in parts[:-1]):
        return True
    return parts[-1].lower().startswith(".env")


def heading_sections(lines, headings):
    """{제목: [해당 구간 줄 번호]} (제목 줄부터 같거나 높은 단계의 다음 제목 전까지)."""
    out = {}
    cur, level = None, 0
    for i, line in enumerate(lines, 1):
        m = re.match(r"^(#{1,6})\s+(.*)$", line)
        if m:
            lv = len(m.group(1))
            if cur is not None and lv <= level:
                cur = None
            if cur is None and any(h in m.group(2) for h in headings):
                cur, level = m.group(2).strip(), lv
                out.setdefault(cur, [])
        if cur is not None:
            out[cur].append(i)
    return out


def collect_repo(path, cfg, runner=None, timeout=60):
    path = str(path)
    repo = os.path.basename(os.path.abspath(path))
    res = new_result(1, "files:" + repo)
    maxb = cfg.get("max_file_bytes", 2 * 1024 * 1024)
    stats = {"files_scanned": 0, "skipped_binary": 0, "skipped_large": 0, "skipped_secret": 0, "skipped_other": 0}
    if not os.path.isdir(path):
        add_unverified(res, "저장소 사본 " + repo, "폴더 없음")
        return res
    section_rules = [r for r in cfg.get("history_rules", []) if r.get("section_file") and r.get("repo") == repo]
    exclude = [os.path.normcase(os.path.abspath(x)) for x in cfg.get("_exclude_dirs", [])]
    names = set()
    for label, argv in (("tracked", ["git", "ls-files", "-z"]), ("untracked", ["git", "ls-files", "--others", "--exclude-standard", "-z"])):
        try:
            rc, out, err = run_cmd(argv, timeout=timeout, cwd=path, runner=runner)
        except Exception as e:  # noqa: BLE001
            add_unverified(res, "git ls-files(%s) %s" % (label, repo), error_code(e))
            continue
        if rc != 0:
            add_unverified(res, "git ls-files(%s) %s" % (label, repo), short_reason(err))
            continue
        res["ok"] += 1
        for raw in out.split(b"\0"):
            if raw:
                names.add(raw.decode("utf-8", "replace"))
    seen_dirs = set()
    for rel in sorted(names):
        parts = rel.split("/")
        for i in range(1, len(parts)):
            d = "/".join(parts[:i])
            if d not in seen_dirs and matches(parts[i - 1]):
                seen_dirs.add(d)
                res["findings"].append(finding(1, "path", d + "/", repo))
        if matches(parts[-1]):
            res["findings"].append(finding(1, "path", rel, repo))
        full = os.path.join(path, *parts)
        nfull = os.path.normcase(os.path.abspath(full))
        if any(nfull == x or nfull.startswith(x + os.sep) for x in exclude):
            continue  # 결과 폴더는 스캔에서 항상 제외
        if is_secret_path(rel):
            stats["skipped_secret"] += 1
            continue
        try:
            if os.path.islink(full) or not os.path.isfile(full):
                stats["skipped_other"] += 1
                continue
            if os.path.getsize(full) > maxb:
                stats["skipped_large"] += 1
                continue
            with open(full, "rb") as fh:
                data = fh.read()
        except OSError:
            stats["skipped_other"] += 1
            continue
        if b"\0" in data[:8192]:
            stats["skipped_binary"] += 1
            continue
        stats["files_scanned"] += 1
        text = unicodedata.normalize("NFC", data.decode("utf-8", "replace"))
        lines = text.splitlines()
        hit_lines = {}
        for i, line in enumerate(lines, 1):
            n = len(PATTERN.findall(line))
            if n:
                hit_lines[i] = n
        if hit_lines:
            f = finding(1, "content", rel, repo, count=sum(hit_lines.values()), hit_lines=hit_lines)
            rules_here = [r for r in section_rules if r["section_file"] == rel]
            if rules_here:  # 같은 파일에 절 규칙이 여럿이어도 규칙 ID별로 모두 계산한다
                f["sections"] = {r["id"]: sorted({n for ls in heading_sections(lines, [r["section_heading"]]).values() for n in ls}) for r in rules_here}
            res["findings"].append(f)
    for kind, ref in (("branch", "refs/heads"), ("branch", "refs/remotes"), ("tag", "refs/tags")):
        try:
            rc, out, err = run_cmd(["git", "for-each-ref", "--format=%(refname:short)", ref], timeout=timeout, cwd=path, runner=runner)
        except Exception as e:  # noqa: BLE001
            add_unverified(res, "git for-each-ref %s %s" % (ref, repo), error_code(e))
            continue
        if rc != 0:
            add_unverified(res, "git for-each-ref %s %s" % (ref, repo), short_reason(err))
            continue
        res["ok"] += 1
        for name in dec(out).splitlines():
            if matches(name):
                res["findings"].append(finding(1, kind, name.strip(), repo))
    res["stats"] = stats
    return res


# ---------------------------------------------------------------- 층 2: 이 PC 실행 환경 (이름만)
def _ps(script, timeout, runner):
    return run_cmd(["powershell", "-NoProfile", "-NonInteractive", "-Command", script], timeout=timeout, runner=runner)


def _names_only(obj):
    """딕셔너리면 키(이름)만, 리스트면 문자열 항목만. 값은 버린다."""
    if isinstance(obj, dict):
        return [str(k) for k in obj.keys()]
    if isinstance(obj, list):
        return [x for x in obj if isinstance(x, str)]
    return []


def collect_env_names(runner=None, timeout=60):
    res = new_result(2, "env_names")
    rc, out, err = _ps(PS_ENV_NAMES, timeout, runner)
    if rc != 0:
        add_unverified(res, "환경변수 이름", short_reason(err))
        return res
    data = json.loads(dec(out) or "{}")
    res["ok"] += 1
    total = 0
    for scope in ("user", "machine"):
        for name in _names_only(data.get(scope, [])):
            total += 1
            if matches(name):
                res["findings"].append(finding(2, "env", name, None, scope=scope))
    res["stats"] = {"env_names_seen": total}
    return res


def collect_tasks(runner=None, timeout=60):
    res = new_result(2, "scheduled_tasks")
    rc, out, err = run_cmd(["schtasks", "/query", "/fo", "csv", "/nh"], timeout=timeout, runner=runner)
    if rc != 0:
        add_unverified(res, "작업 스케줄러 이름", short_reason(err))
        return res
    res["ok"] += 1
    seen = set()
    for row in csv.reader(io.StringIO(dec(out))):
        if row and row[0] and row[0] not in seen:
            seen.add(row[0])
            if matches(row[0]):
                res["findings"].append(finding(2, "task", row[0], None))
    res["stats"] = {"tasks_seen": len(seen)}
    return res


def collect_remote(host_cfg, runner=None, timeout=60):
    """구PC 같은 원격 PC: 크론 줄 수와 옛 이름이 든 파일 경로·건수만 읽는다(내용 줄은 읽지 않는다)."""
    name, host = host_cfg["name"], host_cfg["host"]
    res = new_result(2, "remote:" + name)
    head = SSH_HEAD + [host]
    rc, out, err = run_cmd(head + [REMOTE_CRON_SCRIPT], timeout=timeout, runner=runner)
    if rc not in (0, 1):  # grep -c 는 0건이면 종료 코드 1
        add_unverified(res, name + " 크론", short_reason(err))
    else:
        res["ok"] += 1
        n = int((dec(out).strip() or "0").split()[0])
        if n:
            res["findings"].append(finding(2, "remote_cron", name + " crontab", None, count=n))
    rc, out, err = run_cmd(head + [remote_files_script(host_cfg["roots"])], timeout=timeout, runner=runner)
    if rc not in (0, 1):
        add_unverified(res, name + " 파일", short_reason(err))
        return res
    res["ok"] += 1
    files = 0
    for line in dec(out).splitlines():
        path, _, cnt = line.rpartition(":")
        if path and cnt.isdigit() and int(cnt):
            files += 1
            res["findings"].append(finding(2, "remote_file", "%s:%s" % (name, path), None, count=int(cnt)))
    res["stats"] = {"remote_files_hit": files}
    return res


def collect_processes(runner=None, timeout=60):
    res = new_result(2, "processes")
    rc, out, err = _ps(PS_PROCESSES, timeout, runner)
    if rc != 0:
        add_unverified(res, "실행 중 프로세스", short_reason(err))
        return res
    data = json.loads(dec(out) or "[]")
    if isinstance(data, dict):
        data = [data]
    res["ok"] += 1
    seen = set()
    for p in data:
        if not isinstance(p, dict):
            continue
        name = str(p.get("Name") or "")
        exe = str(p.get("ExecutablePath") or "")  # 명령줄 인자는 읽지도 저장하지도 않는다
        key = (name, exe)
        if key in seen:
            continue
        seen.add(key)
        if matches(name) or matches(exe):
            res["findings"].append(finding(2, "process", "%s | %s" % (name, exe), None))
    res["stats"] = {"processes_seen": len(seen)}
    return res


def collect_mcp(files=None):
    res = new_result(2, "mcp_servers")
    home = Path(os.path.expanduser("~"))
    files = files or [home / ".claude.json", home / ".claude" / "settings.json", home / ".claude" / "settings.local.json"]
    existing = [Path(f) for f in files if Path(f).exists()]
    if not existing:
        add_unverified(res, "Claude 설정의 MCP 서버 이름", "설정 파일 없음")
        return res
    names = set()
    for f in existing:
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except Exception as e:  # noqa: BLE001
            add_unverified(res, "MCP 서버 이름 " + f.name, "파싱 실패(%s)" % error_code(e))
            continue
        res["ok"] += 1
        holders = [data]
        if isinstance(data.get("projects"), dict):
            holders += [v for v in data["projects"].values() if isinstance(v, dict)]
        for h in holders:
            m = h.get("mcpServers")
            if isinstance(m, dict):
                names.update(str(k) for k in m.keys())  # 서버 이름 키만. 값(주소·토큰)은 버린다.
    for n in sorted(names):
        if matches(n):
            res["findings"].append(finding(2, "mcp", n, None))
    res["stats"] = {"mcp_servers_seen": len(names)}
    return res


# ---------------------------------------------------------------- 층 3: GitHub·GCP 이름
def _lines(out):
    return [x.strip() for x in dec(out).splitlines() if x.strip()]


def collect_github(cfg, runner=None, timeout=60):
    res = new_result(3, "github")
    owner = cfg.get("github_owner", "hansunghee7")
    if not shutil.which("gh") and runner is None:
        add_unverified(res, "GitHub(gh) 조회", "gh 없음")
        return res
    deadline = time.monotonic() + timeout - 5

    def call(what, argv, allow404=False):
        left = max(5, deadline - time.monotonic())
        try:
            rc, out, err = run_cmd(argv, timeout=left, runner=runner)
        except Exception as e:  # noqa: BLE001
            add_unverified(res, what, error_code(e))
            return None
        if rc != 0:
            if allow404 and ("404" in dec(err) or "Not Found" in dec(err)):
                res["ok"] += 1
                return []
            add_unverified(res, what, short_reason(err))
            return None
        res["ok"] += 1
        return _lines(out)

    names = call("저장소 이름 목록", ["gh", "repo", "list", owner, "--limit", "300", "--json", "name", "--jq", ".[].name"])
    for n in names or []:
        if matches(n):
            res["findings"].append(finding(3, "ghrepo", "%s/%s" % (owner, n), None))
    for r in cfg.get("github_target_repos", []):
        full = "%s/%s" % (owner, r)
        for kind, what, argv, allow in (
            ("ghvar", "저장소 변수 이름", ["gh", "variable", "list", "-R", full, "--json", "name", "--jq", ".[].name"], False),
            ("ghsecret", "저장소 비밀 이름", ["gh", "secret", "list", "-R", full, "--json", "name", "--jq", ".[].name"], False),
            ("ghworkflow", "워크플로 파일 이름", ["gh", "api", "repos/%s/contents/.github/workflows" % full, "--jq", ".[].name"], True),
        ):
            got = call("%s %s" % (what, full), argv, allow404=allow)
            for n in got or []:
                if matches(n):
                    res["findings"].append(finding(3, kind, "%s:%s" % (full, n), None))
    return res


def collect_gcp(runner=None, timeout=60):
    res = new_result(3, "gcp")
    if not shutil.which("gcloud") and runner is None:
        for w in ("GCP 프로젝트 목록", "Cloud Run 서비스", "서비스 계정", "비밀 이름"):
            add_unverified(res, w, "gcloud 없음")
        return res
    deadline = time.monotonic() + timeout - 5
    MIN_CALL = 5

    class BudgetExhausted(Exception):
        pass

    def call(argv):
        left = deadline - time.monotonic()
        if left < MIN_CALL:
            raise BudgetExhausted()
        return run_cmd(argv, timeout=left, runner=runner)

    budget_exhausted = False
    try:
        rc, out, err = call(["gcloud", "projects", "list", "--format=value(projectId)", "--quiet"])
    except BudgetExhausted:
        rc, out, err, budget_exhausted = 1, b"", b"", True
    except Exception as e:  # noqa: BLE001
        rc, out, err = 1, b"", b"timed out" if error_code(e) == "시간 초과" else b""
    if rc != 0:
        reason = "시간 예산 소진" if budget_exhausted else short_reason(err)
        for w in ("GCP 프로젝트 목록", "Cloud Run 서비스 목록", "서비스 계정 목록", "비밀 이름 목록"):
            add_unverified(res, w, reason)
        return res
    res["ok"] += 1
    projects = _lines(out)
    for p in projects:
        if matches(p):
            res["findings"].append(finding(3, "gcp_project", p, None))
    for p in projects:
        # 남은 시간 예산이 바닥나면 이후 프로젝트는 호출 없이 바로 미확인으로 남긴다(강제 5초 호출 반복이
        # 외부 데드라인을 넘겨 수집기 전체가 '시간 초과'로 찍히는 것을 막는다).
        if deadline - time.monotonic() < MIN_CALL:
            for what in ("Cloud Run 서비스", "서비스 계정", "비밀 이름"):
                add_unverified(res, "%s %s" % (what, p), "시간 예산 소진")
            continue
        for kind, what, argv in (
            ("gcp_run", "Cloud Run 서비스", ["gcloud", "run", "services", "list", "--project", p, "--format=value(metadata.name)", "--quiet"]),
            ("gcp_sa", "서비스 계정", ["gcloud", "iam", "service-accounts", "list", "--project", p, "--format=value(email)", "--quiet"]),
            ("gcp_secret", "비밀 이름", ["gcloud", "secrets", "list", "--project", p, "--format=value(name)", "--quiet"]),
        ):
            try:
                rc, out, err = call(argv)
            except BudgetExhausted:
                add_unverified(res, "%s %s" % (what, p), "시간 예산 소진")
                continue
            except Exception as e:  # noqa: BLE001
                add_unverified(res, "%s %s" % (what, p), error_code(e))
                continue
            if rc != 0:
                add_unverified(res, "%s %s" % (what, p), short_reason(err))
                continue
            res["ok"] += 1
            for n in _lines(out):
                if matches(n):
                    res["findings"].append(finding(3, kind, "%s:%s" % (p, n), None))
    return res


# ---------------------------------------------------------------- 분류
def _file_history_hit(rule, repo, rel):
    if rule.get("repo") and rule["repo"] != repo:
        return False
    if rule.get("file"):
        return rule["file"] == rel
    if rule.get("dated_glob"):
        if not fnmatch.fnmatch(rel, rule["dated_glob"]):
            return False
        m = re.search(r"(\d{4}-\d{2}-\d{2})", os.path.basename(rel))
        return bool(m) and m.group(1) <= rule["frozen_through"]  # 새 날짜 파일은 자동 제외하지 않는다
    return False


def classify(f, cfg, today):
    """한 적중을 [(분류, 규칙ID, 건수, 사유)] 로 나눈다. 예정 기한 초과는 위반으로 승격한다."""
    repo, rel, kind = f.get("repo"), f["subject"], f["kind"]
    count = f.get("count", 1)
    if f["layer"] == 1 and kind in ("content", "path"):
        for r in cfg.get("history_rules", []):
            if rule_active(r, today) and _file_history_hit(r, repo, rel):
                return [("history", r["id"], count, "")]
        if kind == "content":
            # 구간 규칙: 지정한 절 안의 줄만 히스토리(규칙마다 따로), 나머지는 계속 분류
            rules = [r for r in cfg.get("history_rules", []) if r.get("section_file") == rel and r.get("repo") == repo and rule_active(r, today)]
            if rules:
                hl = {int(k): v for k, v in (f.get("hit_lines") or {}).items()}
                secs = f.get("sections") or {}
                parts, used = [], set()
                for r in rules:
                    mine = {ln for ln in secs.get(r["id"], []) if ln in hl and ln not in used}
                    used |= mine
                    n_sec = sum(hl[ln] for ln in mine)
                    if n_sec:
                        parts.append(("history", r["id"], n_sec, ""))
                rest = count - sum(parts_n for _, _, parts_n, _ in parts)
                if rest > 0:
                    g = dict(f, count=rest)
                    parts += _explain_or_rest(g, cfg, today)
                return parts
    return _explain_or_rest(f, cfg, today)


def _explain_or_rest(f, cfg, today):
    if f["layer"] == 1 and f["kind"] in ("content", "path"):
        for e in cfg.get("explain_files", []):
            if e.get("repo") == f.get("repo") and e.get("file") == f["subject"]:
                return [("explain", "", f.get("count", 1), "")]
    return _classify_rest(f, cfg, today)


def _classify_rest(f, cfg, today):
    repo, rel, kind, count = f.get("repo"), f["subject"], f["kind"], f.get("count", 1)
    for r in cfg.get("planned", []):
        if kind in r["kinds"] and (not r.get("repo") or r["repo"] == repo) and re.search(r["match"], rel, re.IGNORECASE):
            if r["deadline"] < today:
                return [("violation", r["id"], count, "예정 기한 초과 %s (%s 단계)" % (r["deadline"], r["step"]))]
            return [("planned", r["id"], count, "%s 단계, 기한 %s, 담당 %s" % (r["step"], r["deadline"], r["owner"]))]
    for r in cfg.get("external", []):
        if kind in r.get("kinds", [kind]) and re.search(r["match"], rel, re.IGNORECASE):
            return [("external", r.get("id", ""), count, r.get("note", ""))]
    return [("violation", "", count, "")]


def ratchet_violations(cfg):
    out = []
    lim = cfg.get("ratchet", {})
    cur = {"history_rules": len(cfg.get("history_rules", [])), "explain_files": len(cfg.get("explain_files", [])), "external": len(cfg.get("external", []))}
    for k, v in cur.items():
        if v > lim.get(k, 0):
            out.append(finding(0, "ratchet", "%s %d > 상한 %d" % (k, v, lim.get(k, 0)), None))
    return out


def build_report(results, cfg, today, now_iso, prev=None, layers=(1, 2, 3), strict=False):
    layer_ids = sorted(set(list(layers) + [0]))
    summ = {l: {c: 0 for c in CATEGORIES} for l in layer_ids}
    for l in layer_ids:
        summ[l].update({"hits": 0, "queries_ok": 0, "queries_fail": 0, "collectors_crashed": 0, "hits_by_cat": {c: 0 for c in CATEGORIES}, "by_kind": {}})
    entries = {c: [] for c in CATEGORIES}
    stats = {}
    for r in results:
        l = r["layer"]
        summ[l]["queries_ok"] += r["ok"]
        summ[l]["queries_fail"] += r["fail"]
        summ[l]["collectors_crashed"] += 1 if r.get("crashed") else 0
        for k, v in r["stats"].items():
            stats[k] = stats.get(k, 0) + v
        for u in r["unverified"]:
            entries["unverified"].append(u)
            summ[l]["unverified"] += 1
            summ[l]["hits_by_cat"]["unverified"] += 1
        for f in r["findings"]:
            for cat, rid, n, why in classify(f, cfg, today):
                summ[l][cat] += 1  # 발견 레코드 수(파일·이름 하나가 한 레코드)
                summ[l]["hits_by_cat"][cat] += n  # 적중 횟수(레코드 안의 일치 개수 합)
                summ[l]["hits"] += n
                bk = summ[l]["by_kind"].setdefault(cat, {}).setdefault(f["kind"], [0, 0])
                bk[0] += 1
                bk[1] += n
                if cat in ("planned", "external", "violation"):
                    entries[cat].append({"layer": l, "kind": f["kind"], "repo": f.get("repo"), "subject": f["subject"], "count": n, "rule": rid, "note": why})
    for f in ratchet_violations(cfg):
        summ[0]["violation"] += 1
        entries["violation"].append({"layer": 0, "kind": "ratchet", "repo": None, "subject": f["subject"], "count": 1, "rule": "", "note": "허용 목록이 늘었다"})
    for m in cfg.get("manual_checks", []):
        if m.get("layer", 3) not in layers:
            continue
        entries["unverified"].append({"layer": m.get("layer", 3), "what": m["what"], "reason": "수동 확인 필요(읽기 방법 없음)"})
        summ[m.get("layer", 3)]["unverified"] += 1
        summ[m.get("layer", 3)]["hits_by_cat"]["unverified"] += 1
    vcounts = {}
    for e in entries["violation"]:
        k = violation_key(e)
        vcounts[k] = vcounts.get(k, 0) + e["count"]
    vkeys = sorted(vcounts)
    # 직전 정상 스캔과는 같은 층 조합일 때만 비교한다. 키가 새로 생기거나 같은 키의 건수가 늘면 새 위반이다.
    if prev and prev.get("baseline_ok") and "violation_counts" in prev and sorted(prev.get("layers_run", [])) == sorted(layers):
        pc = prev["violation_counts"]
        new_v = [k for k in vkeys if k not in pc or vcounts[k] > pc[k]]
        resolved = [k for k in pc if k not in vcounts]
    else:
        prev = None
        new_v, resolved = [], []
    total = {c: sum(summ[l][c] for l in layer_ids) for c in CATEGORIES}
    crashed = sum(summ[l]["collectors_crashed"] for l in layer_ids)
    # 기준선으로 쓸 수 있는 정상 스캔: 실행한 모든 층의 조회가 성공하고 수집기가 죽지 않았을 때만
    baseline_ok = crashed == 0 and all(summ[l]["queries_fail"] == 0 for l in layers)
    complete = total["violation"] == 0 and total["planned"] == 0 and total["unverified"] == 0 and all(summ[l]["queries_fail"] == 0 for l in layers)
    return {
        "scanner_version": VERSION, "config_version": cfg.get("config_version"), "run_at": now_iso, "date": today,
        "layers_run": list(layers), "summary": {str(l): summ[l] for l in layer_ids}, "totals": total, "stats": stats,
        "complete": complete, "baseline_ok": baseline_ok,
        "violation_keys": vkeys, "violation_counts": vcounts, "new_violations": new_v, "resolved_violations": resolved, "prev_date": (prev or {}).get("date"),
        "entries": entries, "strict": strict, "exit_code": exit_code_for(total, complete, strict),
    }


def exit_code_for(total, complete, strict=False):
    """위반이 있으면 1. 위반 0이면 0(보고서에 complete=false 명시). --strict 면 미확인·예정이 남을 때 2."""
    if total["violation"]:
        return 1
    if strict and not complete:
        return 2
    return 0


def violation_key(e):
    return "%s|%s|%s|%s" % (e["layer"], e["kind"], e.get("repo") or "", e["subject"])


def render_md(rep):
    L = []
    L.append("# 옛 이름 흔적 스캔 %s" % rep["date"])
    L.append("")
    L.append("- 실행 시각: %s / 스캐너 %s / 설정 %s" % (rep["run_at"], rep["scanner_version"], rep["config_version"]))
    t = rep["totals"]
    if rep["complete"]:
        L.append("- 판정: **완료 가능** (위반 0, 예정 0, 미확인 0)")
    else:
        why = []
        if t["violation"]:
            why.append("위반 %d" % t["violation"])
        if t["planned"]:
            why.append("예정 %d" % t["planned"])
        if t["unverified"]:
            why.append("미확인 %d" % t["unverified"])
        L.append("- 판정: **완료 불가** (%s). 종료 코드는 위반 기준(%d)%s" % (", ".join(why) or "조회 실패", rep["exit_code"], ", --strict 사용 중" if rep.get("strict") else ""))
    L.append("- complete=%s" % ("true" if rep["complete"] else "false"))
    L.append("")
    L.append("각 칸은 `발견 레코드 수 (적중 횟수)`. 레코드는 파일·이름 하나, 적중은 그 안의 일치 개수 합이다. 파일 내용 적중과 경로 이름 적중은 서로 다른 레코드다.")
    L.append("")
    L.append("| 층 | 히스토리 | 설명 | 예정 | 외부제약 | 미확인 | 위반 | 조회 성공/실패 |")
    L.append("|---|---|---|---|---|---|---|---|")
    for l in sorted(int(k) for k in rep["summary"]):
        s = rep["summary"][str(l)]
        if l == 0 and not s["violation"]:
            continue
        cells = " | ".join("%d (%d)" % (s[c], s["hits_by_cat"][c]) for c in CATEGORIES)
        L.append("| %s | %s | %d/%d |" % (LAYER_KO[l], cells, s["queries_ok"], s["queries_fail"]))
    cells = " | ".join("%d (%d)" % (t[c], sum(x["hits_by_cat"][c] for x in rep["summary"].values())) for c in CATEGORIES)
    L.append("| 합계 | %s | %d/%d |" % (cells, sum(s["queries_ok"] for s in rep["summary"].values()), sum(s["queries_fail"] for s in rep["summary"].values())))
    L.append("")
    vk = {}
    for x in rep["summary"].values():
        for kind, (n, h) in x["by_kind"].get("violation", {}).items():
            vk.setdefault(kind, [0, 0])
            vk[kind][0] += n
            vk[kind][1] += h
    if vk:
        L.append("- 위반 분해: " + ", ".join("%s %d레코드/%d적중" % (KIND_KO.get(k, k), n, h) for k, (n, h) in sorted(vk.items())))
    st = rep["stats"]
    if st:
        L.append("- 건너뜀: 이진 %d, 2MB 초과 %d, 비밀·금고 경로 %d(열지 않음), 기타 %d / 검사한 파일 %d" % (st.get("skipped_binary", 0), st.get("skipped_large", 0), st.get("skipped_secret", 0), st.get("skipped_other", 0), st.get("files_scanned", 0)))
    if rep["prev_date"]:
        L.append("- 직전 정상 스캔(%s) 대비: 새 위반 %d, 해소 %d" % (rep["prev_date"], len(rep["new_violations"]), len(rep["resolved_violations"])))
    else:
        L.append("- 직전 정상 스캔(같은 층 조합): 없음, 새 위반 비교 안 함")
    L.append("- 이번 실행을 기준선으로 쓸 수 있는가: %s" % ("예" if rep["baseline_ok"] else "아니오(조회 실패 있음)"))
    L.append("")
    if rep["new_violations"]:
        L.append("## 새 위반 (최대 30)")
        L += ["- " + k for k in rep["new_violations"][:30]]
        L.append("")
    e = rep["entries"]
    if e["unverified"]:
        L.append("## 미확인 %d건" % len(e["unverified"]))
        for u in e["unverified"]:
            L.append("- 층%s %s: %s" % (u["layer"], u["what"], u["reason"]))
        L.append("")
    if e["planned"]:
        by = {}
        for p in e["planned"]:
            by.setdefault(p["rule"], [0, 0, p["note"]])
            by[p["rule"]][0] += 1
            by[p["rule"]][1] += p["count"]
        L.append("## 예정 %d건" % len(e["planned"]))
        for rid, (n, h, note) in sorted(by.items()):
            L.append("- %s: %d건(적중 %d) %s" % (rid, n, h, note))
        L.append("")
    if e["violation"]:
        L.append("## 위반 레코드 %d건 (적중 많은 순 상위 40)" % len(e["violation"]))
        for v in sorted(e["violation"], key=lambda x: -x["count"])[:40]:
            L.append("- [층%s %s] %s%s (적중 %d) %s" % (v["layer"], KIND_KO.get(v["kind"], v["kind"]), (v["repo"] + ":") if v["repo"] else "", v["subject"], v["count"], v["note"]))
        L.append("")
    return "\n".join(L) + "\n"


def load_prev(out_dir, today, layers=None):
    """직전 정상 스캔(baseline_ok)의 JSON. 같은 날 재실행이면 덮어쓰기 전 오늘 파일도 후보다."""
    best = None
    try:
        files = sorted(Path(out_dir).glob("????-??-??.json"))
    except OSError:
        return None
    for p in files:
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            continue
        if d.get("baseline_ok") and d.get("date", "") <= today and (layers is None or sorted(d.get("layers_run", [])) == sorted(layers)):
            best = d
    return best


def build_collectors(cfg, layers, repos, runner=None, timeout=60):
    cs = []
    if 1 in layers:
        for r in repos:
            cs.append((1, "files:" + os.path.basename(os.path.abspath(r)), lambda r=r: collect_repo(r, cfg, runner, timeout)))
    if 2 in layers:
        cs += [(2, "env_names", lambda: collect_env_names(runner, timeout)), (2, "scheduled_tasks", lambda: collect_tasks(runner, timeout)),
               (2, "processes", lambda: collect_processes(runner, timeout)), (2, "mcp_servers", lambda: collect_mcp())]
        for h in cfg.get("remote_hosts", []):
            cs.append((2, "remote:" + h["name"], lambda h=h: collect_remote(h, runner, timeout)))
    if 3 in layers:
        cs += [(3, "github", lambda: collect_github(cfg, runner, timeout)), (3, "gcp", lambda: collect_gcp(runner, timeout))]
    return cs


def main(argv=None):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass
    ap = argparse.ArgumentParser(description="옛 이름 흔적 3층 스캐너(읽기 전용)")
    ap.add_argument("--config", default=None)
    ap.add_argument("--out", default=None)
    ap.add_argument("--layers", default="1,2,3")
    ap.add_argument("--repos", nargs="*", default=None)
    ap.add_argument("--timeout", type=int, default=None)
    ap.add_argument("--no-write", action="store_true")
    ap.add_argument("--strict", action="store_true", help="위반 0이어도 미확인·예정이 남으면 종료 코드 2")
    a = ap.parse_args(argv)
    cfg = load_config(a.config)
    layers = tuple(int(x) for x in a.layers.split(",") if x)
    out_dir = Path(a.out or cfg["output_dir"])
    assert_clean_path(out_dir)
    timeout = a.timeout or cfg.get("collector_timeout_sec", 60)
    repos = a.repos or cfg["repos"]
    check_out_dir(out_dir, repos if 1 in layers else [])
    cfg["_exclude_dirs"] = [str(out_dir)]
    today = today_str()
    now_iso = dt.datetime.now().astimezone().isoformat(timespec="seconds")
    prev = load_prev(out_dir, today, layers)
    results = run_collectors(build_collectors(cfg, layers, repos, None, timeout), timeout)
    rep = build_report(results, cfg, today, now_iso, prev, layers, a.strict)
    md = render_md(rep)
    if not a.no_write:
        out_dir.mkdir(parents=True, exist_ok=True)
        jp, mp = out_dir / (today + ".json"), out_dir / (today + ".md")
        assert_clean_path(jp)
        jp.write_text(json.dumps(rep, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        mp.write_text(md, encoding="utf-8")
    print(md)
    return rep["exit_code"]


if __name__ == "__main__":
    sys.exit(main())
