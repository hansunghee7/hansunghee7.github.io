// gemini.google.com에서 브리프를 입력하고, 딥리서치 모드로 제출한 뒤,
// 응답이 끝날 때까지 기다렸다가 결과를 가로챈다.
//
// ⚠️ 이 파일에서 가장 불확실한 부분은 SELECTORS다. 실제 화면을 보고
// 확인된 부분(2026-08-30, 사장님 직접 확인)도 있고, 여전히 추정인
// 부분도 있다. 실제로 안 맞으면 콘솔에 "[숏폼 리서치]"로 시작하는
// 로그가 어디서 못 찾았는지 알려준다 -- 그 로그를 보고 실제 요소를
// 찾아 이 파일의 SELECTORS만 고치면 된다.
//
// ✅ 확인됨: 딥리서치 모드는 "딥 리서치" 글자가 화면에 바로 안 보이고,
// 입력창 영역의 "+" 버튼을 먼저 눌러야 그 메뉴 안에 나타난다(2단계).
//
// 검증하는 법 (F12 콘솔에 붙여넣기):
//   document.querySelector('[contenteditable="true"]')       // 입력창
//   [...document.querySelectorAll('button')].find(b => /전송|보내기|send/i.test(b.getAttribute('aria-label')||''))  // 전송 버튼
//   [...document.querySelectorAll('button')].find(b => (b.textContent||'').trim()==='+')  // "+" 버튼
//   // 위 "+"를 실제로 클릭한 다음에 아래를 실행해야 메뉴가 열려있어 잡힌다:
//   [...document.querySelectorAll('[role="menuitemradio"], [role="menuitem"], button, li, span')].find(b => /딥\s*리서치|deep research/i.test(b.textContent||''))  // 딥 리서치 메뉴 항목

