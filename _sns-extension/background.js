// content-script가 잡아낸 팔로워 수를 받아서, GitHub 저장소의
// assets/data/sns-insight.json 파일에 오늘 날짜로 기록합니다.
// 같은 날 같은 플랫폼이 여러 번 잡히면 그날 값을 덮어씁니다(하루 1개).
//
// 로그인(GitHub 토큰) 전에 잡힌 값은 버리지 않고 pendingCaptures에
// 쌓아두었다가, popup에서 로그인하면 그때 한꺼번에 반영합니다.

var REPO = "hansunghee7/hansunghee7.github.io";
var DATA_PATH = "assets/data/sns-insight.json";

// 팝업에서 "최근 수집 기록"으로 보여주는 로그. 최신이 앞에 오게 쌓고
// LOG_MAX개까지만 남긴다 -- 성공/실패 여부를 확인할 방법이 지금까지
// 전혀 없었어서(에러도 조용히 무시했음) 추가함.
var LOG_KEY = "recentLog";
var LOG_MAX = 15;

function pushLog(entry) {
  chrome.storage.local.get([LOG_KEY], function (res) {
    var log = res[LOG_KEY] || [];
    log.unshift(entry);
    if (log.length > LOG_MAX) log = log.slice(0, LOG_MAX);
    chrome.storage.local.set({ recentLog: log });
  });
}

chrome.runtime.onMessage.addListener(function (msg) {
  if (msg && msg.type === "SNS_CAPTURE") {
    handleCapture(msg);
  }
});

// ── 8개 SNS 전체 수집 한 바퀴 ──────────────────────────────────
// 가족 공유 PC라 특정 시각에 PC가 켜져 있다는 보장이 없어서(실제로
// Windows 예약 작업이 한 번도 자동 실행 안 됐던 걸 확인함), 정해진 시각
// 예약 대신 "사용자가 SNS를 신경 쓰는 순간"에 8개 프로필을 백그라운드
// 탭(화면에 안 보이는 새 탭)으로 조용히 열었다가 자동으로 닫으면서
// 갱신한다. 이 신호는 세 군데서 온다:
//   1) SNS 인사이트 대시보드 페이지를 열 때 (dashboard-trigger.js)
//   2) 그 페이지에서 새로고침 버튼을 누를 때 -- 이건 사용자가 명시적으로
//      "지금 다시 확인해줘"라고 요청한 것이므로 쿨다운을 건너뛴다(force).
//   3) 8개 플랫폼 중 아무 한 곳이라도 직접 방문할 때 (content-script.js)
//      -- 하나만 봐도 나머지도 같이 도니, 굳이 대시보드까지 안 들어가도
//      자연스러운 SNS 사용만으로 데이터가 쌓인다.
// 페이지를 여러 번 열어도 매번 8개를 다 열진 않게 쿨다운을 둔다(강제
// 새로고침 제외).
var DASHBOARD_PLATFORMS = [
  "https://www.linkedin.com/in/simplifier",
  "https://www.facebook.com/simplifier.seoul",
  "https://www.instagram.com/simplifier_seoul/",
  "https://www.threads.com/?hl=ko",
  "https://blog.naver.com/simplifiers",
  "https://brunch.co.kr/@simplifier",
  "https://connect.rememberapp.co.kr/profile/1582110/posts",
  "https://www.rocketpunch.com/@simplfier/post",
];
var ROUND_COOLDOWN_MS = 20 * 60 * 1000; // 20분 이내 재방문은 다시 안 돈다(강제 새로고침 제외)
var TAB_CLOSE_DELAY_MS = 22000; // content-script가 최대 20초까지 찾으니 여유 두고 닫음

chrome.runtime.onMessage.addListener(function (msg) {
  if (msg && msg.type === "SNS_COLLECT_REQUEST") {
    console.log("[SNS 인사이트] SNS_COLLECT_REQUEST 수신 (force=" + !!msg.force + ")");
    maybeRunFullRound(!!msg.force);
  }
});

