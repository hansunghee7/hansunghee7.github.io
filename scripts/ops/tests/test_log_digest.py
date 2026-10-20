"""log_digest: 마스킹·묶기·원인 후보 규칙 단위 시험(ssh 출력은 가짜 텍스트로 대체).

가짜 키 모양 문자열은 실행 중에 이어 붙여 만든다(파일에 키 모양 원문을 두지 않기 위해서).
"""
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import log_digest as d  # noqa: E402

UTC = timezone.utc
START = datetime(2026, 10, 18, 6, 0, tzinfo=UTC)
END = datetime(2026, 10, 19, 6, 0, tzinfo=UTC)
FAKE_GH = "gh" + "p_" + "Q" * 30          # 깃허브 토큰 모양(가짜)
FAKE_LONG = "Zx9" * 9                     # 27자 영숫자 덩어리(가짜)

# 10/19 reseed-guides 사례를 줄인 가짜 수집 결과(구PC 로그 형식 그대로)
RAW = """@@gate
2026-10-18 20:57:42 대기 avail=2240MB window=n
2026-10-18 21:02:42 대기 avail=2392MB window=n
2026-10-18 22:27:43 90분 대기 뒤 포기
2026-10-19 00:28:55 대기 avail=1900MB window=y
2026-10-19 02:27:46 통과(deploy, avail=1887MB) job=reseed
@@workers
W|20261018-205738|reseed-guides|reseed||2026-10-18 21:07:41|2026-10-18 21:12:21
W|20261019-002852|reseed-guides|reseed||2026-10-19 00:38:54|2026-10-19 00:43:34
W|20261019-022744|reseed-guides|reseed|Succeeded||2026-10-19 02:28:31
W|20261019-045927|measure|measure|Succeeded||2026-10-19 05:00:04
W|20261019-050000|ci|build|Failed||2026-10-19 05:03:00
@@keepalive
2026-10-16 14:40:01 시작
@@checks
== 2026-10-18T23:00:10+00:00 claude-md-polish-check rc=1
CLAUDE.md 폴리싱/반영 점검 이상:
- 폴리싱_기록.md: 마지막 폴리싱 20일 전(기준 14일)
== 2026-10-18T23:05:02+00:00 communication-watcher rc=0
== 2026-10-18T23:10:02+00:00 token-check rc=2
Traceback: auth failed token=FAKE_GH id=FAKE_LONG
@@backup_private
== 2026-10-18T18:30:01+00:00
OK simplifier-cxo-db main=d7d8301a48 bundle=3715227B
DONE
@@backup_hdd
@@backup_hdd_verify
== 2026-10-19T01:53:17+00:00
FAIL verify /srv/carvit-store/backup/x-2026-10-18.bundle
@@idle_guard
2026-10-19 01:08:01 UTC 유휴 크레딧 없음
2026-10-19 01:28:01 UTC 풀 ep51_flow: 남은 컷 0(정책 거절 []), 다음 편 큐가 비어 있어 핏이 다음 편을 올려야 합니다
@@hermes
Oct 19 01:11:35 goosolar python3[1]: 2026-10-19 01:11:35,440 WARNING 텔레그램 통신 일시 오류(자동 재시도): NetworkError
@@watch
점검 34건, 문제 1건, 알림 0건
@@now
MEM 2900
MOUNT /srv/carvit-store OK
MOUNT /srv/carvit-bulk NG
MOUNT /srv/carvit-fast OK
RUNNER OK
HERMES OK
@@end
""".replace("FAKE_GH", FAKE_GH).replace("FAKE_LONG", FAKE_LONG)


def items():
    ev, now = d.collect_events(d.split_sections(RAW))
    return d.group(ev, START, END), now


def test_mask_long_alnum_and_key_shapes():
    s = f"key={FAKE_LONG} tok={FAKE_GH} short=abc123 file=Worker_20261018-205738-utc.log"
    out = d.mask(s)
    assert FAKE_LONG not in out
    assert FAKE_GH[:6] not in out
    assert "short=abc123" in out                     # 짧은 값은 그대로
    assert "Worker_20261018-205738-utc.log" in out   # 파일 이름(밑줄·하이픈으로 끊김)은 남는다
    assert d.mask("a" * 23) == "a" * 23 and d.mask("a" * 24) == "***"


