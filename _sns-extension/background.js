// content-script가 잡아낸 팔로워 수를 받아서, GitHub 저장소의
// assets/data/sns-insight.json 파일에 오늘 날짜로 기록합니다.
// 같은 날 같은 플랫폼이 여러 번 잡히면 그날 값을 덮어씁니다(하루 1개).
//
// 로그인(GitHub 토큰) 전에 잡힌 값은 버리지 않고 pendingCaptures에
// 쌓아두었다가, popup에서 로그인하면 그때 한꺼번에 반영합니다.

var REPO = "hansunghee7/hansunghee7.github.io";
var DATA_PATH = "assets/data/sns-insight.json";

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
      if (putRes.status === 409 && retryCount < 3) {
        // 그 사이 다른 커밋이 먼저 들어간 경우 -- sha를 다시 받아서 재시도
        setTimeout(function () { commitCapture(token, capture, retryCount + 1); }, 800 + Math.random() * 800);
      }
    })
    .catch(function () {
      // 네트워크 오류 등은 조용히 무시(다음 방문 때 다시 시도됨). 개인용
      // 도구라 실패를 알림으로 띄우기보다 다음 기회에 자연히 재시도되게 둠.
    });
}
