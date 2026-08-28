# Simplifier Studio 스타일 가이드

`insight-7b3e9f2c/` 안에 새 페이지를 추가하거나 기존 페이지를 고칠 때 지키는 규칙입니다.
비공개 내부 도구 섹션(noindex, 사이트 메뉴에 미노출)이라 규칙이 느슨해지기 쉬운데,
페이지가 9개로 늘어난 뒤로는 하나씩 따로 관리하면 금방 어긋납니다 — 이 문서가 그 유일한
기준입니다.

**작업 끝나면 `python scripts/check_studio_style.py`를 실행해서 여기 적힌 규칙을
실제로 지켰는지 확인하세요.** 스크립트가 못 잡는 것(아래 "자동으로 못 잡는 것" 참고)은
브라우저로 직접 확인해야 합니다.

## 이 폴더가 Jekyll 밖에 있다는 것

`insight-7b3e9f2c/` 안 파일들은 front matter가 없는 순수 정적 HTML입니다 — Jekyll
빌드 대상이 아니라서 {% raw %}`{% include %}`{% endraw %}를 못 씁니다. 그래서 여러 페이지가 공유하는
것은 `<link>`/`<script>`로 불러 쓰는 실제 파일(`studio.css`, `studio.js`) 두 개뿐이고,
그 밖의 공유는 전부 이 문서 같은 "사람(과 AI)이 읽고 맞추는" 규칙입니다.

## 새 페이지를 만들 때 (필수 체크리스트)

1. `<head>`에 아래 그대로 포함:
   ```html
   <meta name="robots" content="noindex, nofollow, noarchive">
   <meta name="referrer" content="no-referrer">
   <link rel="icon" type="image/png" href="/favicon-32x32.png" sizes="32x32">
   <link rel="stylesheet" href="/insight-7b3e9f2c/studio.css">
   ```
   - `robots.txt`에 Disallow를 쓰면 오히려 주소가 공개되므로 절대 쓰지 않습니다. `noindex` 메타 태그만 겁니다.
2. `<body>`에 빈 nav를 둡니다 — 직접 링크를 나열하지 않습니다:
   ```html
   <nav id="adminShellNav"></nav>
   ```
3. `</body>` 직전에:
   ```html
   <script src="/insight-7b3e9f2c/studio.js"></script>
   ```
4. 새 메뉴를 **`studio.js`의 `STUDIO_NAV` 배열 한 곳에만** 추가합니다. 9개 파일을
   전부 고치는 게 아닙니다 — 그러려고 이 파일을 분리했습니다.
5. `:root{...}` 디자인 토큰, `body`/`header`/`.info-dot`/`.refresh`/`#adminShellNav`
   CSS를 페이지 자기 `<style>`에 다시 베끼지 않습니다. studio.css가 이미 제공합니다.
   페이지 고유 값(예: `.wrap`의 max-width)만 studio.css `<link>` **다음에** 같은
   선택자로 다시 선언해서 덮어씁니다(일반 CSS 캐스케이드 순서 그대로).

## ⓘ 설명 버튼 (info-dot) 패턴

한 번만 알면 되는 설명(집계 방식, 갱신 주기, 용어 정의 등)은 화면에 상시 노출하지
않고 이 버튼 뒤에 숨깁니다:

```html
<button type="button" class="info-dot" aria-label="설명 보기">ⓘ<span class="info-text">설명 내용</span></button>
```

