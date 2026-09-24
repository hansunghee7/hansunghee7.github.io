"""assets/data/sns_publish_queue.json에서 사장님이 채팅으로 승인한(approved_by가
채워진) status:"pending" 항목만 AItoEarn 발행 흐름 API로 등록한다(실제 게시 시각은
각 항목의 publishAt, AItoEarn 서버가 그 시각에 발행한다. 이 스크립트는 "등록"만
하고 "지금 당장 게시"는 하지 않는다). approved_by가 비어 있는 항목은 건너뛴다.

키는 환경변수 AITOEARN_API_KEY로만 받는다(화면·로그에 출력하지 않는다).
GitHub Actions에서는 시크릿 AITOEARN_API_KEY로 주입한다.

이미지: 항목의 content.media_source에 저장소 경로(예: "log_assets/images/a.jpg")나
URL을 적어 두면, 등록 전에 AItoEarn 업로드 API로 올려 content.media에 AItoEarn
자체 도메인 URL을 채운다. AItoEarn은 media.url에 우리 사이트 도메인을 쓰면
disallowed_domain으로 거부하기 때문이다(2026-09-24 실측). 업로드 절차는 AItoEarn
오픈소스(yikart/aitoearn relay-client.service.ts)와 같다: uploadSign → PUT → confirm.

사용법: AITOEARN_API_KEY=... python scripts/publish_sns_queue.py
"""
import json
import mimetypes
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

QUEUE_PATH = Path("assets/data/sns_publish_queue.json")
API_BASE = "https://aitoearn.ai/api"
API_URL = API_BASE + "/v2/channels/publish/flows"
UA = "simplifier-publisher/1.0 (+https://simplifier.co.kr)"


def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")


def call(path, payload, api_key):
    req = urllib.request.Request(
        API_BASE + path, json.dumps(payload).encode("utf-8"),
        headers={"X-Api-Key": api_key, "Content-Type": "application/json",
                 "Accept": "application/json", "User-Agent": UA},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.load(r)
    if data.get("code") != 0:
        raise RuntimeError(f"{path}: {json.dumps(data, ensure_ascii=False)[:300]}")
    return data.get("data") or {}


def read_source(src):
    if src.startswith("http://") or src.startswith("https://"):
        req = urllib.request.Request(src, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.read(), os.path.basename(urllib.parse.urlparse(src).path)
    path = Path(src)
    return path.read_bytes(), path.name


def upload_media(src, api_key):
    blob, filename = read_source(src)
    sign = call("/assets/uploadSign",
                {"filename": filename, "type": "publishMedia", "size": len(blob)}, api_key)
    if not sign.get("uploadUrl"):
        raise RuntimeError(f"uploadSign에 uploadUrl 없음: {list(sign)}")
    ctype = mimetypes.guess_type(filename)[0] or "application/octet-stream"
    put = urllib.request.Request(sign["uploadUrl"], blob,
                                 headers={"Content-Type": ctype}, method="PUT")
    with urllib.request.urlopen(put, timeout=60):
        pass
    call(f"/assets/{sign['id']}/confirm", {}, api_key)
    return sign["url"]


def attach_media(item, api_key):
    content = item["content"]
    sources = content.get("media_source") or []
    if not sources or content.get("media"):
        return
    content["media"] = [{"url": upload_media(src, api_key)} for src in sources]


def register(item, api_key):
    try:
        attach_media(item, api_key)
    except Exception as e:
        return False, f"이미지 업로드 실패: {type(e).__name__}: {e}"
    content = {k: v for k, v in item["content"].items() if k != "media_source"}
    body = json.dumps({
        "content": content,
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
