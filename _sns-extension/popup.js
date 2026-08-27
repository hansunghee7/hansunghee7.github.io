// CMS(admin/index.html)가 GitHub 로그인할 때 쓰는 것과 똑같은 팝업창 +
// postMessage 방식(Decap/Netlify CMS 표준 OAuth 핸드셰이크)을 그대로
// 재사용합니다. 이미 배포되어 있는 simplifier-cms-auth 워커를 그대로
// 쓰기 때문에, 새 GitHub OAuth 앱이나 새 워커를 만들 필요가 없습니다.

var AUTH_URL = "https://simplifier-cms-auth.simon-8be.workers.dev/auth";

var statusBox = document.getElementById("statusBox");
var loginBtn = document.getElementById("loginBtn");
var logoutBtn = document.getElementById("logoutBtn");

function render() {
  chrome.storage.local.get(["githubToken", "pendingCaptures"], function (res) {
    if (res.githubToken) {
      statusBox.className = "status ok";
      statusBox.textContent = "GitHub 연결됨 — 자동 기록 작동 중";
      loginBtn.style.display = "none";
      logoutBtn.style.display = "block";
    } else {
      var pendingNote = res.pendingCaptures && res.pendingCaptures.length
        ? " (" + res.pendingCaptures.length + "건 대기 중)"
        : "";
      statusBox.className = "status warn";
      statusBox.textContent = "GitHub 연결 필요" + pendingNote;
      loginBtn.style.display = "block";
      logoutBtn.style.display = "none";
    }
  });
}

function handleMessage(e) {
  if (typeof e.data !== "string") return;

  if (e.data === "authorizing:github") {
    // 팝업이 보낸 최초 핸드셰이크 신호 -- 그대로 되돌려 보내 확인해줍니다.
    if (authWindow) authWindow.postMessage("authorizing:github", "*");
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

render();
