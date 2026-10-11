# -*- coding: utf-8 -*-
"""이미지 채점 관문(publish_sns_queue.image_check_problem) 시험. 덱스 독립 검증(2026-10-11)이 지적한 우회 경로를 하나씩 막는지 본다."""
import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location("psq", ROOT / "scripts" / "publish_sns_queue.py")
psq = importlib.util.module_from_spec(spec)
spec.loader.exec_module(psq)

IMG = "assets/data/image_scores/_test_img.bin"
SCORE = "assets/data/image_scores/_test_score.json"


def setup_files(**over):
    d = ROOT / "assets/data/image_scores"
    d.mkdir(parents=True, exist_ok=True)
    (ROOT / IMG).write_bytes(b"fake-image-bytes")
    rec = {"queue_id": "q1", "image": IMG, "sha256": hashlib.sha256(b"fake-image-bytes").hexdigest(), "source": "local-krea2",
           "idea": "같은 질문이 반복되는 건 사람이 아니라 구조 문제", "conditions": {str(i): 1 for i in range(1, 9)}, "score": "8/8"}
    rec.update(over)
    (ROOT / SCORE).write_text(json.dumps(rec, ensure_ascii=False), encoding="utf-8")


def item(**over):
    it = {"id": "q1", "publishAt": "2026-10-13T09:00:00+09:00", "content": {"media_source": [IMG], "body": "x"},
          "image_check": {"file": SCORE}}
    it.update(over)
    return it


def teardown_module(_):
    for f in (IMG, SCORE):
        (ROOT / f).unlink(missing_ok=True)


def test_pass():
    setup_files()
    assert psq.image_check_problem(item()) is None


def test_no_record_blocked():
    assert psq.image_check_problem(item(image_check={})) is not None


def test_bad_or_missing_publish_at_fails_closed():
    setup_files()
    assert psq.image_check_problem(item(publishAt="")) is not None
    assert psq.image_check_problem(item(publishAt="내일")) is not None


def test_old_dated_item_exempt():
    assert psq.image_check_problem(item(publishAt="2026-10-10T09:00:00+09:00", image_check={})) is None


def test_path_escape_blocked():
    setup_files()
    assert psq.image_check_problem(item(image_check={"file": "../outside.json"})) is not None
    assert psq.image_check_problem(item(image_check={"file": "README.md"})) is not None


def test_score_forgery_blocked():
    setup_files(score="8/8", conditions={str(i): 0 for i in range(1, 9)})
    assert psq.image_check_problem(item()) is not None


def test_condition1_required_and_min_six():
    c = {str(i): 1 for i in range(1, 9)}
    c["1"] = 0
    setup_files(conditions=c, score="7/8")
    assert psq.image_check_problem(item()) is not None
    c2 = {str(i): (1 if i <= 5 else 0) for i in range(1, 9)}
    setup_files(conditions=c2, score="5/8")
    assert psq.image_check_problem(item()) is not None


def test_reuse_for_other_post_and_swapped_image_blocked():
    setup_files()
    assert psq.image_check_problem(item(id="q2")) is not None
    (ROOT / IMG).write_bytes(b"different-image")
    assert psq.image_check_problem(item()) is not None


def test_bad_source_and_short_idea_blocked():
    setup_files(source="stock-made-up")
    assert psq.image_check_problem(item()) is not None
    setup_files(idea="짧음")
    assert psq.image_check_problem(item()) is not None