function maybeRunFullRound(force) {
  chrome.storage.local.get(["lastFullRoundAt"], function (res) {
    var last = res.lastFullRoundAt || 0;
    var elapsedMin = Math.round((Date.now() - last) / 60000);
    if (!force && Date.now() - last < ROUND_COOLDOWN_MS) {
      console.log("[SNS 인사이트] 쿨다운 중이라 건너뜀 (마지막 라운드 " + elapsedMin + "분 전)");
      return;
    }
    chrome.storage.local.set({ lastFullRoundAt: Date.now() });
    console.log("[SNS 인사이트] 전체 수집 라운드 시작 -- 8개 탭을 백그라운드로 엽니다");

    DASHBOARD_PLATFORMS.forEach(function (url) {
      chrome.tabs.create({ url: url, active: false }, function (tab) {
        if (chrome.runtime.lastError || !tab) {
          console.log("[SNS 인사이트] 탭 생성 실패:", url, chrome.runtime.lastError && chrome.runtime.lastError.message);
          return;
        }
        console.log("[SNS 인사이트] 탭 열림:", url, "(tabId " + tab.id + ")");
        setTimeout(function () {
          chrome.tabs.remove(tab.id, function () { void chrome.runtime.lastError; });
        }, TAB_CLOSE_DELAY_MS);
      });
    });
  });
}

function todayStr() {
  var d = new Date();
  var pad = function (n) { return String(n).padStart(2, "0"); };
  return d.getFullYear() + "-" + pad(d.getMonth() + 1) + "-" + pad(d.getDate());
}

// 8개 SNS가 거의 동시에 캡처되면(전체 수집 라운드 등) 다들 같은 파일
// (sns-insight.json)에 동시에 쓰려고 해서 GitHub이 sha 충돌(409)로
// 거절하는 경우가 잦았다. 재시도만으로는 8개가 한꺼번에 몰릴 때 부족해서,
// 애초에 동시에 안 쓰도록 커밋을 이 큐에 넣어 하나 끝나야 다음이
// 시작되게 직렬화한다.
var commitQueue = Promise.resolve();
function enqueueCommit(token, capture) {
  commitQueue = commitQueue.then(function () {
    return commitCapture(token, capture, 0);
  });
  return commitQueue;
}

function handleCapture(capture) {
  console.log("[SNS 인사이트] 캡처 수신:", capture.platform, capture.count);
  chrome.storage.local.get(["githubToken"], function (res) {
    if (!res.githubToken) {
      queuePending(capture);
      pushLog({ platform: capture.platform, count: capture.count, capturedAt: capture.capturedAt, status: "pending" });
      return;
    }
    enqueueCommit(res.githubToken, capture);
  });
}

function queuePending(capture) {
  chrome.storage.local.get(["pendingCaptures"], function (res) {
    var pending = res.pendingCaptures || [];
    pending.push(capture);
    chrome.storage.local.set({ pendingCaptures: pending });
  });
}

// popup에서 로그인 성공 직후 호출 -- 쌓여있던 캡처를 한꺼번에 반영.
function flushPending() {
  chrome.storage.local.get(["githubToken", "pendingCaptures"], function (res) {
    if (!res.githubToken || !res.pendingCaptures || !res.pendingCaptures.length) return;
    var pending = res.pendingCaptures;
    chrome.storage.local.set({ pendingCaptures: [] });
    pending.forEach(function (capture) {
      enqueueCommit(res.githubToken, capture);
    });
  });
}
chrome.runtime.onMessage.addListener(function (msg) {
  if (msg && msg.type === "FLUSH_PENDING") flushPending();
});

function ghHeaders(token) {
  return {
    Authorization: "token " + token,
    Accept: "application/vnd.github+json",
  };
}

