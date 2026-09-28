"""N70 1단계: FACEBOOK_PAGE_TOKEN이 어느 페이지를 가리키는지 확인만 한다.
id/name은 비밀값이 아니라 로그에 찍어도 안전하다 -- 토큰 값 자체는 절대 출력하지 않는다.
"""
import json
import os
import urllib.error
import urllib.request

TOKEN = os.environ["FACEBOOK_PAGE_TOKEN"]
API = "https://graph.facebook.com/v26.0"


def get(path, **params):
    params["access_token"] = TOKEN
    qs = "&".join(f"{k}={urllib.parse.quote(str(v))}" for k, v in params.items())
    url = f"{API}/{path}?{qs}"
    try:
        with urllib.request.urlopen(url, timeout=20) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        return {"error": json.load(e)}


import urllib.parse  # noqa: E402

identity = get("me", fields="id,name")
print("페이지 정체성:", json.dumps(identity, ensure_ascii=False))

posts = get("me/posts", fields="id,created_time,likes.summary(true),comments.summary(true),permalink_url", limit=5)
if "data" in posts:
    print(f"최근 게시물 {len(posts['data'])}건 조회 성공")
    for p in posts["data"][:3]:
        likes = p.get("likes", {}).get("summary", {}).get("total_count")
        comments = p.get("comments", {}).get("summary", {}).get("total_count")
        print(f"  - {p.get('id')} likes={likes} comments={comments} {p.get('permalink_url')}")
else:
    print("게시물 조회 실패:", json.dumps(posts, ensure_ascii=False))
