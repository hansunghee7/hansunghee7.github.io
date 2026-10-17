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
import hashlib
import json
import mimetypes
import os
import re
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


def final_body(content):
    """실제로 게시되는 본문: 제목이 있으면 본문 첫 줄로 붙인다(register와 글자 수 관문이 같은 값을 보게 한다)."""
    title = (content.get("title") or "").strip()
    body = content.get("body") or ""
    if title and not body.lstrip().startswith(title):
        return f"{title}\n\n{body}"
    return body


THREADS_MAX = 500  # AItoEarn threads.constants.ts maxBodyLength/maxTotalTextLength. 한 게시 = 한 글(답글 이어붙이기 미지원)


def register(item, api_key):
    try:
        attach_media(item, api_key)
    except Exception as e:
        return False, f"이미지 업로드 실패: {type(e).__name__}: {e}"
    content = {k: v for k, v in item["content"].items() if k != "media_source"}
    # AItoEarn은 페이스북·링크드인·인스타그램에서 title 칸을 쓰지 않고 body만
    # 게시한다(yikart/aitoearn facebook-publish.provider.ts는 message=body,
    # linkedin-publish.provider.ts는 commentary=body). 2026-09-24 인스타에 제목 없이
    # 올라간 것을 사장님이 발견. 사장님이 직접 올리던 모양(첫 줄 제목, 빈 줄, 본문)에
    # 맞춰 제목을 본문 첫 줄로 넣는다.
    title = (content.get("title") or "").strip()
    body = content.get("body") or ""
    if title and not body.lstrip().startswith(title):
        content["body"] = f"{title}\n\n{body}"
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


def policy_problem(item):
    """사장님 게시 정책을 어긴 항목이면 이유를, 아니면 None을 돌려준다.

    문서에만 있던 규칙이 세션마다 빠져 이미지 없는 글과 링크 2개 글이 실제로
    게시됐다(2026-10-02 사장님이 링크드인에서 발견). 그래서 등록 직전에 막는다.
    - 대표 이미지 필수(사장님 지시 2026-09-28): content.media_source가 비면 등록하지 않는다.
    - 콜투액션은 관련글 링크 1개만(사장님 지시 2026-09-30·10-02): 본문 URL이 2개 이상이면
      등록하지 않는다(원문 링크 "from https://..." 줄을 넣지 않는다).
    """
    content = item.get("content") or {}
    if not content.get("media_source"):
        return "대표 이미지(content.media_source)가 없습니다"
    if item.get("platform") == "threads":
        n = len(final_body(content))
        if n > THREADS_MAX:
            return f"스레드 본문이 {n}자입니다(제목 포함 {THREADS_MAX}자 이하만 가능, 답글 이어붙이기 미지원이라 요약본을 따로 써야 합니다)"
    # 본문 규칙(링크 1개·CTA·원문 줄 금지)의 정본은 scripts/sns/post_gate.py(모든 게시 경로 공용).
    # 큐 본문에는 제목이 따로 있어(final_body가 붙인다) 첫 줄 검사는 하지 않는다.
    sys.path.insert(0, str(Path(__file__).resolve().parent / "sns"))
    from post_gate import text_problems
    problems = text_problems(content.get("body") or "", channel=item.get("platform") or "")
    if problems:
        return problems[0]
    return image_check_problem(item)


IMAGE_SOURCES = ("unsplash", "nano-banana", "local-krea2")


def image_check_problem(item):
    """이미지 선정 조건 8개 채점 기록이 없거나 위조·불일치면 등록하지 않는다(2026-10-11 마야 사고, 9/19 KPT 7번 재발).

    조건 8개는 문서(질문하기_파이프라인.md 5-2절)에만 있어 세션마다 빠졌다. 큐 항목의 image_check.file이
    저장소 안 JSON 채점 파일을 가리켜야 하고, 그 파일이 아래를 모두 만족해야 한다(덱스 독립 검증 10/11 지적 반영).
      queue_id==항목 id, source 3종 중 하나, idea 10자 이상, conditions 1~8이 0/1, score==합계(6/8 이상, 1번 필수),
      image가 media_source에 있고 sha256이 실제 파일과 일치. 채점 파일은 `scripts/ops/maya_image_score.py`로 만든다.
    publishAt이 없거나 형식 오류면 막는다(실패 폐쇄). 2026-10-12 전 게시분은 컨펌이 끝난 항목이라 제외한다.
    """
    root = Path(__file__).resolve().parents[1]
    try:
        day = datetime.fromisoformat(str(item.get("publishAt")).replace("Z", "+00:00")).date().isoformat()
    except Exception:
        return f"publishAt({item.get('publishAt')!r}) 형식 오류: 이미지 채점 관문을 적용할 수 없어 막습니다"
    if day < "2026-10-12":
        return None
    f = str((item.get("image_check") or {}).get("file") or "")
    if not f:
        return "image_check.file(이미지 조건 8개 채점 파일)이 없습니다"
    try:
        p = (root / f).resolve()
        p.relative_to(root.resolve())
        if not p.is_file() or p.suffix != ".json":
            return f"image_check.file({f})이 저장소 안 JSON 파일이 아닙니다"
        d = json.loads(p.read_text(encoding="utf-8"))
        conds = d.get("conditions") or {}
        vals = [conds.get(str(i)) for i in range(1, 9)]
        if any(v not in (0, 1) for v in vals):
            return "채점 파일 conditions 1~8이 모두 0 또는 1이어야 합니다"
        total = sum(vals)
        if d.get("queue_id") != item.get("id"):
            return "채점 파일 queue_id가 이 큐 항목 id와 다릅니다(다른 글의 채점 재사용 금지)"
        if d.get("source") not in IMAGE_SOURCES:
            return f"채점 파일 source는 {IMAGE_SOURCES} 중 하나여야 합니다"
        if len(str(d.get("idea") or "").strip()) < 10:
            return "채점 파일 idea(빅아이디어 한 문장)가 10자 미만입니다"
        if d.get("score") != f"{total}/8" or total < 6 or vals[0] != 1:
            return f"채점 점수 {total}/8 (6/8 이상이고 1번 빅아이디어 조건이 충족돼야 합니다)"
        img = str(d.get("image") or "")
        if img not in (item.get("content", {}).get("media_source") or []):
            return "채점한 이미지가 content.media_source에 없습니다"
        ip = (root / img).resolve()
        ip.relative_to(root.resolve())
        if hashlib.sha256(ip.read_bytes()).hexdigest() != d.get("sha256"):
            return "채점한 이미지와 실제 게시 이미지가 다릅니다(sha256 불일치)"
    except Exception as e:
        return f"이미지 채점 검증 오류(실패 폐쇄): {type(e).__name__}: {e}"
    return None


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
        problem = policy_problem(item)
        if problem:
            item["status"] = "error"
            item["note"] = f"정책 관문: {problem}"
            print(f"[BLOCK] {item['id']}: {problem}")
            changed = True
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
