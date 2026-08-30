/* Simplifier Studio 공용 스크립트. studio.css와 짝을 이룬다 -- 사이드바
   메뉴 목록·활성 표시, ⓘ 말풍선 클릭/탭 토글, 새로고침 버튼 상태 표시
   같은, 페이지마다 똑같이 복붙돼 있던 로직을 여기 한 곳으로 모았다.
   2026-08-28. 메뉴를 추가/이름 변경할 때는 이제 파일마다 안 고치고
   아래 STUDIO_NAV 배열만 고치면 전체 페이지에 반영된다. */
(function () {
  "use strict";

  // href는 location.pathname과 정확히 비교해서 현재 페이지를 찾는다
  // (사이트 인사이트만 "/insight-7b3e9f2c/"처럼 슬래시로 끝남).
  // 2026-08-30 순서 개편: 이전엔 만든 순서대로 쌓여서 참조 문서(시스템
  // 구조·UX 가이드)가 인사이트 3형제 사이에 끼어 있었다. 이제 사용
  // 목적·빈도 순으로 묶는다 -- 매일 보는 인사이트(모니터링) → 일할 때
  // 여는 제작 도구(글쓰기→퍼블리싱이 실제 작업 순서) → 대화 → 가끔
  // 찾는 참조 문서. group이 바뀌는 지점마다 사이드바에 소제목이 붙는다.
  var STUDIO_NAV = [
    { href: "/insight-7b3e9f2c/", label: "사이트 인사이트", group: "인사이트" },
    { href: "/insight-7b3e9f2c/search-insight.html", label: "검색·UX 품질", group: "인사이트" },
    { href: "/insight-7b3e9f2c/sns-insight.html", label: "SNS 인사이트", group: "인사이트" },
    { href: "/insight-7b3e9f2c/book-insight.html", label: "북 인사이트", group: "인사이트" },
    { href: "/insight-7b3e9f2c/write.html", label: "글쓰기", group: "제작" },
    { href: "/insight-7b3e9f2c/multi-publish.html", label: "멀티 퍼블리싱", group: "제작" },
    { href: "/insight-7b3e9f2c/shorts-studio.html", label: "숏폼 스튜디오", group: "제작" },
    { href: "/insight-7b3e9f2c/newsletter-research.html", label: "뉴스레터 리서치", group: "제작" },
    { href: "/insight-7b3e9f2c/pillar-manage.html", label: "필러 관리", group: "제작" },
    { href: "/insight-7b3e9f2c/ask.html", label: "Simplifier와의 대화", group: "대화" },
    { href: "/insight-7b3e9f2c/system-map.html", label: "시스템 구조", group: "참조" },
    { href: "/insight-7b3e9f2c/style-guide.html", label: "통합 UX 가이드", group: "참조" },
  ];

  function escapeHtmlAttr(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }

  function renderNav() {
    var nav = document.getElementById("adminShellNav");
    if (!nav) return;
    var here = location.pathname;
    var prevGroup = null;
    var linksHtml = STUDIO_NAV.map(function (item) {
      var active = item.href === here;
      var head = "";
      if (item.group && item.group !== prevGroup) {
        head = '<div class="shell-group">' + escapeHtmlAttr(item.group) + "</div>";
        prevGroup = item.group;
      }
      return head + '<a href="' + escapeHtmlAttr(item.href) + '"' + (active ? ' class="active"' : "") + ">" + escapeHtmlAttr(item.label) + "</a>";
    }).join("");
    // 모바일에서만 보이는 햄버거 버튼 + 펼침 목록. 데스크톱은 CSS가 버튼을
    // 숨기고 .shell-links를 원래처럼 세로로 그냥 보여준다(별도 처리 없음).
    nav.innerHTML =
      '<div class="shell-title">Simplifier Studio</div>' +
      '<button type="button" class="shell-burger" id="shellBurger" aria-label="메뉴 열기" aria-expanded="false" aria-controls="shellLinks"><span></span><span></span><span></span></button>' +
      '<div class="shell-links" id="shellLinks">' + linksHtml + "</div>";

    var burger = document.getElementById("shellBurger");
    var links = document.getElementById("shellLinks");
    if (!burger || !links) return;

    function setOpen(open) {
      links.classList.toggle("open", open);
      burger.classList.toggle("open", open);
      burger.setAttribute("aria-expanded", open ? "true" : "false");
      burger.setAttribute("aria-label", open ? "메뉴 닫기" : "메뉴 열기");
    }
    burger.addEventListener("click", function (e) {
      e.stopPropagation();
      setOpen(!links.classList.contains("open"));
    });
    // 링크 목록 바깥을 탭하면 닫는다(같은 페이지 안에서 다시 탭할 수 있으므로
    // 링크 클릭 자체는 페이지 이동으로 자연스럽게 닫힘 처리됨).
    document.addEventListener("click", function (e) {
      if (!links.classList.contains("open")) return;
      if (nav.contains(e.target)) return;
      setOpen(false);
    });
  }

  /* ⓘ(및 사이트 인사이트에서만 쓰는 "?" 섹션 설명 .h2note-q)는 마우스를
     올리면(:hover) 말풍선이 뜬다(CSS만으로 처리). 터치기기는 hover가
     없으므로, 탭하면 aria-pressed를 켜서 같은 CSS 규칙으로 말풍선을
     띄우고 다시 탭하거나 다른 곳을 탭하면 닫는다. .h2note-q는 사이트
     인사이트에만 있지만, 두 종류를 한 핸들러로 묶어야 "하나 열면
     나머지는 다 닫힘"이 유지된다 -- 페이지 전체에 한 번만 건다(각
     버튼은 innerHTML로 다시 그려질 수 있어서, 버튼 자체가 아니라
     document에 위임). */
  var TOGGLE_SELECTOR = ".info-dot, .h2note-q";
  /* 화면 오른쪽 끝 근처의 ⓘ는 기본 앵커(left:0)로 말풍선을 펼치면 뷰포트
     밖으로 나가 가로 스크롤이 생긴다(좁은 창에서 실측 확인). visibility
     로만 감춰져 있어도(display:none이 아니라서) getBoundingClientRect로
     열기 전에 크기를 미리 잴 수 있으므로, 열릴 때마다 넘칠지 계산해서
     넘치면 오른쪽 기준(.info-text--right)으로 뒤집는다. */
  function positionInfoText(btn) {
    if (!btn) return;
    var text = btn.querySelector(".info-text");
    if (text) {
      text.classList.remove("info-text--right");
      var rect = text.getBoundingClientRect();
      if (rect.right > window.innerWidth - 8) {
        text.classList.add("info-text--right");
      }
      return;
    }
    // .h2note-text(사이트 인사이트)는 가운데 정렬 말풍선이라 좌/우 넘치는
    // 만큼만 옆으로 밀어준다(--tt-shift, CSS의 translateX 계산에 반영).
    var note = btn.querySelector(".h2note-text");
    if (!note) return;
    note.style.setProperty("--tt-shift", "0px");
    var noteRect = note.getBoundingClientRect();
    var overflowRight = noteRect.right - (window.innerWidth - 8);
    var overflowLeft = 8 - noteRect.left;
    if (overflowRight > 0) note.style.setProperty("--tt-shift", (-overflowRight) + "px");
    else if (overflowLeft > 0) note.style.setProperty("--tt-shift", overflowLeft + "px");
  }
  /* 열릴 때만 계산하던 걸로는 부족했다 -- .info-text는 닫혀 있어도
     visibility:hidden일 뿐 position:absolute라서, 기본 앵커(left:0)가
     뷰포트 오른쪽 밖으로 나가면 한 번도 안 열어봐도 그 페이지 자체가
     가로 스크롤이 생긴다(2026-08-30 모바일 375px 실측 -- 거의 모든
     인사이트 페이지에서 클릭 전부터 이미 발생 중이었음). 그래서 로드
     시점과, 데이터 fetch 후 카드가 새로 그려지는 시점(=DOM 변경) 모두에
     대해 전체 ⓘ를 미리 계산해둔다. */
  function positionAllInfoDots() {
    document.querySelectorAll(TOGGLE_SELECTOR).forEach(positionInfoText);
  }
  function bindInfoDots() {
    document.addEventListener("mouseover", function (e) {
      var btn = e.target.closest ? e.target.closest(TOGGLE_SELECTOR) : null;
      if (btn) positionInfoText(btn);
    });
    document.addEventListener("click", function (e) {
      var btn = e.target.closest ? e.target.closest(TOGGLE_SELECTOR) : null;
      var wasOpen = btn && btn.getAttribute("aria-pressed") === "true";
      document.querySelectorAll('.info-dot[aria-pressed="true"], .h2note-q[aria-pressed="true"]').forEach(function (o) { o.setAttribute("aria-pressed", "false"); });
      if (!btn) return;
      e.preventDefault();
      e.stopPropagation();
      if (!wasOpen) positionInfoText(btn);
      btn.setAttribute("aria-pressed", wasOpen ? "false" : "true");
    });

    positionAllInfoDots();
    var reposRaf = null;
    function schedulePositionAll() {
      if (reposRaf) return;
      reposRaf = requestAnimationFrame(function () { reposRaf = null; positionAllInfoDots(); });
    }
    window.addEventListener("resize", schedulePositionAll);
    new MutationObserver(schedulePositionAll).observe(document.body, { childList: true, subtree: true });
  }

  /* 새로고침 버튼 상태 표시 -- 눌러도 반영됐는지 알 길이 없다는 피드백을 받아
     추가함. loading(스피너+비활성) -> success/error(1.6초 flash) -> idle 순으로 돈다. */
  function setRefreshState(btn, state) {
    btn.classList.remove("is-loading", "is-success", "is-error");
    var icon = btn.querySelector(".refresh-icon");
    var label = btn.querySelector(".refresh-label");
    if (state === "loading") {
      btn.disabled = true; btn.classList.add("is-loading");
      icon.textContent = "↻"; label.textContent = "불러오는 중…";
    } else if (state === "success") {
      btn.disabled = false; btn.classList.add("is-success");
      icon.textContent = "✓"; label.textContent = "완료";
    } else if (state === "error") {
      btn.disabled = false; btn.classList.add("is-error");
      icon.textContent = "✕"; label.textContent = "실패";
    } else {
      btn.disabled = false;
      icon.textContent = "↻"; label.textContent = "새로고침";
    }
  }

  window.Studio = {
    NAV: STUDIO_NAV,
    renderNav: renderNav,
    setRefreshState: setRefreshState,
  };

  renderNav();
  bindInfoDots();
})();
