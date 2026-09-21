"""로컬 LLM(올라마) 호출 공용 도우미.

무엇인가
--------
정기 위임 작업(주간 아카이브 후보 분류, 주간 변경 요약)이 공통으로 쓰는
"올라마에 질문 하나 던지고 답 받기" 함수 모음이다. 표준 라이브러리만 쓴다.

왜 이렇게 설계했나
------------------
1. 로컬 LLM은 가공(분류, 요약 초안)만 한다. 판정은 하지 않는다. 그래서 이 모듈은
   프롬프트를 만들지 않고, 호출·재시도·집계만 맡는다.
2. 모델은 새로 올리지 않는다. `pick_model()`이 지금 올라와 있는 모델(/api/ps)을
   먼저 찾고, 아무것도 안 올라와 있으면 설치된 모델(/api/tags) 중 기본 모델만 쓴다.
   헤르메스가 같은 GPU를 쓰므로 다른 모델로 바꾸거나 내리지 않는다.
3. `num_ctx` 등 실행 옵션은 지정하지 않는다(올라와 있는 모델의 설정을 바꿔 재적재를
   일으키지 않기 위해). 지정하는 옵션은 temperature 하나다.
4. 실패는 재시도 1회 후 LLMError로 올린다. 부르는 쪽이 그 항목만 "LLM 실패"로
   표기하고 계속 간다(한 항목 실패로 전체를 멈추지 않는다).
5. 호출 횟수는 모듈 전역 통계로 센다. 출력 파일 첫머리에 그대로 적어, 얼마나
   LLM에 기댔는지 눈으로 볼 수 있게 한다.
6. 로컬 주소(localhost)만 허용한다. 인터넷으로 나가는 호출을 코드 수준에서 막는다.
"""
import json
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone

OLLAMA = "http://localhost:11434"
DEFAULT_MODEL = "qwen2.5-coder:14b"
KST = timezone(timedelta(hours=9))

# 호출 통계(프로세스 안에서만 유효)
STATS = {"calls": 0, "ok": 0, "failed": 0}


class LLMError(RuntimeError):
    """재시도 후에도 실패한 호출."""


def now_kst() -> str:
    return datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S KST")


def _get_json(path: str, timeout: int = 10) -> dict:
    if not OLLAMA.startswith("http://localhost"):
        raise LLMError("로컬 올라마 주소만 허용")
    with urllib.request.urlopen(OLLAMA + path, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def pick_model() -> str:
    """지금 올라와 있는 모델 이름을 돌려준다. 없으면 설치된 기본 모델 이름.

    아무것도 올라와 있지 않으면 첫 호출 때 기본 모델이 적재된다(다른 모델은 쓰지 않음).
    """
    try:
        loaded = _get_json("/api/ps").get("models") or []
        if loaded:
            return loaded[0]["name"]
        installed = [m["name"] for m in _get_json("/api/tags").get("models") or []]
    except (urllib.error.URLError, OSError) as e:
        raise LLMError(f"올라마에 접속 못 함: {e}") from e
    if DEFAULT_MODEL in installed:
        return DEFAULT_MODEL
    raise LLMError(f"올라와 있는 모델이 없고 기본 모델({DEFAULT_MODEL})도 설치돼 있지 않음")


def chat(prompt: str, system: str | None = None, model: str | None = None,
         timeout: int = 300, retries: int = 1, temperature: float = 0.2) -> str:
    """올라마 /api/chat에 질문 하나를 보내고 답 문자열을 돌려준다(스트림 끔)."""
    model = model or pick_model()
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    body = json.dumps({
        "model": model, "messages": messages, "stream": False,
        "options": {"temperature": temperature},
    }).encode("utf-8")
    last = None
    for attempt in range(retries + 1):
        STATS["calls"] += 1
        try:
            req = urllib.request.Request(OLLAMA + "/api/chat", data=body,
                                         headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                text = json.loads(r.read().decode("utf-8"))["message"]["content"].strip()
            if not text:
                raise LLMError("빈 응답")
            STATS["ok"] += 1
            return text
        except (urllib.error.URLError, OSError, KeyError, ValueError, LLMError) as e:
            STATS["failed"] += 1
            last = e
            if attempt < retries:
                time.sleep(2)
    raise LLMError(f"{type(last).__name__}: {last}")


def stats_line() -> str:
    return f"{STATS['calls']}회 (성공 {STATS['ok']}, 실패 {STATS['failed']})"
