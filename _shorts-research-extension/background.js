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

// 결과를 GitHub 이슈로도 남긴다(토큰이 저장돼 있을 때만) -- 클립보드/팝업은
// 이 확장을 켜둔 브라우저를 벗어나면 사라지지만, 이슈는 저장소에 남아서
// 탐(클로드)이 나중에 정기적으로 확인해 처리할 수 있는 착지점이 된다.
// 실패해도 기존 클립보드/팝업 결과 흐름을 막지 않는다 -- 완전히 부가적인
// 경로다.
var REPO = "hansunghee7/hansunghee7.github.io";

function openResearchIssue(brief, planText, resultText) {
  chrome.storage.local.get(["githubToken"], function (res) {
    if (!res.githubToken) return; // 미연결이면 조용히 건너뜀 -- README 참고
    var title = "[리서치 완료] " + brief.slice(0, 60) + (brief.length > 60 ? "…" : "");
    var body =
      "## 브리프\n\n" + brief +
      (planText ? "\n\n## 제미나이가 제시한 계획 (자동 승인됨)\n\n" + planText : "") +
      "\n\n## 결과\n\n" + resultText +
      "\n\n---\n_숏폼 리서치 자동화 확장이 자동으로 등록함 (" + new Date().toISOString() + ")_";

    fetch("https://api.github.com/repos/" + REPO + "/issues", {
      method: "POST",
      headers: {
        Authorization: "token " + res.githubToken,
        Accept: "application/vnd.github+json",
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ title: title, body: body }),
    })
      .then(function (r) {
        if (!r.ok) {
          return r.json().catch(function () { return {}; }).then(function (b) {
            console.log("[숏폼 리서치] GitHub 이슈 등록 실패:", r.status, b && b.message);
          });
        }
        console.log("[숏폼 리서치] GitHub 이슈 등록 완료");
      })
      .catch(function (e) {
        console.log("[숏폼 리서치] GitHub 이슈 등록 실패:", e.message);
      });
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

// content-script는 딥리서치 전환 버튼이나 응답 영역 선택자를 못 찾아도
// 조용히 fallback을 타고 계속 진행한다(README 참고) -- 기능은 안 죽지만
// 딥리서치 대신 일반 채팅으로 제출되는 것 같은 문제를 아무도 모른 채
// 지나갈 수 있다. 같은 종류가 MISS_WARN_THRESHOLD회 연속이면 팝업에
// 경고를 띄운다. "계획 확인 단계 없음"은 원래 짧은 요청이면 자연스럽게
// 발생하는 정상 케이스라 여기 포함하지 않는다.
var MISS_WARN_THRESHOLD = 2;
var MISS_KIND_LABELS = {
  deepResearchToggle: "딥리서치 모드 전환 버튼",
  responseContainer: "응답 영역",
};

function updateSelectorMissStreak(misses) {
  var missSet = {};
  (misses || []).forEach(function (k) { missSet[k] = true; });

  chrome.storage.local.get(["selectorMissStreak", "selectorWarning"], function (res) {
    var streak = res.selectorMissStreak || {};
    Object.keys(MISS_KIND_LABELS).forEach(function (kind) {
      var missed = !!missSet[kind];
      streak[kind] = missed ? (streak[kind] || 0) + 1 : 0;

      if (missed && streak[kind] === MISS_WARN_THRESHOLD) {
        chrome.storage.local.set({ selectorWarning: { kind: kind, streak: streak[kind], since: Date.now() } });
        notify(
          "숏폼 리서치 — 선택자 확인 필요",
          MISS_KIND_LABELS[kind] + "을(를) " + streak[kind] + "번 연속 못 찾았습니다. 화면 구조가 바뀌었을 수 있어요."
        );
      } else if (!missed && res.selectorWarning && res.selectorWarning.kind === kind) {
        chrome.storage.local.remove("selectorWarning");
      }
    });
    chrome.storage.local.set({ selectorMissStreak: streak });
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

function startResearch(brief, queueItemId) {
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
        if (queueItemId) updateQueueItemStatus(queueItemId, "error", "창 생성 실패");
        return;
      }
      var tabId = win.tabs[0].id;
      chrome.storage.local.set({
        activeResearch: { tabId: tabId, brief: brief, startedAt: startedAt, queueItemId: queueItemId || null },
      });

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

// ── 리서치 대기열 (무인 파이프라인) ────────────────────────────
// 사장님이 팝업을 열지 않아도, 이 저장소의 queue.json에 "pending" 항목을
// 추가해두면 알아서 하나씩 처리한다. chrome.alarms는 크롬이 켜져 있는 한
// (팝업/탭이 안 떠 있어도) 주기적으로 서비스 워커를 깨워주므로, 이 방식이
// 성립한다 -- 단, 크롬 자체는 실행 중이어야 한다(README 참고).
var QUEUE_PATH = "_shorts-research-extension/queue.json";
var QUEUE_ALARM = "checkResearchQueue";
var QUEUE_CHECK_PERIOD_MIN = 10;

chrome.alarms.create(QUEUE_ALARM, { periodInMinutes: QUEUE_CHECK_PERIOD_MIN });
chrome.runtime.onInstalled.addListener(function () {
  chrome.alarms.create(QUEUE_ALARM, { periodInMinutes: QUEUE_CHECK_PERIOD_MIN });
});

// ── 워치독 ──────────────────────────────────────────────────────
// content-script.js 안에는 이미 "25분 넘으면 타임아웃"이라는 로직이
// 있지만, 그건 최소화된 창 안의 자바스크립트가 실제로 계속 돌고 있을
// 때만 동작한다. 크롬이 메모리 절약을 위해 안 쓰는 백그라운드 탭을
// 정지(discard)시키면 그 안의 타이머·감시 로직이 통째로 멈춰버려서,
// "타임아웃되면 실패 처리한다"는 로직 자체가 실행이 안 될 수 있다 --
// 관측할 수 없는 구간(그 탭 안에서 실제로 무슨 일이 있었는지)이라, 원인을
// 캐기보다 그 구간에 의존하지 않는 별도 감시자를 둔다. background.js는
// 항상 살아서 알람을 받으므로, 여기서 독립적으로 "너무 오래 걸리면
// 강제로 정리"한다 -- 특히 대기열은 activeResearch가 안 지워지면 다음
// 항목으로 영영 못 넘어가므로 이게 없으면 무인 파이프라인 전체가 멈춘다.
var WATCHDOG_ALARM = "researchWatchdog";
var WATCHDOG_PERIOD_MIN = 5;
var STUCK_THRESHOLD_MS = 30 * 60 * 1000; // content-script 자체 타임아웃(25분)보다 여유를 둠

chrome.alarms.create(WATCHDOG_ALARM, { periodInMinutes: WATCHDOG_PERIOD_MIN });
chrome.runtime.onInstalled.addListener(function () {
  chrome.alarms.create(WATCHDOG_ALARM, { periodInMinutes: WATCHDOG_PERIOD_MIN });
});

function checkWatchdog() {
  chrome.storage.local.get(["activeResearch"], function (res) {
    var active = res.activeResearch;
    if (!active || Date.now() - active.startedAt < STUCK_THRESHOLD_MS) return;

    console.log("[숏폼 리서치] 워치독: " + Math.round(STUCK_THRESHOLD_MS / 60000) + "분 넘게 응답 없음 -- 강제 정리");
    pushLog({
      briefSnippet: active.brief.slice(0, 80),
      startedAt: active.startedAt,
      finishedAt: Date.now(),
      status: "error",
      note: "워치독: " + Math.round(STUCK_THRESHOLD_MS / 60000) + "분 넘게 응답이 없어 중단 처리함 (탭이 멈췄거나 크롬이 백그라운드 탭을 정지시켰을 수 있음)",
      source: active.queueItemId ? "queue" : "manual",
    });
    if (active.queueItemId) updateQueueItemStatus(active.queueItemId, "error", "워치독 타임아웃");
    notify("숏폼 리서치 — 응답 없음", "실행이 멈춘 것 같아 정리했습니다. 대기열이 있으면 다음 항목으로 이어서 진행합니다.");
    chrome.storage.local.remove("activeResearch");
    // 탭 자체는 안 닫는다 -- 화면에 뭐가 남아있는지 확인이 필요할 수 있어서
    // (파일 상단 "실패 시 탭을 안 닫는다" 정책과 동일).
  });
}

function fetchQueue(token) {
  return fetch("https://api.github.com/repos/" + REPO + "/contents/" + QUEUE_PATH, {
    headers: { Authorization: "token " + token, Accept: "application/vnd.github+json" },
  }).then(function (r) {
    if (!r.ok) throw new Error("큐 조회 실패: HTTP " + r.status);
    return r.json();
  }).then(function (fileRes) {
    var items;
    try {
      items = JSON.parse(decodeURIComponent(escape(atob(fileRes.content.replace(/\n/g, "")))));
    } catch (e) {
      items = [];
    }
    return { items: items, sha: fileRes.sha };
  });
}

function writeQueue(token, items, sha, message) {
  return fetch("https://api.github.com/repos/" + REPO + "/contents/" + QUEUE_PATH, {
    method: "PUT",
    headers: {
      Authorization: "token " + token,
      Accept: "application/vnd.github+json",
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      message: message + " [skip ci]",
      content: btoa(unescape(encodeURIComponent(JSON.stringify(items, null, 2) + "\n"))),
      sha: sha,
    }),
  });
}

// 대기열 항목 하나의 상태를 바꾼다. 사람이 그 사이 queue.json을 손으로
// 고쳤을 수도 있어서(항목 추가 등) sha 충돌(409) 시 한 번만 재조회 후
// 재시도한다 -- _sns-extension만큼 몰릴 일이 없어서(한 번에 하나씩만
// 처리) 간단한 재시도로 충분하다.
function updateQueueItemStatus(queueItemId, status, note, retried) {
  chrome.storage.local.get(["githubToken"], function (res) {
    if (!res.githubToken) return;
    fetchQueue(res.githubToken).then(function (q) {
      var item = q.items.filter(function (i) { return i.id === queueItemId; })[0];
      if (!item) return;
      item.status = status;
      item.finishedAt = new Date().toISOString();
      if (note) item.note = note;
      return writeQueue(res.githubToken, q.items, q.sha, "chore: 리서치 대기열 갱신 (" + queueItemId + " -> " + status + ")");
    }).then(function (putRes) {
      if (putRes && putRes.status === 409 && !retried) {
        updateQueueItemStatus(queueItemId, status, note, true);
        return;
      }
      if (putRes && !putRes.ok) console.log("[숏폼 리서치] 큐 갱신 실패:", putRes.status);
    }).catch(function (e) {
      console.log("[숏폼 리서치] 큐 갱신 실패:", e.message);
    });
  });
}

function checkQueueAndStart() {
  chrome.storage.local.get(["githubToken", "activeResearch"], function (res) {
    if (!res.githubToken) return; // 큐도 GitHub 연결이 있어야 동작 (README 참고)
    if (res.activeResearch) return; // 이미 하나 도는 중이면 겹치지 않게 건너뜀

    fetchQueue(res.githubToken).then(function (q) {
      var pending = q.items.filter(function (i) { return i.status === "pending"; })[0];
      if (!pending) return;

      pending.status = "in_progress";
      pending.startedAt = new Date().toISOString();
      return writeQueue(res.githubToken, q.items, q.sha, "chore: 리서치 대기열 시작 (" + pending.id + ")").then(function (putRes) {
        if (!putRes.ok) {
          console.log("[숏폼 리서치] 큐 항목 점유 실패(다른 곳에서 먼저 처리했을 수 있음):", putRes.status);
          return;
        }
        console.log("[숏폼 리서치] 대기열에서 실행:", pending.id);
        startResearch(pending.brief, pending.id);
      });
    }).catch(function (e) {
      console.log("[숏폼 리서치] 큐 확인 실패:", e.message);
    });
  });
}

chrome.alarms.onAlarm.addListener(function (alarm) {
  if (alarm.name === QUEUE_ALARM) checkQueueAndStart();
  if (alarm.name === WATCHDOG_ALARM) checkWatchdog();
});

chrome.runtime.onMessage.addListener(function (msg) {
  if (msg && msg.type === "START_RESEARCH") {
    startResearch(msg.brief);
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
        source: active && active.queueItemId ? "queue" : "manual",
      });
      updateSelectorMissStreak(msg.misses);
      openResearchIssue(active ? active.brief : "", msg.planText, msg.result);
      if (active && active.queueItemId) updateQueueItemStatus(active.queueItemId, "done");
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
        source: active && active.queueItemId ? "queue" : "manual",
      });
      updateSelectorMissStreak(msg.misses);
      if (active && active.queueItemId) updateQueueItemStatus(active.queueItemId, "error", msg.message);
      notify("숏폼 리서치 실패", msg.message + " — 창을 열어둔 채로 두었으니 직접 확인해보세요.");
      chrome.storage.local.remove("activeResearch");
      // 실패 시엔 탭을 안 닫는다 (파일 상단 설명 참고).
    });
  }

  if (msg && msg.type === "DISMISS_SELECTOR_WARNING") {
    chrome.storage.local.get(["selectorMissStreak", "selectorWarning"], function (res) {
      var streak = res.selectorMissStreak || {};
      if (res.selectorWarning) streak[res.selectorWarning.kind] = 0;
      chrome.storage.local.set({ selectorMissStreak: streak });
      chrome.storage.local.remove("selectorWarning");
    });
  }
});
