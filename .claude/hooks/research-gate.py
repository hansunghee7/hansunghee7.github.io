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
if data.get("tool_name") != "Agent":
    sys.exit(0)
ti = data.get("tool_input") or {}
kind = str(ti.get("subagent_type") or "general-purpose")
prompt = str(ti.get("prompt") or "")
if "[제미나이 불가:" in prompt:
    sys.exit(0)
research = re.search(r"리서치|벤치마킹|웹\s*조사|자료\s*수집|출처|research|benchmark", prompt, re.I)
if kind == "collector" or (kind in ("general-purpose", "claude") and research):
    sys.stderr.write(
        "[리서치 관문] 웹 리서치는 클로드 서브에이전트가 아니라 구글 검색 연동 제미나이 API로 돌립니다(사장님 규칙 9/24, 관문 9/26). "
        "여러 질문은 병렬 호출로 한 번에. 제미나이로 안 되는 이유가 있으면 프롬프트에 \"[제미나이 불가: 이유]\"를 적고 다시 부르세요.")
    sys.exit(2)
sys.exit(0)
