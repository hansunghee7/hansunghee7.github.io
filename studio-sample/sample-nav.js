/* Simplifier Studio 샘플 사이트 전용 nav 스크립트.
   insight-7b3e9f2c/studio.js를 그대로 fork했다 -- 시각/동작(사이드바, ⓘ 말풍선,
   모바일 햄버거)은 완전히 동일하게 유지하되, 메뉴 목록만 이 4개 샘플 페이지로
   제한한다. 진짜 studio.js를 그대로 불러오면 STUDIO_NAV 전체(SNS 인사이트,
   글쓰기 도구, 대화 등 내부 전용 메뉴)가 고객사에게 그대로 노출되므로 반드시
   이 파일을 따로 둔다 -- 실수로 studio.js를 링크하지 않도록 주의. */
(function () {
  "use strict";

  var SAMPLE_NAV = [
    { href: "/studio-sample/", label: "소개" },
    { href: "/studio-sample/ux-guide-81d2dd.html", label: "통합 UX 가이드" },
    { href: "/studio-sample/brand-guide-8c9e69.html", label: "브랜드 가이드" },
    { href: "/studio-sample/morning-briefing.html", label: "모닝 브리핑 샘플" },
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
    var linksHtml = SAMPLE_NAV.map(function (item) {
      var active = item.href === here;
      return '<a href="' + escapeHtmlAttr(item.href) + '"' + (active ? ' class="active"' : "") + ">" + escapeHtmlAttr(item.label) + "</a>";
    }).join("");
    nav.innerHTML =
      '<div class="shell-title">Simplifier · 샘플</div>' +
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
    document.addEventListener("click", function (e) {
      if (!links.classList.contains("open")) return;
      if (nav.contains(e.target)) return;
      setOpen(false);
    });
  }

  /* ⓘ 말풍선 동작 -- insight-7b3e9f2c/studio.js의 bindInfoDots/positionInfoText와
     동일 로직(그대로 fork). 세 실제 페이지 모두 이 버튼을 쓰므로 빠지면 안 된다. */
  var TOGGLE_SELECTOR = ".info-dot, .h2note-q";
  function positionInfoText(btn) {
    if (!btn) return;
    var viewportWidth = document.documentElement.clientWidth;
    var text = btn.querySelector(".info-text");
    if (text) {
      text.classList.remove("info-text--right");
      var rect = text.getBoundingClientRect();
      if (rect.right > viewportWidth - 8) {
        text.classList.add("info-text--right");
      }
      return;
    }
    var note = btn.querySelector(".h2note-text");
    if (!note) return;
    var currentShift = parseFloat(note.style.getPropertyValue("--tt-shift")) || 0;
    var noteRect = note.getBoundingClientRect();
    var naturalRight = noteRect.right - currentShift;
    var naturalLeft = noteRect.left - currentShift;
    var overflowRight = naturalRight - (viewportWidth - 8);
    var overflowLeft = 8 - naturalLeft;
    var nextShift = 0;
    if (overflowRight > 0) nextShift = -overflowRight;
    else if (overflowLeft > 0) nextShift = overflowLeft;
    note.style.setProperty("--tt-shift", nextShift + "px");
  }
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

  renderNav();
  bindInfoDots();
})();
