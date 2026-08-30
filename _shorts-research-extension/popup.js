var briefInput = document.getElementById("briefInput");
var startBtn = document.getElementById("startBtn");
var statusBox = document.getElementById("statusBox");
var resultBox = document.getElementById("resultBox");
var resultText = document.getElementById("resultText");
var copyBtn = document.getElementById("copyBtn");
var logList = document.getElementById("logList");

function setStatus(kind, text) {
  statusBox.className = "status " + kind;
  statusBox.textContent = text;
}

function elapsedLabel(startedAt) {
  var mins = Math.floor((Date.now() - startedAt) / 60000);
  return mins < 1 ? "방금 시작" : mins + "분 경과";
}

function renderLog(log) {
  if (!log || !log.length) {
    logList.innerHTML = '<div class="log-empty">아직 기록 없음</div>';
    return;
  }
  logList.innerHTML = log.map(function (e) {
    var mark = e.status === "success" ? '<span class="mark success">✓ 완료</span>' : '<span class="mark error">✗ 실패</span>';
    var when = e.finishedAt ? new Date(e.finishedAt).toLocaleTimeString("ko-KR") : "";
    var note = e.status === "error" ? '<div class="hint">' + escapeHtml(e.note || "") + "</div>" : "";
    return (
      '<div class="log-item">' +
      '<div class="brief">' + escapeHtml(e.briefSnippet || "") + (e.briefSnippet && e.briefSnippet.length >= 80 ? "…" : "") + "</div>" +
      '<div class="meta">' + mark + "<span>" + when + "</span></div>" +
      note +
      "</div>"
    );
  }).join("");
}

function escapeHtml(s) {
  var div = document.createElement("div");
  div.textContent = s;
  return div.innerHTML;
}

function refreshFromStorage() {
  chrome.storage.local.get(["researchLog", "activeResearch"], function (res) {
    renderLog(res.researchLog);

    if (res.activeResearch) {
      startBtn.disabled = true;
      setStatus("running", "진행 중 — " + elapsedLabel(res.activeResearch.startedAt) + " (보통 5~20분)");
    } else if (res.researchLog && res.researchLog.length && res.researchLog[0].status === "success") {
      startBtn.disabled = false;
      setStatus("ok", "완료");
      resultBox.style.display = "block";
      resultText.value = res.researchLog[0].result || "";
    } else if (res.researchLog && res.researchLog.length && res.researchLog[0].status === "error") {
      startBtn.disabled = false;
      setStatus("error", "실패 — 아래 기록에서 원인 확인");
    } else {
      startBtn.disabled = false;
      setStatus("idle", "대기 중");
    }
  });
}

startBtn.addEventListener("click", function () {
  var brief = briefInput.value.trim();
  if (!brief) {
    setStatus("error", "브리프를 먼저 붙여넣으세요");
    return;
  }
  chrome.runtime.sendMessage({ type: "START_RESEARCH", brief: brief });
  startBtn.disabled = true;
  resultBox.style.display = "none";
  setStatus("running", "시작함 — gemini.google.com을 여는 중");
});

copyBtn.addEventListener("click", function () {
  navigator.clipboard.writeText(resultText.value).then(function () {
    copyBtn.textContent = "복사됨";
    setTimeout(function () { copyBtn.textContent = "결과 다시 복사"; }, 1500);
  });
});

// 진행 중일 때 팝업을 열어두면 경과 시간이 갱신되도록.
setInterval(refreshFromStorage, 5000);

chrome.storage.onChanged.addListener(function (changes) {
  if (changes.researchLog || changes.activeResearch) refreshFromStorage();
});

refreshFromStorage();