def test_mask_mail_and_ip_shapes():
    mail = "someone" + "@" + "example" + ".org"
    ip = ".".join(["10", "1", "2", "3"])
    out = d.mask(f"to {mail} from {ip}")
    assert mail not in out and ip not in out


def test_group_counts_and_last_success():
    it, _ = items()
    r = it["실행기 reseed-guides/reseed"]
    assert r.fails == 2
    assert r.last_ok == datetime(2026, 10, 19, 2, 28, 31, tzinfo=UTC)
    assert it["실행기 measure/measure"].fails == 0
    assert it["점검 communication-watcher"].fails == 0
    assert it["백업 HDD 검증"].fails == 1


def test_reseed_cause_is_gate_memory_wait():
    """10/19 사례: 취소된 reseed가 관문 메모리 3GB 미만 대기와 겹친다고 짚어야 한다."""
    it, _ = items()
    c = it["실행기 reseed-guides/reseed"].cause_list()[0]
    assert "3GB 미만" in c and "1900~2392MB" in c and "회피창" in c
    assert "2/2회" in c


def test_gate_giveup_is_demoted_to_echo_when_worker_explains_it():
    it, _ = items()
    g = it["실행기 관문(job_started)"]
    assert g.fails == 0 and g.warns == 1


def test_rule_table_causes():
    it, _ = items()
    assert "기한 경과" in it["점검 claude-md-polish-check"].cause_list()[0]
    assert "인증" in it["점검 token-check"].cause_list()[0]
    assert "번들 검증" in it["백업 HDD 검증"].cause_list()[0]
    assert "네트워크" in it["헤르메스 게이트웨이"].cause_list()[0]
    assert "큐가 비어" in it["공장 대기열"].cause_list()[0]
    # 관문 대기 흔적 없는 실패는 규칙표로 간다
    assert it["실행기 ci/build"].cause_list()[0].startswith("규칙표에 없는")


def test_render_is_short_masked_and_has_conclusion():
    it, now = items()
    text = d.render(it, now, START, END)
    lines = text.strip().splitlines()
    assert len(lines) <= d.MAX_LINES
    assert lines[1].startswith("결론: 실패")
    assert FAKE_GH[:6] not in text and FAKE_LONG not in text
    assert "NG: /srv/carvit-bulk" in text and "관문 3GB 미만" in text


def test_render_caps_at_20_lines():
    ev = [d.Event(f"작업{i}", START.replace(hour=12), "fail", "Traceback x") for i in range(40)]
    text = d.render(d.group(ev, START, END), d.parse_now([]), START, END)
    assert len(text.strip().splitlines()) <= d.MAX_LINES
    assert "외 " in text


def test_fetch_remote_sends_lf_bytes(monkeypatch):
    seen = {}

    def fake(cmd, **kw):
        seen["cmd"], seen["input"] = cmd, kw["input"]
        return SimpleNamespace(returncode=0, stdout=RAW.encode("utf-8"), stderr=b"")

    monkeypatch.setattr(subprocess, "run", fake)
    out = d.fetch_remote(START, END, "host")
    assert "@@end" in out
    assert isinstance(seen["input"], bytes) and b"\r\n" not in seen["input"]
    assert seen["cmd"][-3:-1] == ["20261018-060000", "20261019-060000"]


def test_main_writes_file_from_raw(tmp_path, monkeypatch):
    raw = tmp_path / "raw.txt"
    raw.write_text(RAW, encoding="utf-8")
    monkeypatch.setattr(d, "OUT_DIR", tmp_path / "out")
    assert d.main(["--end-kst", "2026-10-19 15:00", "--raw-in", str(raw)]) == 0
    f = tmp_path / "out" / "2026-10-19_1500.md"
    assert f.exists() and "reseed" in f.read_text(encoding="utf-8")