- **네이티브 `title="..."` 속성을 설명 수단으로 쓰지 않습니다.** 마우스 호버에만
  반응하고 클릭/탭에는 반응하지 않아서, 실제로 화면에서 눌러도 아무 일도 안
  일어나는 죽은 버튼처럼 보입니다(이미 두 번 발견되어 고친 버그 — 아래 "과거에
  실제로 있었던 사고" 참고). `title=`은 이미 화면에 보이는 텍스트가 너무 길어서
  잘렸을 때(말줄임 `text-overflow:ellipsis`) 브라우저 기본 보조 툴팁으로만 씁니다 —
  그 정보 없이도 화면에서 핵심은 이미 보이는 경우에 한해서입니다.
- **배치 원칙: 항상 그것이 설명하는 텍스트 바로 옆에 붙입니다.** `margin-left:auto`
  등으로 줄 끝에 밀어두지 않습니다.
- `aria-label`은 통일해서 `"설명 보기"`를 씁니다.
- 동작(hover 데스크톱 / 탭 토글 터치기기, 하나 열면 나머지 자동 닫힘)은
  `studio.js`의 `bindInfoDots()`가 전역으로 처리합니다 — 페이지에서 따로 클릭
  핸들러를 만들지 않습니다.

## 새로고침 버튼

버튼 안에 `.refresh-icon`/`.refresh-label` span을 두고, 상태 전환은 직접 만들지
않고 공용 헬퍼를 씁니다:

```js
Studio.setRefreshState(btn, "loading");  // -> "success" / "error" -> setTimeout으로 "idle"
```

## 과거에 실제로 있었던 사고 (재발 방지용 기록)

- **`title=` 죽은 툴팁**: book-insight/sns-insight의 초기 버전, 그리고 외부
  `shorts-lab` 파이프라인이 생성하는 `shorts-studio.html`에서 반복 발견. 원인은
  항상 같음 — "설명은 필요한데 상시 노출은 부담스럽다"는 생각에 제일 쉬운
  `title=` 속성으로 때웠다가, 클릭/탭에 반응 안 하는 걸 나중에야 발견. → ⓘ 버튼
  패턴으로 교체.
- **설명 문단을 ⓘ 툴팁으로 옮기면서 여백까지 같이 사라짐**: 사이트 인사이트
  "핵심 KPI" 섹션에서, 제목 밑에 있던 `<p class="h2note">...</p>`(자체
  `margin-bottom:22px`)를 ⓘ 툴팁으로 정리하면서 그 문단이 갖고 있던 여백까지
  통째로 없어져 제목과 카드가 6px로 바짝 붙어버렸음. **설명 텍스트를 문단에서
  ⓘ로 옮길 때는, 그 문단이 만들어주던 여백을 다른 곳(보통 다음 콘텐츠 블록의
  `margin-top`)에 반드시 다시 넣어줘야 합니다.** 이건 코드 패턴 검사로 못 잡고
  브라우저로 실측해야만 보입니다 — 새 헤더를 만들거나 기존 설명 문단을 정리할
  때마다 제목 바로 아래 요소의 `getBoundingClientRect()` 간격을 확인하세요.

## 자동으로 못 잡는 것 (브라우저로 직접 확인)

`check_studio_style.py`는 문자열 패턴만 봅니다. 아래는 반드시 미리보기 서버로
띄워서 눈으로/`javascript_tool`로 확인해야 합니다:

- 제목과 바로 아래 콘텐츠 사이 여백이 부자연스럽게 좁지 않은지(위 사고 사례)
- ⓘ 버튼을 실제로 클릭했을 때 말풍선이 뜨는지 (`aria-pressed` 토글 확인)
- 모바일 폭(375px)에서 사이드바가 가로 스크롤 바로 정상 축소되는지
- 콘솔/네트워크 에러 없이 로드되는지

## 외부에서 생성되는 페이지 (예: shorts-studio.html)

`shorts-studio.html`은 이 저장소 밖 `shorts-lab/pipeline/build_studio_site.py`가
매번 새로 써서 덮어씁니다. 이 페이지를 직접 손으로 고쳐도 다음 파이프라인 실행
때 되돌아갑니다 — **생성기 스크립트 쪽을 고쳐야 영구적으로 반영됩니다.** 이런
페이지를 발견하면 생성기 코드에도 이 문서의 규칙이 반영돼 있는지 확인하세요.
