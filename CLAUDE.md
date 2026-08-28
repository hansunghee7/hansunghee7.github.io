# 저장소 안내 (Claude Code용)

## Simplifier Studio (`insight-7b3e9f2c/`)

`insight-7b3e9f2c/` 안의 어떤 파일이라도 새로 만들거나 고치기 전에,
**[insight-7b3e9f2c/STYLE_GUIDE.md](insight-7b3e9f2c/STYLE_GUIDE.md)를 먼저 읽으세요.**
필수 `<head>`/nav/스크립트 구조, ⓘ 설명 버튼 패턴, 새로고침 버튼 패턴, 과거에
실제로 있었던 사고(죽은 `title=` 툴팁, 설명 문단을 ⓘ로 옮기며 여백이 같이 사라진
사례) 등 이 폴더의 UX/기술 규칙이 전부 그 문서에 있습니다.

작업을 끝냈다고 보고하기 전에 반드시 실행:

```bash
python scripts/check_studio_style.py
```

FAIL이 하나라도 있으면 고치기 전까지 완료로 보지 마세요. `title=` 관련 항목은
WARN으로만 뜨는데, 그건 사람 판단이 필요해서입니다 — STYLE_GUIDE.md의 기준으로
직접 검토하세요. 이 스크립트는 문자열 패턴만 봅니다 — 제목과 콘텐츠 사이 여백처럼
시각적으로만 드러나는 문제는 미리보기 서버로 띄워서 직접 확인해야 합니다.

`insight-7b3e9f2c/shorts-studio.html`은 이 저장소 밖 `shorts-lab` 프로젝트의
파이프라인이 매번 새로 써서 덮어씁니다 — 이 파일을 직접 고쳐도 다음 파이프라인
실행 때 되돌아갑니다. 영구히 고치려면 `shorts-lab/pipeline/build_studio_site.py`
쪽을 고쳐야 합니다.
