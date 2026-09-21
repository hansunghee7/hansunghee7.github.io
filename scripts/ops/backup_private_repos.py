#!/usr/bin/env python3
"""비공개 저장소(경험DB, 새김) 일일 백업 (2026-09-22 사장님 승인).

왜: 두 저장소는 GitHub 무료 요금제라 main 삭제·강제 덮어쓰기 보호를 켤 수 없다(403 확인).
그래서 막는 대신 복구할 수 있게 매일 통째로 복사한다.

무엇을 하나
1. 미러 복제(`git clone --mirror`)를 만들고 매일 갱신한다. 강제 덮어쓰기로 사라진 예전 커밋이 미러 안에 남도록
   `gc.auto=0`, `gc.pruneExpire=never`, `core.logAllRefUpdates=always`를 둔다.
2. 미러에서 `git bundle`(모든 브랜치·태그 포함 단일 파일)을 날짜별로 만들어 검증하고 이 PC와 구글 드라이브에 둔다.
3. 각 위치에서 14일치만 남긴다.
4. 결과를 last-run.txt에 적는다(감시 대장이 이 파일의 나이를 본다). 저장소 하나라도 실패하면 last-run.txt를 갱신하지 않는다.

사용:
  backup_private_repos.py            백업 실행
  backup_private_repos.py --restore-test   최신 번들에서 임시 폴더로 복원해 원격 main과 같은지 확인

비밀값은 다루지 않는다(깃 자격 증명은 이 PC의 기존 설정을 그대로 쓴다). 출력에 토큰을 쓰지 않는다.
"""
import datetime
import glob
import os
import shutil
import subprocess
import sys
import tempfile

OWNER = "hansunghee7"
REPOS = ["simplifier-cxo-db", "simplifier-saegim"]
ROOT = os.environ.get("BACKUP_ROOT", r"C:\work\_backup\private-repos")
DRIVE = os.environ.get("BACKUP_DRIVE", r"G:\내 드라이브\_backup\simplifier-private-repos")
STATE = os.environ.get("BACKUP_STATE", r"C:\work\_ops\backup")
KEEP = 14

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def git(*args, cwd=None, check=True):
    r = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if check and r.returncode != 0:
        raise RuntimeError(f"git {' '.join(args[:2])} 실패: {r.stderr.strip()[:300]}")
    return r.stdout.strip()


def remote_main(repo):
    out = git("ls-remote", f"https://github.com/{OWNER}/{repo}.git", "refs/heads/main")
    return out.split()[0] if out else ""


def prune(folder, repo):
    files = sorted(glob.glob(os.path.join(folder, f"{repo}-*.bundle")))
    for old in files[:-KEEP]:
        os.remove(old)


def backup_one(repo, today):
    mirror = os.path.join(ROOT, "mirror", f"{repo}.git")
    os.makedirs(os.path.dirname(mirror), exist_ok=True)
    if not os.path.isdir(mirror):
        git("clone", "--mirror", f"https://github.com/{OWNER}/{repo}.git", mirror)
    for k, v in (("gc.auto", "0"), ("gc.pruneExpire", "never"), ("core.logAllRefUpdates", "always")):
        git("config", k, v, cwd=mirror)
    git("remote", "update", cwd=mirror)  # --prune을 쓰지 않아 원격에서 지워진 브랜치도 미러에 남는다
    want = remote_main(repo)
    have = git("rev-parse", "refs/heads/main", cwd=mirror)
    if want != have:
        raise RuntimeError(f"{repo}: 미러 main({have[:8]})이 원격 main({want[:8]})과 다름")
    bdir = os.path.join(ROOT, "bundles")
    os.makedirs(bdir, exist_ok=True)
    bundle = os.path.join(bdir, f"{repo}-{today}.bundle")
    git("bundle", "create", bundle, "--all", cwd=mirror)
    git("bundle", "verify", bundle, cwd=mirror)
    prune(bdir, repo)
    os.makedirs(DRIVE, exist_ok=True)
    shutil.copy2(bundle, os.path.join(DRIVE, os.path.basename(bundle)))
    prune(DRIVE, repo)
    return have, os.path.getsize(bundle)


def main():
    if "--restore-test" in sys.argv:
        return restore_test()
    today = datetime.date.today().isoformat()
    lines, failed = [], False
    for repo in REPOS:
        try:
            sha, size = backup_one(repo, today)
            lines.append(f"OK {repo} main={sha[:10]} bundle={size}B")
        except Exception as e:  # 한 저장소 실패가 다른 저장소를 막지 않게
            failed = True
            lines.append(f"FAIL {repo} {e}")
    print("\n".join(lines))
    if not failed:
        os.makedirs(STATE, exist_ok=True)
        with open(os.path.join(STATE, "last-run.txt"), "w", encoding="utf-8") as f:
            f.write(datetime.datetime.now().isoformat(timespec="seconds") + "\n" + "\n".join(lines) + "\n")
    return 1 if failed else 0


def restore_test():
    ok = True
    for where, folder in (("PC", os.path.join(ROOT, "bundles")), ("드라이브", DRIVE)):
        for repo in REPOS:
            files = sorted(glob.glob(os.path.join(folder, f"{repo}-*.bundle")))
            if not files:
                print(f"FAIL {where} {repo}: 번들 없음")
                ok = False
                continue
            tmp = tempfile.mkdtemp(prefix="restore-")
            try:
                git("clone", files[-1], os.path.join(tmp, "r"))
                got = git("rev-parse", "HEAD", cwd=os.path.join(tmp, "r"))
                want = remote_main(repo)
                files_n = len(git("ls-files", cwd=os.path.join(tmp, "r")).splitlines())
                same = got == want
                ok &= same
                print(f"{'OK' if same else 'DIFF'} {where} {repo}: 복원 HEAD={got[:10]} 원격 main={want[:10]} 추적 파일 {files_n}개 ({os.path.basename(files[-1])})")
            finally:
                shutil.rmtree(tmp, ignore_errors=True)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
