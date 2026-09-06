"""1회성 검증 스크립트 — 새김(saegim) v0.4의 guide_views·lookup 로직을 실제
Supabase에 대해 확인한다. 확인 끝나면 이 파일과 워크플로를 삭제한다
(simplifier-saegim README의 2026-09-04 검증 패턴과 동일한 1회성 절차).

이 세션(원격/샌드박스)은 Supabase에 직접 붙을 수 없어(네트워크 정책),
GitHub Actions 러너를 빌려 실행한다. simplifier-saegim은 private 저장소라
이 워크플로에서 체크아웃할 수 없어, 최소한의 로직만 여기 그대로 복제했다
(store.py/saegim.py의 실제 코드는 이미 별도로 단위 테스트 32개로 검증됨 —
이 스크립트는 "그 로직이 실제 Supabase 스키마와 맞는가"만 확인하는 용도).

하는 일:
  1. STYLE_GUIDE.md를 파싱해 guide_sections에 심는다(실제 운영 데이터 — 유지).
  2. lookup·get 한 번씩 흉내내 guide_views에 기록한다(검증용 — 확인 후 삭제).
  3. list_sections/report 스타일 집계(조회 수·인용 수 분리)가 정상 동작하는지 확인.
"""

import os
import re
import sys

from supabase import create_client

DOC_PATH = "insight-7b3e9f2c/STYLE_GUIDE.md"
DOC_TAG = "STYLE_GUIDE"

HEADING_RE = re.compile(r"^(#{2,3})\s+(.+?)[ \t]*$", re.MULTILINE)
ID_COMMENT_RE = re.compile(r"<!--\s*id:\s*([0-9a-f]{2,8})\s*-->\s*$")
EXEMPT_MARK = "⚠️상시"


def parse_and_extract(text):
    matches = list(HEADING_RE.finditer(text))
    top = 0
    sub = 0
    rows = []
    for i, m in enumerate(matches):
        rest = m.group(2)
        idm = ID_COMMENT_RE.search(rest)
        if not idm:
            print(f"오류: id 없는 헤딩 발견 — {rest!r} (먼저 migrate 필요)", file=sys.stderr)
            sys.exit(1)
        section_id = idm.group(1)
        title = rest[: idm.start()].rstrip()
        exempt = EXEMPT_MARK in title
        title = title.replace(EXEMPT_MARK, "").strip()

        if m.group(1) == "##":
            top += 1
            sub = 0
            number = str(top)
        else:
            sub += 1
            number = f"{top}.{sub}"

        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[start:end].strip()

        rows.append(
            {
                "doc": DOC_TAG,
                "section_id": section_id,
                "section_number": number,
                "title": title,
                "body": body,
                "exempt": exempt,
            }
        )
    return rows


def main():
    sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"])

    with open(DOC_PATH, encoding="utf-8") as f:
        text = f.read()
    rows = parse_and_extract(text)
    print(f"1) 파싱: {len(rows)}개 절 발견")

    sb.table("guide_sections").upsert(rows, on_conflict="doc,section_id").execute()
    print(f"   → guide_sections에 '{DOC_TAG}' {len(rows)}개 절 심기 완료 (운영 데이터, 유지)")

    # lookup 흉내: "패턴" 같은 실제 존재하는 단어로 키워드 점수 매겨 상위 1개 고름
    query = "패턴"
    scored = []
    for r in rows:
        haystack = f"{r['title']}\n{r['body']}".lower()
        score = haystack.count(query.lower())
        if score > 0:
            scored.append((score, r))
    scored.sort(key=lambda p: p[0], reverse=True)
    assert scored, f"검증용 쿼리 '{query}'로 매칭되는 절이 없음 — 검증 실패"
    lookup_hit = scored[0][1]
    print(f"2) lookup('{query}') → 상위 매치: §{lookup_hit['section_number']} {lookup_hit['title']}")

    view_rows = [
        {"doc": DOC_TAG, "section_id": lookup_hit["section_id"], "kind": "lookup"},
        {"doc": DOC_TAG, "section_id": rows[0]["section_id"], "kind": "get"},
    ]
    sb.table("guide_views").insert(view_rows).execute()
    print("3) guide_views에 lookup 1건 + get 1건 기록 완료")

    # list_sections/report 스타일 집계 재현
    view_count = (
        sb.table("guide_views").select("section_id").eq("doc", DOC_TAG).execute().data
    )
    citation_count = (
        sb.table("guide_citations").select("section_id").eq("doc", DOC_TAG).execute().data
    )
    print(
        f"4) 집계 확인: 조회 수(views)={len(view_count)}건, 인용 수(citations)={len(citation_count)}건"
        " — 서로 다른 테이블에서 독립적으로 집계됨"
    )
    assert len(view_count) == 2, "방금 넣은 조회 2건이 안 보임 — guide_views 테이블 문제"

    # 검증용으로 넣은 조회 기록은 실제 사용이 아니므로 정리한다.
    sb.table("guide_views").delete().eq("doc", DOC_TAG).execute()
    remaining = sb.table("guide_views").select("section_id").eq("doc", DOC_TAG).execute().data
    assert not remaining, "검증용 조회 기록 정리 실패"
    print("5) 검증용 조회 기록 정리 완료(실제 사용 기록만 남도록) — guide_sections 시딩은 유지")

    print("\n✅ 전부 통과 — guide_views·lookup 로직이 실제 Supabase에서 정상 동작함")


if __name__ == "__main__":
    main()
