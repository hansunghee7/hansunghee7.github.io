/* Simplifier Studio 공용 스크립트. studio.css와 짝을 이룬다 -- 사이드바
   메뉴 목록·활성 표시, ⓘ 말풍선 클릭/탭 토글, 새로고침 버튼 상태 표시
   같은, 페이지마다 똑같이 복붙돼 있던 로직을 여기 한 곳으로 모았다.
   2026-08-28. 메뉴를 추가/이름 변경할 때는 이제 파일마다 안 고치고
   아래 STUDIO_NAV 배열만 고치면 전체 페이지에 반영된다. */
(function () {
  "use strict";

  // href는 location.pathname과 정확히 비교해서 현재 페이지를 찾는다
  // (사이트 인사이트만 "/insight-7b3e9f2c/"처럼 슬래시로 끝남).
  var STUDIO_NAV = [
    { href: "/insight-7b3e9f2c/", label: "사이트 인사이트" },
    { href: "/insight-7b3e9f2c/system-map.html", label: "시스템 구조" },
    { href: "/insight-7b3e9f2c/style-guide.html", label: "스타일 가이드" },
    { href: "/insight-7b3e9f2c/sns-insight.html", label: "SNS 인사이트" },
    { href: "/insight-7b3e9f2c/book-insight.html", label: "북 인사이트" },
    { href: "/insight-7b3e9f2c/write.html", label: "글쓰기" },
    { href: "/insight-7b3e9f2c/multi-publish.html", label: "멀티 퍼블리싱" },
    { href: "/insight-7b3e9f2c/shorts-studio.html", label: "숏폼 스튜디오" },
    { href: "/insight-7b3e9f2c/newsletter-research.html", label: "뉴스레터 리서치" },
    { href: "/insight-7b3e9f2c/pillar-manage.html", label: "필러 관리" },
    { href: "/insight-7b3e9f2c/ask.html", label: "Simplifier와의 대화" },
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
    var linksHtml = STUDIO_NAV.map(function (item) {
      var active = item.href === here;
      return '<a href="' + escapeHtmlAttr(item.href) + '"' + (active ? ' class="active"' : "") + ">" + escapeHtmlAttr(item.label) + "</a>";
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
  function bindInfoDots() {
    document.addEventListener("click", function (e) {
      var btn = e.target.closest ? e.target.closest(TOGGLE_SELECTOR) : null;
      var wasOpen = btn && btn.getAttribute("aria-pressed") === "true";
      document.querySelectorAll('.info-dot[aria-pressed="true"], .h2note-q[aria-pressed="true"]').forEach(function (o) { o.setAttribute("aria-pressed", "false"); });
      if (!btn) return;
      e.preventDefault();
      e.stopPropagation();
      btn.setAttribute("aria-pressed", wasOpen ? "false" : "true");
    });
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
