"""PreToolUse 훅(2026-09-26 탐, 사장님 "넣자"): 웹 리서치를 클로드 서브에이전트(collector 등)로 보내려 하면 멈추고
구글 검색 연동 제미나이 API로 돌리게 한다.
이유: 사장님 규칙 "리서치는 제미나이 API로"(9/24)가 기억 파일에만 있어 9/26 탐이 PIN 벤치마킹을 하이쿠 collector로 돌림
(클로드 토큰 약 5만). 문서 규칙은 세션이 바뀌면 빠지므로 도구 관문에 둔다(CLAUDE.md id:4e7b).
예외: 프롬프트에 "[제미나이 불가: 이유]"를 적으면 통과(로그인 필요한 페이지, 파일 저장이 필요한 수집 등).
"""
import json, re, sys
try:
    sys.stderr.reconfigure(encoding="utf-8")  # 윈도우 기본(cp949)로 쓰면 안내가 깨져 보임(9/26 실측)
except Exception:
    pass

try:
    data = json.loads(sys.stdin.buffer.read().decode("utf-8"))
except Exception:
    sys.exit(0)
tool = data.get("tool_name")
if tool in ("Bash", "PowerShell"):
    # 도구를 우회한 검색 연동 호출 차단(사장님 9/26 "질문할 내용을 한방에 모아서 ... 강제"): 질문마다 따로 부르면 횟수·비용만 샌다
    cmd = str((data.get("tool_input") or {}).get("command", ""))
    if re.search(r"google_?search|googleSearch", cmd) and "vertex_research.py" not in cmd and "[제미나이 불가:" not in cmd:
        sys.stderr.write("[리서치 관문] 검색 연동 제미나이는 vertex_research.py로만 부릅니다(질문을 모아 API 1회, 주제당 첫 조사+보충 1회). "
                         "사용: python C:/work/_ops/tools/vertex_research.py --topic \"주제\" \"질문1\" \"질문2\" ...")
        sys.exit(2)
    sys.exit(0)
if tool != "Agent":
    sys.exit(0)
ti = data.get("tool_input") or {}
kind = str(ti.get("subagent_type") or "general-purpose")
prompt = str(ti.get("prompt") or "")
if "[제미나이 불가:" in prompt:
    sys.exit(0)
research = re.search(r"리서치|벤치마킹|웹\s*조사|자료\s*수집|출처|research|benchmark", prompt, re.I)
if kind == "collector" or (kind in ("general-purpose", "claude") and research):
    sys.stderr.write(
        "[리서치 관문] 웹 리서치는 클로드 서브에이전트가 아니라 구글 검색 연동 제미나이로 돌립니다(사장님 규칙 9/24, 관문 9/26). "
        "도구: python C:/work/_ops/tools/vertex_research.py \"질문1\" \"질문2\" (Vertex AI, 무료 체험 크레딧, 검색 연동 9/26 실측 200). "
        "여러 질문은 병렬 호출로 한 번에. 제미나이로 안 되는 이유가 있으면 프롬프트에 \"[제미나이 불가: 이유]\"를 적고 다시 부르세요.")
    sys.exit(2)
sys.exit(0)
