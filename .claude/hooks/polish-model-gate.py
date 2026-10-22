"""PreToolUse(Agent) 훅(2026-10-14 핏, 사장님 지시): 쇼츠·롱폼 대본 윤문을 서브에이전트(소넷 등)에 맡기지 못하게 막는다.
윤문은 제미나이 3.8 고정이다(사장님 2026-10-05·10-14). 명령은 shorts-lab `python tools/sheet/polish_38.py <편ID> <초안> <출력>`.
대상: 프롬프트에 '윤문'이 있고 polish_request·SCRIPT_POLISH_GUIDE·narration 같은 대본 문맥이 함께 있는 서브에이전트 발주. 파싱 실패는 통과(fail-open)."""
import json, re, sys
try:
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass
try:
    data = json.loads(sys.stdin.buffer.read().decode("utf-8"))
except Exception:
    sys.exit(0)
ti = data.get("tool_input") or {}
text = f"{ti.get('prompt', '')} {ti.get('description', '')}"
if "윤문" in text and re.search(r"polish_request|SCRIPT_POLISH_GUIDE|narration|대본", text) and not re.search(r"polish_38|제미나이\s*3\.8", text):
    sys.stderr.write("[윤문 모델 관문] 대본 윤문은 서브에이전트(소넷 등)가 아니라 제미나이 3.8로 합니다(사장님 2026-10-05·10-14 고정). "
                     "shorts-lab에서 `python tools/sheet/polish_38.py <편ID> <초안파일> <출력파일>`을 실행한 뒤 factcheck_script.py로 이어 가세요. "
                     "본 세션이 문장을 직접 고쳐 윤문을 대신하는 것도 같은 위반입니다.\n")
    sys.exit(2)
sys.exit(0)
