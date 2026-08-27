"""
cinaeng/ux-book-tracker가 매일 새벽 4시(KST)에 수집하는 「UX의 언어들」
베스트셀러 순위 데이터(data/history.json)를 그대로 미러링한다.

우리가 다시 스크래핑하지 않는 이유: 그 트래커가 이미 매일 안정적으로 돌고
있어서, 같은 걸 두 번 만들면 유지보수만 늘어난다. 대신 그 결과물을 서버
사이드에서 복사해온다 -- 그 파일은 CORS 헤더(access-control-allow-origin)가
없어서(확인함) 브라우저에서 직접 fetch할 수 없기 때문에, 여기서 대신 받아
우리 저장소에 커밋해둔다.

절대 그냥 덮어쓰지 않는다 -- 원본이 일시적으로 404/빈 응답을 주면 우리 쪽
히스토리가 통째로 날아갈 수 있어서, JSON 파싱 + "비어있지 않은 리스트"
검증을 통과했을 때만 파일을 쓴다. 실패하면 기존 파일은 그대로 두고 경고만
남기고 정상 종료한다(이 스텝의 실패가 다른 커밋을 막으면 안 됨).
"""
import json
import sys
import urllib.request

SOURCE_URL = "https://cinaeng.github.io/ux-book-tracker/data/history.json"
OUT_PATH = "assets/data/ux-book-history.json"


def fetch_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main():
    try:
        data = fetch_json(SOURCE_URL)
    except Exception as e:
        print(f"미러링 실패, 기존 파일 유지: {e}", file=sys.stderr)
        return

    if not isinstance(data, list) or not data:
        print("원본이 빈 리스트/예상과 다른 형식이라 건너뜀", file=sys.stderr)
        return

    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"UX의 언어들 히스토리 미러링 완료 — 총 {len(data)}개 레코드")


if __name__ == "__main__":
    main()
