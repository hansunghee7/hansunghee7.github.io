// CMS(admin/index.html)가 GitHub 로그인할 때 쓰는 것과 똑같은 팝업창 +
// postMessage 방식(Decap/Netlify CMS 표준 OAuth 핸드셰이크)을 그대로
// 재사용합니다. 이미 배포되어 있는 simplifier-cms-auth 워커를 그대로
// 쓰기 때문에, 새 GitHub OAuth 앱이나 새 워커를 만들 필요가 없습니다.

var AUTH_URL = "https://simplifier-cms-auth.simon-8be.workers.dev/auth";

var statusBox = document.getElementById("statusBox");
var loginBtn = document.getElementById("loginBtn");
var logoutBtn = document.getElementById("logoutBtn");
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
    var noteHtml = e.status === "error" && e.note
      ? '<span class="note">(' + escapeHtml(e.note) + ")</span>"
      : e.status === "miss"
      ? '<span class="note">(문구를 못 찾음)</span>'
      : "";
    return (
      '<div class="log-item">' +
      '<span class="mark ' + e.status + '">' + mark + "</span>" +
      '<span class="plat">' + escapeHtml(label) + "</span>" +
      '<span class="cnt">' + (e.count != null ? e.count.toLocaleString() + "명" : "") + "</span>" +
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
    ["githubToken", "pendingCaptures", "recentLog", "lastFullRoundDate", "selectorWarning"],
    function (res) {
    renderSelectorWarning(res.selectorWarning);
    var roundEl = document.getElementById("roundStatus");
    if (res.lastFullRoundDate === kstToday()) {
      roundEl.textContent = "오늘 전체 수집 완료 (" + res.lastFullRoundDate + ")";
    } else {
      roundEl.textContent = "오늘 아직 전체 수집 안 됨" + (res.lastFullRoundDate ? " (마지막: " + res.lastFullRoundDate + ")" : "");
    }
    if (res.githubToken) {
      statusBox.className = "status ok";
      statusBox.textContent = "GitHub 연결됨 — 자동 기록 작동 중";
      loginBtn.style.display = "none";
      logoutBtn.style.display = "block";
      // 401(인증 실패)이 반복될 때, 저장된 토큰이 실제로 어떤 값인지
      // (진짜 GitHub 토큰인지, 빈 값/이상한 값인지) 확인하기 위한 디버그
      // 표시. 토큰 전체는 절대 노출하지 않고 앞 8자만 보여준다.
      var t = res.githubToken;
      document.getElementById("tokenDebug").textContent =
        "토큰: " + t.slice(0, 8) + "… (" + t.length + "자)";
    } else {
      document.getElementById("tokenDebug").textContent = "";
      var pendingNote = res.pendingCaptures && res.pendingCaptures.length
        ? " (" + res.pendingCaptures.length + "건 대기 중)"
        : "";
      statusBox.className = "status warn";
      statusBox.textContent = "GitHub 연결 필요" + pendingNote;
      loginBtn.style.display = "block";
      logoutBtn.style.display = "none";
    }
    renderLog(res.recentLog);
  });
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

function handleMessage(e) {
  if (typeof e.data !== "string") return;

  if (e.data === "authorizing:github") {
    // 팝업이 보낸 최초 핸드셰이크 신호 -- 그대로 되돌려 보내 확인해줍니다.
    // GitHub 로그인 페이지 자체가 Cross-Origin-Opener-Policy를 걸어놔서,
    // 팝업이 github.com을 거쳐 갔다 오면 이 postMessage가 브라우저 정책으로
    // 막힐 수 있다(chrome://extensions 오류 탭에 경고로 뜸). 그래도 최종
    // 토큰은 팝업->이 창 방향의 메시지로 별도 전달되어 로그인은 정상
    // 완료되므로, 이 신호는 실패해도 조용히 무시한다.
    try { if (authWindow) authWindow.postMessage("authorizing:github", "*"); } catch (err) { /* ignore */ }
    return;
  }

  if (e.data.indexOf("authorization:github:success:") === 0) {
    var payload = JSON.parse(e.data.slice("authorization:github:success:".length));
    chrome.storage.local.set({ githubToken: payload.token }, function () {
      window.removeEventListener("message", handleMessage);
      if (authWindow) authWindow.close();
      chrome.runtime.sendMessage({ type: "FLUSH_PENDING" });
      render();
    });
  } else if (e.data.indexOf("authorization:github:error:") === 0) {
    window.removeEventListener("message", handleMessage);
    statusBox.className = "status warn";
    statusBox.textContent = "로그인 실패 — 다시 시도해주세요";
  }
}

var authWindow = null;
loginBtn.addEventListener("click", function () {
  authWindow = window.open(AUTH_URL, "github-oauth", "width=600,height=700");
  window.addEventListener("message", handleMessage);
});

logoutBtn.addEventListener("click", function () {
  chrome.storage.local.remove(["githubToken"], render);
});

// ── 액세스 토큰 직접 입력 ──────────────────────────────────────
// OAuth 팝업 방식은 GitHub 로그인 페이지 자체의 Cross-Origin-Opener-Policy
// 때문에, 팝업이 github.com을 거쳐 갔다 오는 순간 원래 창과의 연결이
// 구조적으로 끊겨버려 안정적으로 동작하지 않는 걸 확인했다(로그인은
// 끝났는데 새 토큰이 이 창에 전달이 안 됨). Sveltia CMS도 같은 이유로
// "액세스 토큰으로 로그인"을 별도 제공하는 것과 같은 이유로, 여기도
// 토큰을 직접 붙여넣는 방식을 둔다 -- 팝업/postMessage 없이 그냥
// chrome.storage에 저장하면 끝이라 훨씬 안정적이다.
var patInput = document.getElementById("patInput");
var patStatus = document.getElementById("patStatus");
var patSaveBtn = document.getElementById("patSaveBtn");

patSaveBtn.addEventListener("click", function () {
  var value = patInput.value.trim();
  if (!value) {
    patStatus.className = "warn";
    patStatus.textContent = "토큰을 입력해주세요.";
    return;
  }
  patStatus.className = "";
  patStatus.textContent = "확인 중...";
  patSaveBtn.disabled = true;

  // 저장하기 전에 실제로 이 저장소에 쓸 수 있는 토큰인지 먼저 확인한다 --
  // 확인 없이 저장하면, 잘못된 토큰을 넣고도 몰랐다가 나중에 수집 실패
  // 로그를 보고서야 알게 되는 지금과 같은 상황이 반복된다.
  fetch("https://api.github.com/repos/hansunghee7/hansunghee7.github.io", {
    headers: { Authorization: "token " + value, Accept: "application/vnd.github+json" },
  })
    .then(function (r) {
      patSaveBtn.disabled = false;
      if (!r.ok) {
        return r.json().catch(function () { return {}; }).then(function (body) {
          patStatus.className = "warn";
          patStatus.textContent = "저장 안 됨 — " + r.status + (body && body.message ? " " + body.message : "") + ". 토큰과 저장소 접근 권한을 확인해주세요.";
        });
      }
      chrome.storage.local.set({ githubToken: value }, function () {
        patInput.value = "";
        patStatus.className = "ok";
        patStatus.textContent = "확인됨 — 저장했습니다.";
        chrome.runtime.sendMessage({ type: "FLUSH_PENDING" });
        render();
      });
    })
    .catch(function (e) {
      patSaveBtn.disabled = false;
      patStatus.className = "warn";
      patStatus.textContent = "확인 실패 — " + String((e && e.message) || e);
    });
});

render();
