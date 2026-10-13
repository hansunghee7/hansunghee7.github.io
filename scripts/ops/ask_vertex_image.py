#!/usr/bin/env python3
"""이미지를 함께 보내 제미나이 3.8에게 묻는 경로(2026-10-13 마야). ask_vertex.py의 이미지 입력판.

왜: 이미지 후보를 마야가 직접 채점하면 자기 평가라서(사장님 10/13 "후킹 이미지 조건이 맞게 나왔는지 점검"), 글 맥락을 모르는 제미나이에게 조건표와
이미지만 주고 따로 채점시킨다. 이미지 검수 판정은 제미나이·솔라 모델에 한해 허용(CLAUDE.md, 사장님 확정 2026-09-22).
인증·회사/개인 프로젝트 선택은 ask_vertex.py와 같은 gcloud 토큰을 쓴다(키 값 없음). 질문에 고객 정보·비밀값을 넣지 않는다.

사용: python scripts/ops/ask_vertex_image.py <질문파일> <출력파일> 이미지1.jpg [이미지2.jpg ...] [--model gemini-3.8-flash] [--who 마야]
종료 코드: 0 성공 / 2 호출 실패
"""
import argparse
import base64
import json
import mimetypes
import sys
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ask_vertex as av  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("q")
    ap.add_argument("out")
    ap.add_argument("images", nargs="+")
    ap.add_argument("--model", default="gemini-3.8-flash")
    ap.add_argument("--who", default="마야")
    a = ap.parse_args()
    parts = [{"text": Path(a.q).read_text(encoding="utf-8")}]
    for i, p in enumerate(a.images, 1):
        mt = mimetypes.guess_type(p)[0] or "image/jpeg"
        parts.append({"text": f"[이미지 {i}] 파일: {Path(p).name}"})
        parts.append({"inlineData": {"mimeType": mt, "data": base64.b64encode(Path(p).read_bytes()).decode()}})
    body = {"contents": [{"role": "user", "parts": parts}]}
    proj, tok = av.COMPANY_PROJECT, av.token(av.COMPANY_ACCOUNT)
    if not tok:
        proj, tok = av.PROJECT, av.token()
    url = f"https://aiplatform.googleapis.com/v1/projects/{proj}/locations/{av.REGION}/publishers/google/models/{a.model}:generateContent"
    req = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"),
                                 headers={"Authorization": "Bearer " + tok, "Content-Type": "application/json"})
    try:
        r = json.loads(urllib.request.urlopen(req, timeout=300).read())
    except urllib.error.HTTPError as e:
        print(f"호출 실패 HTTP {e.code}: {e.read().decode('utf-8', 'replace')[:300]}", file=sys.stderr)
        return 2
    cand = (r.get("candidates") or [{}])[0]
    text = "".join(p.get("text", "") for p in cand.get("content", {}).get("parts", []))
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(text, encoding="utf-8")
    print(f"답 저장: {a.out} ({len(text)}자, 청구 {proj})", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
