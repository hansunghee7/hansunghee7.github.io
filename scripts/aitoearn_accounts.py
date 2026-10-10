"""AItoEarn에 연결된 채널 계정 목록을 읽기 전용으로 조회한다(N17 스레드 accountId 확인용, 2026-10-11).

왜: 큐 항목에 넣을 accountId(예: threads_xxx)를 저장소 어디에도 기록해 두지 않아, 스레드 예약 자동화가 막혀 있었다.
키(AITOEARN_API_KEY)는 GitHub Secret에만 있으므로 워크플로(aitoearn-accounts.yml)에서 실행한다.
출력은 플랫폼·accountId·이름 앞부분만 낸다(토큰·키는 출력하지 않는다). 쓰기 요청은 하지 않는다.
목록 API 경로를 문서에서 못 찾아 후보 GET 경로를 차례로 시험하고, 각 경로의 HTTP 상태를 같이 보여 준다.
"""
import json
import os
import sys
import urllib.error
import urllib.request

API_BASE = "https://aitoearn.ai/api"
UA = "simplifier-publisher/1.0 (+https://simplifier.co.kr)"
CANDIDATES = ["/v2/channels/accounts", "/v2/channels/accounts/list", "/v2/accounts", "/v2/channels/account/list", "/v2/channels"]
SAFE_KEYS = ("platform", "type", "accountId", "id", "_id", "name", "nickname", "status")


def get(path, key):
    req = urllib.request.Request(API_BASE + path, headers={"X-Api-Key": key, "Accept": "application/json", "User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, json.load(r)
    except urllib.error.HTTPError as e:
        return e.code, None
    except Exception as e:  # 네트워크 오류도 상태로만 보고
        return type(e).__name__, None


def find_list(data):
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for v in data.values():
            r = find_list(v)
            if r:
                return r
    return []


def main():
    key = os.environ.get("AITOEARN_API_KEY")
    if not key:
        print("AITOEARN_API_KEY 없음")
        return 1
    found = False
    for p in CANDIDATES:
        st, data = get(p, key)
        items = find_list(data) if data else []
        print(f"GET {p} -> {st}, 항목 {len(items)}")
        for it in items:
            if isinstance(it, dict):
                print("  ", {k: str(it[k])[:40] for k in SAFE_KEYS if k in it})
                found = True
        if found:
            break
    return 0 if found else 2


if __name__ == "__main__":
    sys.exit(main())
