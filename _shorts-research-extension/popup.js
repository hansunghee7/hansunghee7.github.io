var briefInput = document.getElementById("briefInput");
var startBtn = document.getElementById("startBtn");
var statusBox = document.getElementById("statusBox");
var resultBox = document.getElementById("resultBox");
var resultText = document.getElementById("resultText");
var copyBtn = document.getElementById("copyBtn");
var logList = document.getElementById("logList");
var planBox = document.getElementById("planBox");
var planText = document.getElementById("planText");
var approveBtn = document.getElementById("approveBtn");
var cancelBtn = document.getElementById("cancelBtn");
var selectorWarningBox = document.getElementById("selectorWarningBox");
var selectorWarningText = document.getElementById("selectorWarningText");
var dismissWarningBtn = document.getElementById("dismissWarningBtn");

var MISS_KIND_LABELS = {
  deepResearchToggle: "딥리서치 모드 전환 버튼",
  responseContainer: "응답 영역",
};

function renderSelectorWarning(warning) {
  if (!warning) {
    selectorWarningBox.style.display = "none";
    return;
  }
  var label = MISS_KIND_LABELS[warning.kind] || warning.kind;
  selectorWarningText.textContent =
    label + "을(를) " + warning.streak + "번 연속 못 찾았습니다 — 화면 구조가 바뀌었을 수 있어요. 콘솔 로그로 확인해주세요.";
  selectorWarningBox.style.display = "block";
}

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
    var mark = e.status === "success"
      ? '<span class="mark success">✓ 완료</span>'
      : e.status === "cancelled"
      ? '<span class="mark cancelled">– 취소됨</span>'
      : '<span class="mark error">✗ 실패</span>';
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
  chrome.storage.local.get(["researchLog", "activeResearch", "pendingPlan", "selectorWarning"], function (res) {
    renderLog(res.researchLog);
    renderSelectorWarning(res.selectorWarning);

    if (res.pendingPlan) {
      startBtn.disabled = true;
      resultBox.style.display = "none";
      planBox.style.display = "block";
      planText.value = res.pendingPlan.planText || "(계획 내용을 가져오지 못했습니다 — 탭을 직접 확인해보세요)";
      setStatus("running", "계획 확인 필요 — 위 내용을 읽고 승인/취소하세요");
      return;
    }
    planBox.style.display = "none";

    if (res.activeResearch) {
      startBtn.disabled = true;
      setStatus("running", "진행 중 — " + elapsedLabel(res.activeResearch.startedAt) + " (보통 5~20분)");
    } else if (res.researchLog && res.researchLog.length && res.researchLog[0].status === "cancelled") {
      startBtn.disabled = false;
      setStatus("cancelled", "취소됨");
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
  planBox.style.display = "none";
  setStatus("running", "시작함 — gemini.google.com을 여는 중");
});

approveBtn.addEventListener("click", function () {
  chrome.runtime.sendMessage({ type: "APPROVE_PLAN" });
  planBox.style.display = "none";
  setStatus("running", "승인함 — 실제 조사를 시작하는 중");
});

cancelBtn.addEventListener("click", function () {
  chrome.runtime.sendMessage({ type: "CANCEL_PLAN" });
  planBox.style.display = "none";
});

dismissWarningBtn.addEventListener("click", function () {
  chrome.runtime.sendMessage({ type: "DISMISS_SELECTOR_WARNING" });
  selectorWarningBox.style.display = "none";
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
  if (changes.researchLog || changes.activeResearch || changes.pendingPlan || changes.selectorWarning) refreshFromStorage();
});

// ── GitHub 연결 (선택) ──────────────────────────────────────────
// _sns-extension의 PAT 붙여넣기 방식을 그대로 재사용한다 -- OAuth 팝업보다
// 훨씬 안정적으로 동작하는 걸 이미 확인했기 때문. 저장 전에 이 저장소에
// 쓸 수 있는 토큰인지 먼저 확인해서, 잘못된 토큰을 넣고도 몰랐다가
// 나중에야 알게 되는 상황을 막는다.
var githubStatus = document.getElementById("githubStatus");
var patInput = document.getElementById("patInput");
var patStatus = document.getElementById("patStatus");
var patSaveBtn = document.getElementById("patSaveBtn");

function renderGithubStatus(token) {
  if (token) {
    githubStatus.style.display = "block";
    githubStatus.textContent = "GitHub 연결됨 — 완료 시 이슈로도 자동 등록됩니다";
  } else {
    githubStatus.style.display = "none";
  }
}

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
        renderGithubStatus(value);
      });
    })
    .catch(function (e) {
      patSaveBtn.disabled = false;
      patStatus.className = "warn";
      patStatus.textContent = "확인 실패 — " + String((e && e.message) || e);
    });
});

chrome.storage.local.get(["githubToken"], function (res) {
  renderGithubStatus(res.githubToken);
});

refreshFromStorage();
