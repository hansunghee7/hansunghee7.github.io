// gemini.google.com에서 브리프를 입력하고, 딥리서치 모드로 제출한 뒤,
// 응답이 끝날 때까지 기다렸다가 결과를 가로챈다.
//
// ⚠️ 이 파일에서 가장 불확실한 부분은 SELECTORS다. 이 세션은 로그인된
// gemini.google.com 화면을 직접 본 적이 없어서(콘솔 접근 불가), 아래
// 선택자는 "일반적으로 이런 구조일 것이다"라는 추정이다. 실제로 안 맞으면
// 콘솔에 "[숏폼 리서치]"로 시작하는 로그가 어디서 못 찾았는지 알려준다 --
// 그 로그를 보고 실제 요소를 찾아 이 파일의 SELECTORS만 고치면 된다.
//
// 검증하는 법 (F12 콘솔에 붙여넣기):
//   document.querySelector('[contenteditable="true"]')       // 입력창
//   [...document.querySelectorAll('button')].find(b => /전송|보내기|send/i.test(b.getAttribute('aria-label')||''))  // 전송 버튼
//   [...document.querySelectorAll('[role="menuitemradio"], button, div')].find(b => /딥\s*리서치|deep research/i.test(b.textContent||''))  // 모드 전환

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
    // 딥리서치 모드 진입점 -- "도구" 메뉴 안에 있을 수도, 입력창 옆 칩일
    // 수도 있다. 텍스트로 찾으므로 어디 있든 웬만하면 잡힌다.
    deepResearchToggle: {
      textPattern: /딥\s*리서치|deep\s*research/i,
      candidateTags: ["button", "div[role=\"menuitemradio\"]", "div[role=\"menuitem\"]", "span"],
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
  };

  var STABLE_MS = 12000; // 이만큼 DOM 변화가 없으면 "응답 끝났다"고 본다
  var MIN_RESEARCH_MS = 45000; // 딥리서치는 최소 이 정도는 걸리니, 그 전엔 끝났다고 오판하지 않는다
  var MAX_WAIT_MS = 25 * 60 * 1000; // 25분 넘으면 포기하고 타임아웃 보고

  function log() {
    var args = Array.prototype.slice.call(arguments);
    console.log.apply(console, [LOG_PREFIX].concat(args));
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
    return waitFor(function () { return findFirst(SELECTORS.input); }, 15000, 500).then(function (input) {
      // 딥리서치 모드 전환 -- 못 찾아도 실패시키지 않는다. 일반 모드로라도
      // 제출하는 게 아무것도 안 하는 것보다 낫고, 로그로 남겨서 나중에
      // 선택자를 고칠 근거를 남긴다.
      var toggle = findByText(SELECTORS.deepResearchToggle.candidateTags, SELECTORS.deepResearchToggle.textPattern);
      if (toggle) {
        toggle.click();
        log("딥리서치 모드 전환 클릭함");
      } else {
        log("⚠️ 딥리서치 모드 전환 버튼을 못 찾음 -- 일반 모드로 제출됩니다. 결과를 확인 후 SELECTORS.deepResearchToggle을 실제 화면 기준으로 고쳐주세요.");
      }

      insertText(input, brief);

      return waitFor(findSubmitButton, 5000, 300);
    }).then(function (submitBtn) {
      submitBtn.click();
      log("제출 완료, 응답 대기 시작");
      return waitForCompletion();
    });
  }

  // DOM 변화가 STABLE_MS 이상 없으면 응답이 끝난 것으로 본다. 폴링 대신
  // MutationObserver를 쓰는 이유: 탭이 백그라운드(최소화 창)에 있으면
  // setInterval/setTimeout이 브라우저에 의해 느려질 수 있는데, DOM 변화
  // 이벤트 자체는 그런 스로틀링의 영향을 덜 받는다.
  function waitForCompletion() {
    return new Promise(function (resolve, reject) {
      var startedAt = Date.now();
      var lastChangeAt = Date.now();
      var target = findFirst(SELECTORS.responseContainer) || document.body;

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
          copiedToClipboard: copied,
        });
      })
      .catch(function (err) {
        log("❌ 실패:", err.message);
        chrome.runtime.sendMessage({ type: "RESEARCH_ERROR", message: err.message });
      });

    sendResponse({ received: true });
    return true;
  });

  log("content script 로드됨, INJECT_BRIEF 대기 중");
})();
