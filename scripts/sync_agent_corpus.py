"""
블로그 글(log_assets/markdown)을 읽어서 조각내고 Voyage AI로 임베딩한 뒤
Supabase(simplifier-agent 프로젝트의 콘텐츠 창고)에 반영한다.

책 원고는 다루지 않는다 -- 이 저장소는 공개 저장소라, 책 내용은 절대
여기 들어오면 안 된다(별도로 로컬에서만 처리, simplifier-agent 폴더 참고).

내용이 바뀌지 않은 글은 건너뛴다(content_hash 비교) -- 매번 전체를 다시
돌리지 않기 위함. GitHub Actions에서 log_assets/markdown 변경 시 자동
실행되도록 붙어있다(.github/workflows/sync-agent-corpus.yml).

필요한 저장소 Secrets (Settings -> Secrets and variables -> Actions):
  SUPABASE_URL           simplifier-agent Supabase 프로젝트 URL
  SUPABASE_SERVICE_KEY   그 프로젝트의 service_role(관리자) 키
  VOYAGE_API_KEY         Voyage AI API 키
세 값 모두 대화로 주고받지 말고 이 화면에 사장님이 직접 붙여넣을 것.
"""
import functools
import hashlib
import os
import re
import sys
from pathlib import Path
from urllib.parse import quote

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")
print = functools.partial(print, flush=True)

BLOG_DIR = Path(__file__).resolve().parent.parent / "log_assets" / "markdown"

CHUNK_SIZE = 800
CHUNK_OVERLAP = 100

FOOTER_CUTOFF = '<div class="post-cta">'
CAT_SCRIPT_RE = re.compile(
    r"<!-- CAT_LINK_SCRIPT_START -->.*?<!-- CAT_LINK_SCRIPT_END -->", re.DOTALL
)
MEANINGLESS_ALT_RE = re.compile(r"^\d+\.(jpe?g|png|gif)$", re.IGNORECASE)


