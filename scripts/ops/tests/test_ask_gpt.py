"""ask_gpt.py 시험: 네트워크 없이 모의 호출로 상한·비밀 거부·토큰 기록·키 비출력을 확인한다.

실행: python -m pytest scripts/ops/tests/test_ask_gpt.py -v
"""
import importlib.util
import json
from pathlib import Path

import pytest

OPS = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("ask_gpt_under_test", OPS / "ask_gpt.py")
ag = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ag)

FAKE_KEY = "FAKEKEY-0123456789"
REPLY = {"output": [{"type": "reasoning"}, {"type": "message", "content": [{"text": "1. 가"}, {"text": " 나"}]}],
         "usage": {"input_tokens": 11, "output_tokens": 222, "output_tokens_details": {"reasoning_tokens": 150}}}


@pytest.fixture
def env(tmp_path, monkeypatch):
    f = tmp_path / "secret.env"
    f.write_text("OTHER=1\nAZURE_OPENAI_API_KEY=" + FAKE_KEY + "\n", encoding="utf-8")
    monkeypatch.setenv("AZURE_ENV_FILE", str(f))
    monkeypatch.setenv("AZURE_USAGE_LOG", str(tmp_path / "usage.jsonl"))
    monkeypatch.delenv("AZURE_GPT_DAILY_CALLS", raising=False)
    return tmp_path


def fake(key, text, max_tokens):
    fake.seen = (text, max_tokens)
    return REPLY


def test_success_joins_message_text_and_logs_tokens(env):
    out = ag.run("마야", "ideas", "숏폼 소재", caller=fake)
    assert out == "1. 가 나"
    assert "5개" in fake.seen[0] and fake.seen[1] == 4000
    rec = json.loads((env / "usage.jsonl").read_text(encoding="utf-8").splitlines()[0])
    assert (rec["who"], rec["task"], rec["input_tokens"], rec["output_tokens"], rec["reasoning_tokens"], rec["ok"]) == \
           ("마야", "ideas", 11, 222, 150, True)
    assert "1. 가" not in json.dumps(rec, ensure_ascii=False)  # 답 본문은 기록하지 않음


def test_secret_in_prompt_rejected_without_call(env):
    def boom(*a):
        raise AssertionError("호출되면 안 됨")
    with pytest.raises(ag.AskError) as e:
        ag.run("핏", "ideas", "내 password 는 abc", caller=boom)
    assert e.value.code == 3
    assert not (env / "usage.jsonl").exists()


def test_daily_cap_rejects(env, monkeypatch):
    monkeypatch.setenv("AZURE_GPT_DAILY_CALLS", "2")
    ag.run("마야", "ideas", "a", caller=fake)
    ag.run("마야", "ideas", "b", caller=fake)
    with pytest.raises(ag.AskError) as e:
        ag.run("마야", "ideas", "c", caller=fake)
    assert e.value.code == 5


def test_missing_key(env, monkeypatch):
    monkeypatch.setenv("AZURE_ENV_FILE", str(env / "none.env"))
    with pytest.raises(ag.AskError) as e:
        ag.run("마야", "ideas", "a", caller=fake)
    assert e.value.code == 4


def test_failure_logged_and_key_not_leaked(env, capsys):
    def bad(key, text, max_tokens):
        raise RuntimeError("boom " + key)
    with pytest.raises(ag.AskError) as e:
        ag.run("마야", "ideas", "a", caller=bad)
    assert e.value.code == 6 and FAKE_KEY not in e.value.msg
    rec = json.loads((env / "usage.jsonl").read_text(encoding="utf-8").splitlines()[0])
    assert rec["ok"] is False


def test_main_never_prints_key(env, monkeypatch, capsys):
    monkeypatch.setattr(ag, "call_azure", fake)
    out = env / "ans.md"
    rc = ag.main(["--who", "마야", "--task", "ideas", "--out", str(out), "주제"])
    cap = capsys.readouterr()
    assert rc == 0
    assert FAKE_KEY not in cap.out + cap.err
    assert out.read_text(encoding="utf-8") == "1. 가 나"
    assert FAKE_KEY not in (env / "usage.jsonl").read_text(encoding="utf-8")


def test_empty_answer_is_failure(env):
    empty = lambda k, t, m: {"output": [{"type": "reasoning"}], "usage": {}}
    with pytest.raises(ag.AskError) as e:
        ag.run("마야", "ideas", "a", caller=empty)
    assert e.value.code == 6
