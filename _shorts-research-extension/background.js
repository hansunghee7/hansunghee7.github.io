// 팝업에서 "리서치 시작"을 누르면 여기가 받아서:
//  1) gemini.google.com을 화면에 안 보이는 최소화 창으로 연다
//     (_sns-extension과 같은 패턴 -- 사용자가 쓰던 창에 안 끼어든다)
//  2) content-script.js에 브리프를 전달해 입력·제출을 시킨다
//  3) 완료/실패 결과를 받아 기록하고 알림을 띄운다
//
// 완료되면 창을 잠깐 뒤 자동으로 닫는다(결과는 이미 팝업에 저장돼 있으니
// 안 봐도 됨). 실패하면 창을 안 닫는다 -- 뭐가 잘못됐는지 화면으로
// 직접 봐야 할 수도 있어서, 실패의 증거를 지우지 않는다.

var LOG_KEY = "researchLog";
var LOG_MAX = 15;
var CLOSE_DELAY_ON_SUCCESS_MS = 10000;
var SEND_RETRY_MAX = 8;
var SEND_RETRY_INTERVAL_MS = 1500;

function pushLog(entry) {
  chrome.storage.local.get([LOG_KEY], function (res) {
    var log = res[LOG_KEY] || [];
    log.unshift(entry);
    if (log.length > LOG_MAX) log = log.slice(0, LOG_MAX);
    chrome.storage.local.set({ researchLog: log });
  });
}

function notify(title, message) {
  chrome.notifications.create({
    type: "basic",
    iconUrl: "icons/icon128.png",
    title: title,
    message: message,
  });
}

// content-script가 로드 직후 리스너 등록을 마치기 전에 메시지를 보내면
// "Receiving end does not exist" 에러가 난다. Gemini는 SPA라 탭 status가
// "complete"여도 앱 렌더링이 덜 끝났을 수 있어서, 실패 시 잠깐 쉬었다가
// 몇 번 더 시도한다.
function sendInjectBriefWithRetry(tabId, brief, attempt) {
  chrome.tabs.sendMessage(tabId, { type: "INJECT_BRIEF", brief: brief }, function () {
    if (chrome.runtime.lastError) {
      if (attempt >= SEND_RETRY_MAX) {
        pushLog({
          briefSnippet: brief.slice(0, 80),
          startedAt: Date.now(),
          status: "error",
          note: "content script와 연결 실패 (재시도 " + SEND_RETRY_MAX + "회 초과): " + chrome.runtime.lastError.message,
        });
        notify("숏폼 리서치 실패", "gemini.google.com 페이지와 연결하지 못했습니다.");
        return;
      }
      setTimeout(function () {
        sendInjectBriefWithRetry(tabId, brief, attempt + 1);
      }, SEND_RETRY_INTERVAL_MS);
    }
  });
}

function startResearch(brief) {
  var startedAt = Date.now();
  chrome.windows.create(
    { url: "https://gemini.google.com/app", focused: false, state: "minimized" },
    function (win) {
      if (chrome.runtime.lastError || !win || !win.tabs || !win.tabs.length) {
        pushLog({
          briefSnippet: brief.slice(0, 80),
          startedAt: startedAt,
          status: "error",
          note: "창 생성 실패: " + (chrome.runtime.lastError && chrome.runtime.lastError.message),
        });
        notify("숏폼 리서치 실패", "gemini.google.com 창을 열지 못했습니다.");
        return;
      }
      var tabId = win.tabs[0].id;
      chrome.storage.local.set({ activeResearch: { tabId: tabId, brief: brief, startedAt: startedAt } });

      chrome.tabs.onUpdated.addListener(function listener(updatedTabId, info) {
        if (updatedTabId !== tabId || info.status !== "complete") return;
        chrome.tabs.onUpdated.removeListener(listener);
        // 페이지 자체 로드 완료 시점. SPA 렌더링 여유를 조금 더 준다.
        setTimeout(function () {
          sendInjectBriefWithRetry(tabId, brief, 0);
        }, 1500);
      });
    }
  );
}