def clean_html_body(text: str) -> str:
    text = CAT_SCRIPT_RE.sub("", text)
    cutoff = text.find(FOOTER_CUTOFF)
    if cutoff != -1:
        text = text[:cutoff]

    def img_to_caption(match):
        alt = match.group(1)
        if not alt or MEANINGLESS_ALT_RE.match(alt.strip()):
            return ""
        return f"[이미지: {alt}]"

    text = re.sub(r'<img[^>]*alt="([^"]*)"[^>]*>', img_to_caption, text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n\s*\n+", "\n\n", text)
    return text.strip()


def content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def parse_blog_article(path: Path):
    text = path.read_text(encoding="utf-8")
    _, _, rest = text.partition("---\n")
    front_matter, _, body = rest.partition("\n---")
    meta = {}
    for line in front_matter.strip().splitlines():
        if ":" in line:
            key, _, value = line.partition(":")
            meta[key.strip()] = value.strip().strip("'\"")

    # CMS의 "공개 여부" 토글이 꺼진(초안) 글은 창고에 넣지 않는다 --
    # 기본값은 true(공개)이고, 명시적으로 false일 때만 제외한다.
    if meta.get("published", "true").lower() == "false":
        return None

    body = clean_html_body(body)
    return {
        "source_type": "blog",
        "title": meta.get("title", path.stem),
        "source_url": f"https://simplifier.co.kr/log_assets/markdown/{quote(path.stem + '.html')}",
        "body": body,
        "content_hash": content_hash(body),
        "metadata": {"category": meta.get("category"), "date": meta.get("date")},
    }


def chunk_text(text: str, size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP):
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    chunks = []
    current = ""
    for para in paragraphs:
        if len(current) + len(para) + 1 <= size:
            current = f"{current}\n{para}" if current else para
        else:
            if current:
                chunks.append(current)
            if len(para) > size:
                for i in range(0, len(para), size - overlap):
                    chunks.append(para[i : i + size])
                current = ""
            else:
                current = para
    if current:
        chunks.append(current)
    return chunks


def collect_documents():
    if not BLOG_DIR.exists():
        sys.exit(f"블로그 글 폴더를 못 찾음 - {BLOG_DIR}")
    docs = [parse_blog_article(p) for p in sorted(BLOG_DIR.glob("*.md"))]
    return [d for d in docs if d is not None]  # 비공개(초안) 글은 parse_blog_article이 None을 반환


def cleanup_unpublished(current_titles, supabase_client):
    """비공개로 전환됐거나 파일 자체가 없어진 글은 창고에서도 지운다."""
    existing = (
        supabase_client.table("content_chunks")
        .select("title")
        .eq("source_type", "blog")
        .execute()
    )
    existing_titles = {row["title"] for row in existing.data}
    stale = existing_titles - current_titles
    for title in stale:
        supabase_client.table("content_chunks").delete().eq(
            "source_type", "blog"
        ).eq("title", title).execute()
    if stale:
        print(f"비공개 전환/삭제된 글 {len(stale)}개 정리함")


def filter_changed_docs(docs, supabase_client):
    """여기서는 지우지 않는다 -- 미리 지우면 새 조각이 다 올라오기 전까지
    그 글이 검색에서 통째로 사라지는 구간이 생긴다. 지우는 건
    embed_and_upload_rows가 끝난 뒤 cleanup_stale_chunks에서 한다."""
    existing = (
        supabase_client.table("content_chunks")
        .select("source_type, title, metadata")
        .eq("source_type", "blog")
        .execute()
    )
    existing_hash = {}
    for row in existing.data:
        key = (row["source_type"], row["title"])
        if key not in existing_hash:
            existing_hash[key] = (row.get("metadata") or {}).get("content_hash")

    changed = [
        doc
        for doc in docs
        if existing_hash.get((doc["source_type"], doc["title"])) != doc["content_hash"]
    ]

    print(f"블로그 {len(docs)}개 중 새로 처리할 문서: {len(changed)}개")
    return changed


def cleanup_stale_chunks(rows, supabase_client):
    """새 조각을 다 올린 뒤에, 글이 짧아져서 필요 없어진 예전 조각만 지운다."""
    from collections import defaultdict

    new_counts = defaultdict(int)
    for row in rows:
        new_counts[(row["source_type"], row["title"])] += 1

    for (source_type, title), count in new_counts.items():
        supabase_client.table("content_chunks").delete().eq(
            "source_type", source_type
        ).eq("title", title).gte("chunk_index", count).execute()


def build_rows(docs):
    rows = []
    for doc in docs:
        metadata = dict(doc.get("metadata", {}))
        metadata["content_hash"] = doc["content_hash"]
        for idx, chunk in enumerate(chunk_text(doc["body"])):
            rows.append(
                {
                    "source_type": doc["source_type"],
                    "title": doc["title"],
                    "source_url": doc["source_url"],
                    "chunk_index": idx,
                    "content": chunk,
                    "metadata": metadata,
                }
            )
    return rows


def embed_and_upload_rows(rows, voyage_client, supabase_client):
    import time
    import voyageai

    batch_size = 15
    seconds_between_requests = 21

    for i in range(0, len(rows), batch_size):
        batch = rows[i : i + batch_size]
        for attempt in range(3):
            try:
                result = voyage_client.embed(
                    [r["content"] for r in batch],
                    model="voyage-4",
                    input_type="document",
                    output_dimension=1024,
                )
                break
            except voyageai.error.RateLimitError:
                print("  분당 한도 초과, 65초 대기 후 재시도...")
                time.sleep(65)
        else:
            sys.exit("반복적으로 rate limit에 걸려 중단합니다.")

        for row, vector in zip(batch, result.embeddings):
            row["embedding"] = vector

        supabase_client.table("content_chunks").upsert(
            batch, on_conflict="source_type,title,chunk_index"
        ).execute()

        done = min(i + batch_size, len(rows))
        print(f"  {done}/{len(rows)} 임베딩+저장 완료")
        if done < len(rows):
            time.sleep(seconds_between_requests)


def main():
    import voyageai
    from supabase import create_client

    supabase_url = os.environ["SUPABASE_URL"]
    supabase_key = os.environ["SUPABASE_SERVICE_KEY"]
    voyage_key = os.environ["VOYAGE_API_KEY"]

    supabase_client = create_client(supabase_url, supabase_key)
    voyage_client = voyageai.Client(api_key=voyage_key)

    docs = collect_documents()
    print(f"전체 블로그 문서: {len(docs)}개")

    cleanup_unpublished({d["title"] for d in docs}, supabase_client)

    changed = filter_changed_docs(docs, supabase_client)
    if not changed:
        print("새로 처리할 문서가 없습니다. 완료.")
        return

    rows = build_rows(changed)
    print(f"이번에 처리할 조각: {len(rows)}개")
    embed_and_upload_rows(rows, voyage_client, supabase_client)
    cleanup_stale_chunks(rows, supabase_client)
    print("완료.")


if __name__ == "__main__":
    main()
