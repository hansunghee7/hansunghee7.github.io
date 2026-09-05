// 2026-09-05: GitHub 연결/토큰 붙여넣기 UI를 없앴다. background.js가
// GitHub PAT를 직접 안 들고 Cloudflare Worker(simplifier-claude-usage-writer)
// 의 좁은 창구만 호출하는 방식으로 바뀌어서, 이 팝업에서 로그인·토큰
// 입력을 받을 이유가 없어졌다 -- 자세한 이유는 worker.js·WORKER_DEPLOY.md
// 참고. 이제 이 팝업은 "최근 수집 기록"을 보여주는 역할만 한다.

var logList = document.getElementById("logList");

var PLATFORM_LABELS = {
  linkedin: "LinkedIn",
  facebook: "Facebook",
  instagram: "Instagram",
  threads: "Threads",
  naver_blog: "네이버블로그",
  brunch: "브런치",
  remember: "리멤버 커넥트",
  rocketpunch: "로켓펀치",
  naver_clip: "네이버클립(신기한 아파트사전)",
  content_instagram: "인스타그램(신기한 아파트사전)",
  content_threads: "스레드(신기한 아파트사전)",
  content_facebook: "페이스북(신기한 아파트사전)",
  content_tiktok: "틱톡(신기한 아파트사전)",
  content_x: "X(신기한 아파트사전)",
  claude_usage: "클로드 사용량",
};

var STATUS_MARK = { success: "✓", error: "✕", pending: "…", miss: "△" };

function escapeHtml(s) {
  return (s == null ? "" : String(s)).replace(/[&<>"']/g, function (c) {
    return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
  });
}

function formatTime(iso) {
  try {
    var d = new Date(iso);
    var pad = function (n) { return String(n).padStart(2, "0"); };
    return pad(d.getMonth() + 1) + "/" + pad(d.getDate()) + " " + pad(d.getHours()) + ":" + pad(d.getMinutes());
  } catch (e) {
    return "";
  }
}

function renderLog(log) {
  if (!log || !log.length) {
    logList.innerHTML = '<div class="log-empty">아직 기록 없음 — 프로필 페이지를 열면 여기 쌓입니다</div>';
    return;
  }
  logList.innerHTML = log.map(function (e) {
    var label = PLATFORM_LABELS[e.platform] || e.platform;
    var mark = STATUS_MARK[e.status] || "?";
    var noteHtml = e.note
      ? '<span class="note">(' + escapeHtml(e.note) + ")</span>"
      : e.status === "miss"
      ? '<span class="note">(문구를 못 찾음)</span>'
      : "";
    return (
      '<div class="log-item">' +
      '<span class="mark ' + e.status + '">' + mark + "</span>" +
      '<span class="plat">' + escapeHtml(label) + "</span>" +
      '<span class="cnt">' + (e.count != null ? e.count.toLocaleString() + (e.unit || "명") : "") + "</span>" +
      noteHtml +
      '<span class="time">' + formatTime(e.capturedAt) + "</span>" +
      "</div>"
    );
  }).join("");
}

// SNS 인사이트 페이지가 "오늘자 기록이 있는지"로 새로고침 동작 여부를
// 정하는 것과 같은 기준을 여기서도 보여준다 -- background.js가 실제로
// 언제 마지막으로 전체 수집 라운드를 돌렸는지(lastFullRoundDate)를
// 그대로 읽어서 "오늘 수집 완료/아직 안 됨"으로 표시한다.
function kstToday() {
  return new Intl.DateTimeFormat("en-CA", { timeZone: "Asia/Seoul" }).format(new Date());
}

function renderSelectorWarning(warning) {
  var box = document.getElementById("selectorWarningBox");
  if (!warning) {
    box.style.display = "none";
    return;
  }
  var label = PLATFORM_LABELS[warning.platform] || warning.platform;
  document.getElementById("selectorWarningText").textContent =
    label + " 팔로워 수를 " + warning.streak + "번 연속 못 찾았습니다 — 페이지 구조가 바뀌었을 수 있어요. 직접 열어서 확인해주세요.";
  box.style.display = "block";
}

function render() {
  chrome.storage.local.get(
    ["recentLog", "lastFullRoundDate", "selectorWarning"],
    function (res) {
      renderSelectorWarning(res.selectorWarning);
      var roundEl = document.getElementById("roundStatus");
      if (res.lastFullRoundDate === kstToday()) {
        roundEl.textContent = "오늘 전체 수집 완료 (" + res.lastFullRoundDate + ")";
      } else {
        roundEl.textContent = "오늘 아직 전체 수집 안 됨" + (res.lastFullRoundDate ? " (마지막: " + res.lastFullRoundDate + ")" : "");
      }
      renderLog(res.recentLog);
    }
  );
}

// 다른 탭에서 새로 캡처가 기록되면(recentLog 갱신) 팝업이 열려 있는 동안에도
// 바로 반영되게 -- 팝업을 닫았다 여는 수고 없이 확인할 수 있다.
chrome.storage.onChanged.addListener(function (changes, area) {
  if (area === "local" && changes.recentLog) {
    renderLog(changes.recentLog.newValue);
  }
  if (area === "local" && "selectorWarning" in changes) {
    renderSelectorWarning(changes.selectorWarning.newValue);
  }
});

document.getElementById("dismissWarningBtn").addEventListener("click", function () {
  chrome.runtime.sendMessage({ type: "DISMISS_SELECTOR_WARNING" });
  document.getElementById("selectorWarningBox").style.display = "none";
});

render();