chrome.runtime.onMessage.addListener(function (msg) {
  if (msg && msg.type === "START_RESEARCH") {
    startResearch(msg.brief);
  }

  // 딥리서치가 조사 계획을 제시하고 승인을 기다리는 단계. 탭은 그대로 두고,
  // 팝업에 "계획 확인 필요" 상태를 띄운다 -- 사람이 직접 계획을 읽고
  // 승인/취소를 결정해야 하므로 여기서 자동으로 진행시키지 않는다.
  if (msg && msg.type === "RESEARCH_PLAN_READY") {
    chrome.storage.local.get(["activeResearch"], function (res) {
      var active = res.activeResearch;
      chrome.storage.local.set({
        pendingPlan: {
          tabId: active ? active.tabId : null,
          planText: msg.planText,
          readyAt: Date.now(),
        },
      });
      notify("숏폼 리서치 — 계획 확인 필요", "제미나이가 조사 계획을 제시했습니다. 확장 팝업에서 확인 후 승인/취소하세요.");
    });
  }

  if (msg && msg.type === "APPROVE_PLAN") {
    chrome.storage.local.get(["pendingPlan"], function (res) {
      if (!res.pendingPlan || !res.pendingPlan.tabId) return;
      chrome.tabs.sendMessage(res.pendingPlan.tabId, { type: "CONFIRM_PLAN" }, function () { void chrome.runtime.lastError; });
      chrome.storage.local.remove("pendingPlan");
    });
  }

  if (msg && msg.type === "CANCEL_PLAN") {
    chrome.storage.local.get(["pendingPlan", "activeResearch"], function (res) {
      if (res.pendingPlan && res.pendingPlan.tabId) {
        chrome.tabs.sendMessage(res.pendingPlan.tabId, { type: "CANCEL_PLAN" }, function () { void chrome.runtime.lastError; });
      }
      chrome.storage.local.remove("pendingPlan");
    });
  }

  if (msg && msg.type === "RESEARCH_CANCELLED") {
    chrome.storage.local.get(["activeResearch"], function (res) {
      var active = res.activeResearch;
      pushLog({
        briefSnippet: active ? active.brief.slice(0, 80) : "",
        startedAt: active ? active.startedAt : Date.now(),
        finishedAt: Date.now(),
        status: "cancelled",
      });
      if (active && active.tabId) {
        chrome.tabs.remove(active.tabId, function () { void chrome.runtime.lastError; });
      }
      chrome.storage.local.remove("activeResearch");
      chrome.storage.local.remove("pendingPlan");
    });
  }

  if (msg && msg.type === "RESEARCH_COMPLETE") {
    chrome.storage.local.get(["activeResearch"], function (res) {
      var active = res.activeResearch;
      pushLog({
        briefSnippet: active ? active.brief.slice(0, 80) : "",
        startedAt: active ? active.startedAt : Date.now(),
        finishedAt: Date.now(),
        status: "success",
        result: msg.result,
        copiedToClipboard: msg.copiedToClipboard,
      });
      notify(
        "숏폼 리서치 완료",
        msg.copiedToClipboard
          ? "결과가 클립보드에 복사됐습니다. 바로 붙여넣으세요."
          : "결과가 준비됐습니다. 확장 팝업에서 확인 후 복사하세요."
      );
      if (active && active.tabId) {
        setTimeout(function () {
          chrome.tabs.remove(active.tabId, function () { void chrome.runtime.lastError; });
        }, CLOSE_DELAY_ON_SUCCESS_MS);
      }
      chrome.storage.local.remove("activeResearch");
      chrome.storage.local.remove("pendingPlan");
    });
  }

  if (msg && msg.type === "RESEARCH_ERROR") {
    chrome.storage.local.get(["activeResearch"], function (res) {
      var active = res.activeResearch;
      pushLog({
        briefSnippet: active ? active.brief.slice(0, 80) : "",
        startedAt: active ? active.startedAt : Date.now(),
        finishedAt: Date.now(),
        status: "error",
        note: msg.message,
      });
      notify("숏폼 리서치 실패", msg.message + " — 창을 열어둔 채로 두었으니 직접 확인해보세요.");
      chrome.storage.local.remove("activeResearch");
      chrome.storage.local.remove("pendingPlan");
      // 실패 시엔 탭을 안 닫는다 (파일 상단 설명 참고).
    });
  }
});
