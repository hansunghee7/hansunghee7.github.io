"""fetch_clarity 400 재시도 시험 (urllib을 가짜로 바꿔 실제 API를 호출하지 않는다)."""
import io
import os
import sys
import urllib.error
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
import fetch_clarity as fc


class Resp:
    def __init__(self, b):
        self.b = b

    def read(self):
        return self.b

    def __enter__(self):
        return self

    def __exit__(self, *a):
        pass


def err400():
    return urllib.error.HTTPError("u", 400, "Bad", {}, io.BytesIO(b'{"m":"bad token ' + b"A" * 40 + b'"}'))


def test_400_then_200():
    seq = [err400(), Resp(b'[{"x":1}]')]
    sleeps = []

    def fake(req, timeout=0):
        r = seq.pop(0)
        if isinstance(r, Exception):
            raise r
        return r

    with mock.patch.object(fc.urllib.request, "urlopen", fake):
        out = fc.call_api_retry_400("t", 1, sleep=sleeps.append)
    assert out == [{"x": 1}] and sleeps == [5]


def test_400_then_400(capsys):
    seq = [err400(), err400()]

    def fake(req, timeout=0):
        raise seq.pop(0)

    with mock.patch.object(fc.urllib.request, "urlopen", fake):
        try:
            fc.call_api_retry_400("t", 1, sleep=lambda s: None)
            assert False
        except urllib.error.HTTPError as e:
            assert e.code == 400
    o = capsys.readouterr().out
    assert "시도 2/2" in o and "AAAA" not in o
