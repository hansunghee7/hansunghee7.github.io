"""import_docs_to_opsdb.py의 제외 규칙·공개 구분 시험(DB 호출 없음, N174 1단계).

실행: python -m pytest scripts/ops/tests/test_import_docs.py -v
"""
import importlib.util
import sys
from pathlib import Path

OPS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(OPS))
spec = importlib.util.spec_from_file_location("import_docs_under_test", OPS / "import_docs_to_opsdb.py")
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def test_site_packages_docs_are_skipped():
    p = Path('C:/work/shorts-lab/.x/Lib/site-packages/numpy-2.5.3.dist-info/README.md').parts
    assert m.is_skipped(p, 100)
    assert m.is_skipped(Path('a/dist-packages/x/README.md').parts, 100)


def test_normal_docs_are_kept_and_big_files_skipped():
    assert not m.is_skipped(Path('docs/guide.md').parts, 380_000)
    assert m.is_skipped(Path('docs/big.md').parts, 3_000_001)


def test_existing_skips_still_work():
    assert m.is_skipped(Path('docs/archive/node_modules/a.md').parts, 10)
    assert m.is_skipped(Path('node_modules/x/README.md').parts, 10)


def test_visibility_public_only_for_public_repo():
    assert m.visibility_of('hansunghee7.github.io') == 'public'
    for r in ('shorts-lab', 'solar-bible', 'simplifier-cxo-db', 'saegim-pass-dev', '_ops'):
        assert m.visibility_of(r) == 'private'