(function () {
  var LOG_PREFIX = "[숏폼 리서치]";

  // 실제 페이지에서 확인 전까지는 전부 "최선의 추정 + 일반적 대안"이다.
  var SELECTORS = {
    // Gemini 웹앱 입력창은 지금까지 관찰된 버전들에서 대체로 리치텍스트
    // contenteditable div였다. class는 자주 바뀌므로 속성 기반으로 찾는다.
    input: [
      'div[contenteditable="true"][role="textbox"]',
      'div.ql-editor[contenteditable="true"]',
      'div[contenteditable="true"]',
    ],
    // 딥리서치 모드는 "딥 리서치"라는 글자가 화면에 바로 보이지 않는다 --
    // 입력창 영역의 "+" 버튼을 먼저 눌러야 그 안에 딥 리서치를 포함한
    // 도구 메뉴가 펼쳐진다(실제 화면 확인함, 2026-08-30). 그래서 2단계로
    // 찾는다: (1) "+" 버튼 클릭 (2) 펼쳐진 메뉴에서 "딥 리서치" 항목 클릭.
    deepResearchToggle: {
      plusButton: {
        exactTextPattern: /^\+$/,
        ariaPattern: /도구|추가|tools|add|plus/i,
      },
      menuItemPattern: /딥\s*리서치|deep\s*research/i,
      menuItemTags: ["div[role=\"menuitemradio\"]", "div[role=\"menuitem\"]", "button", "li", "span"],
    },
    submitButton: {
      ariaPattern: /전송|보내기|submit|send/i,
      fallback: 'button[type="submit"]',
    },
    // 응답이 나오는 영역. 못 찾으면 document.body 전체를 관찰한다(더 느슨하지만
    // 항상 동작은 한다).
    responseContainer: [
      '[data-response-index]',
      '.response-container',
      "main",
    ],
    // 딥리서치는 보통 "이런 계획으로 조사할게요, 진행할까요?" 확인 버튼을
    // 먼저 띄우고, 사용자가 승인해야 진짜 조사가 시작된다. 이것도 실제 화면을
    // 못 본 채 추정한 값이라 이름이 다를 수 있다 -- 못 찾으면 로그로 남기고
    // 계획 단계 없이 바로 완료 감지로 넘어간다(질문이 짧아서 계획 단계가
    // 아예 없는 경우와 구분이 안 되지만, 안전한 쪽으로 fallback).
    planConfirmButton: {
      textPattern: /계획대로|리서치\s*시작|조사\s*시작|research\s*plan|start\s*research|진행할까요|시작할까요|승인/i,
      candidateTags: ["button", "div[role=\"button\"]", "div[role=\"menuitem\"]"],
    },
  };

  var STABLE_MS = 12000; // 이만큼 DOM 변화가 없으면 "응답 끝났다"고 본다
  var MIN_RESEARCH_MS = 45000; // 딥리서치는 최소 이 정도는 걸리니, 그 전엔 끝났다고 오판하지 않는다
  var MAX_WAIT_MS = 25 * 60 * 1000; // 25분 넘으면 포기하고 타임아웃 보고
  var PLAN_WAIT_MS = 90000; // 계획 확인 버튼이 뜨는지 이만큼 기다려본다 (안 뜨면 계획 단계 없다고 판단)

  // 이번 실행에서 계획이 나왔다면 그 원문을 담아둔다 -- 사람이 승인하지
  // 않고 자동으로 진행하지만(무인 파이프라인 목표상 사람이 없을 수 있음),
  // 계획 내용은 완료/실패 결과에 실어 GitHub 이슈에 남긴다 -- 뭘 조사했는지
  // 나중에라도 확인할 수 있게.
  var runPlanText = null;

  function log() {
    var args = Array.prototype.slice.call(arguments);
    console.log.apply(console, [LOG_PREFIX].concat(args));
  }

  // 선택자를 못 찾아도 지금까지는 콘솔 경고만 남기고 "일반 모드로라도
  // 계속 진행"했다 -- 기능은 안 죽지만, 딥리서치 대신 일반 채팅으로
  // 조용히 제출되는 것도 모르고 지나갈 수 있다. 이번 실행에서 어떤
  // 선택자가 fallback을 탔는지 모아뒀다가 완료/실패 메시지에 실어
  // background로 보낸다 -- background가 연속 발생 여부를 판단한다.
  var runMisses = {};
  function recordMiss(kind) {
    runMisses[kind] = true;
  }

  function findFirst(selectors) {
    for (var i = 0; i < selectors.length; i++) {
      var el = document.querySelector(selectors[i]);
      if (el) {
        log("입력창 후보 찾음:", selectors[i]);
        return el;
      }
    }
    return null;
  }

  function findByText(candidateTags, pattern) {
    for (var i = 0; i < candidateTags.length; i++) {
      var els = document.querySelectorAll(candidateTags[i]);
      for (var j = 0; j < els.length; j++) {
        if (pattern.test(els[j].textContent || "")) return els[j];
      }
    }
    return null;
  }

  function findSubmitButton() {
    var buttons = document.querySelectorAll("button");
    for (var i = 0; i < buttons.length; i++) {
      var label = buttons[i].getAttribute("aria-label") || "";
      if (SELECTORS.submitButton.ariaPattern.test(label)) return buttons[i];
    }
    return document.querySelector(SELECTORS.submitButton.fallback);
  }

  function findPlusButton() {
    var buttons = document.querySelectorAll("button");
    for (var i = 0; i < buttons.length; i++) {
      var b = buttons[i];
      var text = (b.textContent || "").trim();
      var label = b.getAttribute("aria-label") || "";
      if (SELECTORS.deepResearchToggle.plusButton.exactTextPattern.test(text)) return b;
      if (SELECTORS.deepResearchToggle.plusButton.ariaPattern.test(label)) return b;
    }
    return null;
  }

  // "+" 버튼을 눌러 도구 메뉴를 펼친 뒤, 그 안에서 "딥 리서치" 항목을 찾아
  // 클릭한다. 실패해도 submitBrief 자체는 계속 진행한다 -- 딥리서치 없이
  // 일반 채팅으로라도 제출되는 게 아무것도 안 하는 것보다 낫고, 놓친
  // 지점은 recordMiss로 남겨서 팝업 경고로 드러나게 한다.
  function enableDeepResearch() {
    var plusBtn = findPlusButton();
    if (!plusBtn) {
      log("⚠️ '+' 버튼을 못 찾음 -- 딥리서치 모드 전환 없이 일반 모드로 진행합니다.");
      recordMiss("deepResearchToggle");
      return Promise.resolve();
    }
    plusBtn.click();
    log("'+' 버튼 클릭함, 딥 리서치 메뉴 항목 대기 중");
    return waitFor(function () {
      return findByText(SELECTORS.deepResearchToggle.menuItemTags, SELECTORS.deepResearchToggle.menuItemPattern);
    }, 5000, 300).then(function (menuItem) {
      menuItem.click();
      log("딥리서치 모드 전환 클릭함");
    }, function () {
      log("⚠️ '+' 메뉴는 열렸지만 '딥 리서치' 항목을 못 찾음 -- 일반 모드로 진행합니다. SELECTORS.deepResearchToggle.menuItemPattern 확인 필요.");
      recordMiss("deepResearchToggle");
    });
  }

  // contenteditable div에 텍스트를 넣는다. React 기반 앱은 textContent를
  // 직접 바꾸는 것만으론 내부 상태가 안 바뀌는 경우가 많아서(입력 이벤트를
  // 안 받았다고 인식), execCommand로 "실제 타이핑처럼" 넣고 input 이벤트도
  // 명시적으로 한 번 더 쏜다. execCommand가 deprecated이긴 하지만 이런
  // 용도로는 아직 가장 안정적으로 동작한다.
  function insertText(el, text) {
    el.focus();
    var ok = false;
    try {
      ok = document.execCommand("insertText", false, text);
    } catch (e) {
      ok = false;
    }
    if (!ok) {
      el.textContent = text;
    }
    el.dispatchEvent(new InputEvent("input", { bubbles: true, data: text, inputType: "insertText" }));
    log("입력 완료 (execCommand 성공:", ok, ")");
  }

  function waitFor(checkFn, timeoutMs, intervalMs) {
    return new Promise(function (resolve, reject) {
      var elapsed = 0;
      var timer = setInterval(function () {
        var result = checkFn();
        if (result) {
          clearInterval(timer);
          resolve(result);
          return;
        }
        elapsed += intervalMs;
        if (elapsed >= timeoutMs) {
          clearInterval(timer);
          reject(new Error("타임아웃 (" + timeoutMs + "ms)"));
        }
      }, intervalMs);
    });
  }

  function submitBrief(brief) {
    runMisses = {};
    runPlanText = null;
    var inputEl;
    return waitFor(function () { return findFirst(SELECTORS.input); }, 15000, 500).then(function (input) {
      inputEl = input;
      return enableDeepResearch();
    }).then(function () {
      insertText(inputEl, brief);
      return waitFor(findSubmitButton, 5000, 300);
    }).then(function (submitBtn) {
      submitBtn.click();
      log("제출 완료, 계획 제시 여부 확인 중");
      return waitForPlanThenAutoApprove();
    }).then(function () {
      log("실제 조사 시작됨, 응답 대기 시작");
      return waitForCompletion();
    });
  }

  // 딥리서치는 보통 (1) "이런 계획으로 조사할게요, 진행할까요?"를 먼저
  // 보여주고 (2) 승인해야 (3) 진짜 조사가 시작된다. 예전엔 이 단계에서
  // 사람이 팝업으로 승인/취소하게 했지만, 무인 파이프라인(사장님 없이도
  // 대기열이 스스로 돌아가는 것)이 목표가 되면서 사람 개입 지점을 없앴다
  // -- 계획이 뜨면 즉시 자동 승인한다. 대신 계획 원문은 결과에 실어
  // GitHub 이슈에 남긴다 (runPlanText). 계획 단계 자체가 없으면(질문이
  // 짧거나 선택자가 안 맞는 경우) 조용히 다음 단계로 넘어간다.
  function waitForPlanThenAutoApprove() {
    var button = findByText(SELECTORS.planConfirmButton.candidateTags, SELECTORS.planConfirmButton.textPattern);
    if (button) return autoApprovePlan(button);

    return waitFor(function () {
      return findByText(SELECTORS.planConfirmButton.candidateTags, SELECTORS.planConfirmButton.textPattern);
    }, PLAN_WAIT_MS, 1000).then(autoApprovePlan, function () {
      log("계획 확인 단계 없음(또는 못 찾음) -- 바로 조사가 시작된 것으로 보고 진행합니다.");
      return null;
    });
  }

  function extractPlanText(button) {
    var block = button.closest('[data-response-index], .response-container, article, section') || null;
    var text = block ? (block.innerText || "") : "";
    if (!text || text.length < 20) {
      var fallback = findFirst(SELECTORS.responseContainer) || document.body;
      text = (fallback.innerText || "").slice(-4000);
    }
    return text.trim();
  }

  function autoApprovePlan(button) {
    runPlanText = extractPlanText(button);
    log("계획 제시 감지됨, 자동 승인 진행");
    button.click();
  }

  // DOM 변화가 STABLE_MS 이상 없으면 응답이 끝난 것으로 본다. 폴링 대신
  // MutationObserver를 쓰는 이유: 탭이 백그라운드(최소화 창)에 있으면
  // setInterval/setTimeout이 브라우저에 의해 느려질 수 있는데, DOM 변화
  // 이벤트 자체는 그런 스로틀링의 영향을 덜 받는다.
  function waitForCompletion() {
    return new Promise(function (resolve, reject) {
      var startedAt = Date.now();
      var lastChangeAt = Date.now();
      var target = findFirst(SELECTORS.responseContainer);
      if (!target) {
        log("⚠️ 응답 영역 선택자를 못 찾음 -- document.body 전체를 관찰합니다. SELECTORS.responseContainer 확인 필요.");
        recordMiss("responseContainer");
        target = document.body;
      }

      var observer = new MutationObserver(function () {
        lastChangeAt = Date.now();
      });
      observer.observe(target, { childList: true, subtree: true, characterData: true });

      var checkTimer = setInterval(function () {
        var now = Date.now();
        var elapsed = now - startedAt;
        var quietFor = now - lastChangeAt;

        if (elapsed > MAX_WAIT_MS) {
          clearInterval(checkTimer);
          observer.disconnect();
          reject(new Error("응답이 " + Math.round(MAX_WAIT_MS / 60000) + "분 넘게 안 끝남 -- 타임아웃"));
          return;
        }

        if (elapsed > MIN_RESEARCH_MS && quietFor > STABLE_MS) {
          clearInterval(checkTimer);
          observer.disconnect();
          var text = (target.innerText || target.textContent || "").trim();
          if (!text) {
            reject(new Error("응답 영역에서 텍스트를 못 읽음 -- SELECTORS.responseContainer 확인 필요"));
            return;
          }
          log("응답 안정화 감지, 총 소요:", Math.round(elapsed / 1000) + "초");
          resolve(text);
        }
      }, 2000);
    });
  }

  async function copyToClipboard(text) {
    try {
      await navigator.clipboard.writeText(text);
      log("클립보드 복사 성공");
      return true;
    } catch (e) {
      // 백그라운드 탭/포커스 없는 상태에서 클립보드 API가 브라우저 정책으로
      // 조용히 막힐 수 있다. 그래서 이 실패가 곧 기능 실패는 아니다 --
      // background.js가 결과 텍스트를 어차피 저장해서 팝업에서 수동 복사
      // 가능하게 한다.
      log("⚠️ 자동 클립보드 복사 실패(정상적인 브라우저 정책일 수 있음):", e.message);
      return false;
    }
  }

  chrome.runtime.onMessage.addListener(function (msg, sender, sendResponse) {
    if (!msg || msg.type !== "INJECT_BRIEF") return;

    submitBrief(msg.brief)
      .then(async function (resultText) {
        var copied = await copyToClipboard(resultText);
        chrome.runtime.sendMessage({
          type: "RESEARCH_COMPLETE",
          result: resultText,
          planText: runPlanText,
          copiedToClipboard: copied,
          misses: Object.keys(runMisses),
        });
      })
      .catch(function (err) {
        log("❌ 실패:", err.message);
        chrome.runtime.sendMessage({ type: "RESEARCH_ERROR", message: err.message, misses: Object.keys(runMisses) });
      });

    sendResponse({ received: true });
    return true;
  });

  log("content script 로드됨, INJECT_BRIEF 대기 중");
})();