function commitCapture(token, capture, retryCount) {
  var url = "https://api.github.com/repos/" + REPO + "/contents/" + DATA_PATH;

  return fetch(url, { headers: ghHeaders(token) })
    .then(function (r) {
      if (r.status === 404) return { notFound: true };
      if (!r.ok) {
        // 상태 코드만으로는 왜 거부됐는지(토큰 자체가 무효인지, 스코프
        // 부족인지 등) 알 수 없어서, GitHub이 응답 본문에 같이 주는
        // "message" 필드까지 읽어서 로그에 남긴다.
        return r.json().catch(function () { return {}; }).then(function (body) {
          throw new Error("GET 실패: " + r.status + (body && body.message ? " - " + body.message : ""));
        });
      }
      return r.json();
    })
    .then(function (fileRes) {
      var data = {};
      var sha = null;
      if (!fileRes.notFound) {
        sha = fileRes.sha;
        try {
          data = JSON.parse(decodeURIComponent(escape(atob(fileRes.content.replace(/\n/g, "")))));
        } catch (e) {
          data = {};
        }
      }

      if (!data[capture.platform]) data[capture.platform] = [];
      var day = todayStr();
      var series = data[capture.platform];
      var todayEntry = series.filter(function (e) { return e.date === day; })[0];
      if (todayEntry) {
        todayEntry.count = capture.count;
        todayEntry.capturedAt = capture.capturedAt;
      } else {
        series.push({ date: day, count: capture.count, capturedAt: capture.capturedAt });
      }
      series.sort(function (a, b) { return a.date < b.date ? -1 : 1; });

      var newContentStr = JSON.stringify(data, null, 2);
      var b64 = btoa(unescape(encodeURIComponent(newContentStr)));

      var body = {
        message: "chore: SNS 인사이트 자동 기록 (" + capture.platform + " " + day + ") [skip ci]",
        content: b64,
      };
      if (sha) body.sha = sha;

      return fetch(url, {
        method: "PUT",
        headers: Object.assign({ "Content-Type": "application/json" }, ghHeaders(token)),
        body: JSON.stringify(body),
      });
    })
    .then(function (putRes) {
      if (putRes.status === 409) {
        if (retryCount < 3) {
          // 그 사이 다른 커밋이 먼저 들어간 경우 -- sha를 다시 받아서 재시도.
          // 큐(enqueueCommit)가 우리 자신의 8개끼리는 이미 순서를 보장해주므로,
          // 이 경로는 외부 요인(예: 그 사이 GitHub Actions가 같은 파일에 커밋)으로
          // 인한 드문 충돌을 위한 안전망이다. Promise를 반환해야 큐가 재시도
          // 완료까지 기다리고 다음 커밋을 시작한다.
          return new Promise(function (resolve) {
            setTimeout(resolve, 800 + Math.random() * 800);
          }).then(function () {
            return commitCapture(token, capture, retryCount + 1);
          });
        }
        pushLog({ platform: capture.platform, count: capture.count, capturedAt: capture.capturedAt, status: "error", note: "충돌 재시도 초과" });
        return;
      }
      if (putRes.ok) {
        pushLog({ platform: capture.platform, count: capture.count, capturedAt: capture.capturedAt, status: "success" });
        return;
      }
      return putRes.json().catch(function () { return {}; }).then(function (body) {
        var note = "HTTP " + putRes.status + (body && body.message ? " - " + body.message : "");
        pushLog({ platform: capture.platform, count: capture.count, capturedAt: capture.capturedAt, status: "error", note: note });
      });
    })
    .catch(function (e) {
      // 실패해도 다음 방문 때 자연히 재시도되니 알림은 안 띄우지만,
      // 팝업의 "최근 기록"에는 남겨서 나중에 확인할 수 있게 한다.
      pushLog({ platform: capture.platform, count: capture.count, capturedAt: capture.capturedAt, status: "error", note: String((e && e.message) || e) });
    });
}
