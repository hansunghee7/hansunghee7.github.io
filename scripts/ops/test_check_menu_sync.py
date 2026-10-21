import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import check_menu_sync as m  # noqa: E402

KO = '<header><nav><a href="/a">가</a><a href="https://x.io/b?q=1#h">나</a></nav></header><a href="/z">z</a>'
EN = '<nav><a href="/a">A</a><a href="/b">B</a></nav>'


def test_extract_header_only():
    assert m.extract_links(KO) == ["/a", "https://x.io/b?q=1#h"]


def test_extract_fallback_all():
    assert m.extract_links('<a href="/p">p</a><a>no</a>') == ["/p"]


def test_path_of():
    assert m.path_of("https://x.io/b?q=1#h") == "/b"
    assert m.path_of("https://x.io") == "/"


def test_compare_same():
    same, na, nb, _, _ = m.compare(m.extract_links(KO), m.extract_links(EN))
    assert same and na == nb == 2


def test_compare_count_differs():
    same, na, nb, _, _ = m.compare(["/a", "/b"], ["/a"])
    assert not same and (na, nb) == (2, 1)


def test_compare_path_differs():
    same, *_ = m.compare(["/a", "/b"], ["/a", "/c"])
    assert not same
