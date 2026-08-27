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

function todayStr() {
  var d = new Date();
  var pad = function (n) { return String(n).padStart(2, "0"); };
  return d.getFullYear() + "-" + pad(d.getMonth() + 1) + "-" + pad(d.getDate());
}

function handleCapture(capture) {
  chrome.storage.local.get(["githubToken"], function (res) {
    if (!res.githubToken) {
      queuePending(capture);
      pushLog({ platform: capture.platform, count: capture.count, capturedAt: capture.capturedAt, status: "pending" });
      return;
    }
    commitCapture(res.githubToken, capture, 0);
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
      commitCapture(res.githubToken, capture, 0);
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

  fetch(url, { headers: ghHeaders(token) })
    .then(function (r) {
      if (r.status === 404) return { notFound: true };
      if (!r.ok) throw new Error("GET 실패: " + r.status);
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
          // 그 사이 다른 커밋이 먼저 들어간 경우 -- sha를 다시 받아서 재시도
          setTimeout(function () { commitCapture(token, capture, retryCount + 1); }, 800 + Math.random() * 800);
        } else {
          pushLog({ platform: capture.platform, count: capture.count, capturedAt: capture.capturedAt, status: "error", note: "충돌 재시도 초과" });
        }
        return;
      }
      if (putRes.ok) {
        pushLog({ platform: capture.platform, count: capture.count, capturedAt: capture.capturedAt, status: "success" });
      } else {
        pushLog({ platform: capture.platform, count: capture.count, capturedAt: capture.capturedAt, status: "error", note: "HTTP " + putRes.status });
      }
    })
    .catch(function (e) {
      // 실패해도 다음 방문 때 자연히 재시도되니 알림은 안 띄우지만,
      // 팝업의 "최근 기록"에는 남겨서 나중에 확인할 수 있게 한다.
      pushLog({ platform: capture.platform, count: capture.count, capturedAt: capture.capturedAt, status: "error", note: String((e && e.message) || e) });
    });
}
