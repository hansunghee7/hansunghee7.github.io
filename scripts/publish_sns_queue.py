"""assets/data/sns_publish_queue.json에서 사장님이 채팅으로 승인한(approved_by가
채워진) status:"pending" 항목만 AItoEarn 발행 흐름 API로 등록한다(실제 게시 시각은
각 항목의 publishAt, AItoEarn 서버가 그 시각에 발행한다. 이 스크립트는 "등록"만
하고 "지금 당장 게시"는 하지 않는다). approved_by가 비어 있는 항목은 건너뛴다.

키는 환경변수 AITOEARN_API_KEY로만 받는다(화면·로그에 출력하지 않는다).
GitHub Actions에서는 시크릿 AITOEARN_API_KEY로 주입한다.

사용법: AITOEARN_API_KEY=... python scripts/publish_sns_queue.py
"""
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

QUEUE_PATH = Path("assets/data/sns_publish_queue.json")
API_URL = "https://aitoearn.ai/api/v2/channels/publish/flows"
UA = "simplifier-publisher/1.0 (+https://simplifier.co.kr)"


def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")


def register(item, api_key):
    body = json.dumps({
        "content": item["content"],
        "publishAt": item["publishAt"],
        "items": [{"platform": item["platform"], "accountId": item["accountId"], "option": item.get("option", {})}],
    }).encode("utf-8")
    req = urllib.request.Request(
        API_URL, body,
        headers={
            "X-Api-Key": api_key,
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": UA,
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.load(r)
    except urllib.error.HTTPError as e:
        return False, f"HTTP {e.code}: {e.read().decode('utf-8', 'ignore')[:300]}"
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"

    if data.get("code") == 0:
        flow_id = (data.get("data") or {}).get("flowId") or (data.get("data") or {}).get("id")
        return True, flow_id
    return False, f"full={json.dumps(data, ensure_ascii=False)[:800]}"


def main():
    api_key = os.environ.get("AITOEARN_API_KEY")
    if not api_key:
        sys.exit("AITOEARN_API_KEY 환경변수가 없습니다.")

    queue = json.loads(QUEUE_PATH.read_text(encoding="utf-8"))
    changed = False
    for item in queue:
        if item.get("status") != "pending":
            continue
        if not item.get("approved_by"):
            print(f"[SKIP] {item['id']}: approved_by 없음(사장님 승인 인용 필요)")
            continue
        ok, result = register(item, api_key)
        if ok:
            item["status"] = "registered"
            item["flowId"] = result
            item["registered_at"] = now_iso()
            print(f"[OK] {item['id']} -> flowId={result}")
        else:
            item["status"] = "error"
            item["note"] = str(result)
            print(f"[FAIL] {item['id']}: {result}")
        changed = True

    if changed:
        QUEUE_PATH.write_text(json.dumps(queue, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    else:
        print("등록 대기 중인 항목이 없습니다.")


if __name__ == "__main__":
    main()
