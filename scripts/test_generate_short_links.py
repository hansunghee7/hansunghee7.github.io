"""generate_short_links.py의 순수 함수 단위 시험(absolute, render).

main()은 assets/data/posts.json을 읽고 log_assets/markdown/에 리다이렉트
스텁 파일을 쓰므로 이 시험에서는 부르지 않는다. absolute()/render()는
입력 문자열만으로 결과를 만드는 순수 함수다.

실행: python -m pytest scripts/test_generate_short_links.py
"""
import importlib.util
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("generate_short_links_under_test", SCRIPTS / "generate_short_links.py")
gsl = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gsl)


# ---------------------------------------------------------------------------
# absolute(path_or_url)
# ---------------------------------------------------------------------------

def test_absolute_prefixes_relative_path():
    assert gsl.absolute("/logs/1/") == "https://simplifier.co.kr/logs/1/"


def test_absolute_leaves_full_url_unchanged():
    assert gsl.absolute("https://other.com/x") == "https://other.com/x"


def test_absolute_empty_string_returns_bare_base():
    assert gsl.absolute("") == "https://simplifier.co.kr"


def test_absolute_protocol_relative_url_is_mishandled():
    # 발견한 문제: "//host/path" 형태(프로토콜 상대 URL)는 "://"를 포함하지
    # 않아 외부 URL로 인식되지 못하고 BASE에 그대로 이어붙여진다. 코드는
    # 고치지 않고 현재 동작을 그대로 기록만 한다. PR 본문 '발견한 문제' 참고.
    assert gsl.absolute("//cdn.example.com/x.png") == "https://simplifier.co.kr//cdn.example.com/x.png"


# ---------------------------------------------------------------------------
# render(title, short_url, image)
# ---------------------------------------------------------------------------

def test_render_escapes_html_and_fills_fields():
    html = gsl.render('제목 "따옴표" <script>', "/logs/1/", "/assets/og.png")
    assert '<title>제목 &quot;따옴표&quot; &lt;script&gt; - Simplifier</title>' in html
    assert 'href="https://simplifier.co.kr/logs/1/"' in html
    assert 'content="https://simplifier.co.kr/assets/og.png"' in html
    assert "<script>" not in html  # 이스케이프됐으므로 실제 스크립트 태그는 없어야 함


def test_render_missing_image_falls_back_to_default():
    html = gsl.render("한글 제목", "/logs/2/", None)
    assert "https://simplifier.co.kr/assets/og-image.png" in html


def test_render_empty_title_produces_empty_title_tag():
    html = gsl.render("", "/logs/3/", "")
    assert "<title> - Simplifier</title>" in html
    assert "https://simplifier.co.kr/assets/og-image.png" in html  # 빈 문자열도 이미지 없음으로 취급
