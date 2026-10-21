import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import post_channel_weekly as p

ITEMS = [
    {'id': 'a', 'channel_id': 'yt-shorts', 'title': '글 A'},
    {'id': 'b', 'channel_id': 'ig-x', 'title': '글|B'},
]
SNAPS = [
    {'content_id': 'a', 'captured_at': '2026-10-15T00:00:00Z', 'views': 100, 'likes': 1, 'comments': None},
    {'content_id': 'a', 'captured_at': '2026-10-20T00:00:00Z', 'views': 160, 'likes': 3, 'comments': 2},
    {'content_id': 'b', 'captured_at': '2026-10-20T00:00:00Z', 'views': 500, 'likes': None, 'comments': None},
    {'content_id': 'zz', 'captured_at': '2026-10-20T00:00:00Z', 'views': 7, 'likes': None, 'comments': None},
]


def test_aggregate_delta_and_order():
    rows = p.aggregate(SNAPS, ITEMS)
    assert [r['title'] for r in rows] == ['글|B', '글 A', 'zz']
    a = rows[1]
    assert (a['views'], a['views_delta'], a['reactions'], a['reactions_delta']) == (160, 60, 5, 4)
    assert rows[0]['views_delta'] == 0
    assert rows[2]['channel'] == '(미분류)'


def test_channel_totals():
    t = p.channel_totals(p.aggregate(SNAPS, ITEMS))
    assert t['yt-shorts']['views'] == 160 and t['ig-x']['posts'] == 1


def test_render_empty_and_table():
    assert p.render([]) == p.NO_DATA
    md = p.render(p.aggregate(SNAPS, ITEMS))
    assert '글/B' in md and '| yt-shorts | 1 | 160 |' in md


def test_main_no_data(monkeypatch, capsys):
    import opsdb
    monkeypatch.setattr(opsdb, 'select', lambda *a, **k: [])
    assert p.main() == 0
    assert p.NO_DATA in capsys.readouterr().out
