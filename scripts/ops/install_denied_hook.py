#!/usr/bin/env python3
"""사장님이 1회 실행: ~/.claude/settings.json 에 PermissionDenied 훅(denied_notify.py)을 합쳐 넣는다. 2026-10-03 탐 (대장 N126).
- 기본은 시험 실행(파일을 바꾸지 않고 바뀔 모습만 출력). --apply 를 붙이면 백업(settings.json.bak_denied) 후 저장.
- 이미 들어 있으면 아무것도 안 한다. 다른 설정은 건드리지 않는다. 에이전트는 이 파일을 실행하지 않는다(권한 설정은 사장님 몫).
사용: python scripts/ops/install_denied_hook.py [--apply] [--settings 경로]
"""
import json, os, shutil, sys

args = sys.argv[1:]
path = os.path.expanduser("~/.claude/settings.json")
if "--settings" in args:
    path = args[args.index("--settings") + 1]
cmd = "python C:/work/hansunghee7.github.io/scripts/ops/denied_notify.py"  # 공용 메인 폴더 고정 경로(워크트리 경로를 박지 않는다)
data = json.load(open(path, encoding="utf-8")) if os.path.exists(path) else {}
hooks = data.setdefault("hooks", {})
lst = hooks.setdefault("PermissionDenied", [])
if any(cmd in json.dumps(x) for x in lst):
    print("이미 등록되어 있음. 바꿀 것 없음"); sys.exit(0)
lst.append({"hooks": [{"type": "command", "command": cmd}]})
print("추가될 훅:", json.dumps(lst[-1], ensure_ascii=False))
if "--apply" not in args:
    print("(시험 실행: 파일은 바꾸지 않았음. 적용하려면 --apply)"); sys.exit(0)
if os.path.exists(path):
    shutil.copy(path, path + ".bak_denied")
json.dump(data, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
print("적용 완료:", path, "(백업 .bak_denied). 새 세션부터 적용될 수 있음")
