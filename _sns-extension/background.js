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

// ── 로그인이 필요한 SNS 전체 수집 한 바퀴 ──────────────────────
// 가족 공유 PC라 특정 시각에 PC가 켜져 있다는 보장이 없어서(실제로
// Windows 예약 작업이 한 번도 자동 실행 안 됐던 걸 확인함), 정해진 시각
// 예약 대신 "사용자가 SNS를 신경 쓰는 순간"에 8개 프로필을 백그라운드
// 탭(화면에 안 보이는 새 탭)으로 조용히 열었다가 자동으로 닫으면서
// 갱신한다. 이 신호는 두 군데서 온다:
//   1) SNS 인사이트 페이지에서 새로고침 버튼을 누를 때 -- 사용자가 명시적으로
//      "지금 다시 확인해줘"라고 요청한 것이므로 하루 제한을 건너뛴다(force).
//   2) 8개 플랫폼 중 아무 한 곳이라도 직접 방문할 때 (content-script.js)
//      -- 하나만 봐도 나머지도 같이 도니, 굳이 대시보드까지 안 들어가도
//      자연스러운 SNS 사용만으로 데이터가 쌓인다.
// 매번 들어갈 때마다(하루에도 여러 번) 8개를 전부 다시 도는 게 과하다는
// 피드백으로, 쿨다운(20분)이 아니라 "오늘(KST) 하루 한 번"으로 바꿨다 --
// 오늘 이미 한 번 돌았으면 자연 방문으로는 다시 안 돌고, 새로고침을
// 명시적으로 누르면(force) 그날 몇 번째든 항상 돈다.
//
// 2026-08-30: 브런치·네이버블로그·로켓펀치 3개는 로그인 없이 공개 페이지에서
// 숫자가 보이므로 서버(GitHub Actions + Playwright, scripts/fetch_sns_public.py)가
// 매일 새벽 자동 수집하도록 옮겼다. 그래서 이 목록에서 뺐다 -- 브라우저가
// 여는 탭이 8개에서 5개로 줄고, 그 3개는 PC를 안 켜도 기록이 쌓인다.
// 여기 남은 5개는 전부 로그인해야만 숫자가 보여 서버에서 못 읽는 채널이다.
var DASHBOARD_PLATFORMS = [
  "https://www.linkedin.com/in/simplifier",
  "https://www.facebook.com/simplifier.seoul",
  "https://www.instagram.com/simplifier_seoul/",
  "https://www.threads.com/?hl=ko",
  "https://connect.rememberapp.co.kr/profile/1582110/posts",
];
var TAB_CLOSE_DELAY_MS = 22000; // content-script가 최대 20초까지 찾으니 여유 두고 닫음

// 한 라운드가 도는 동안 들어오는 추가 요청을 무시하는 창. 라운드가 연
// 탭들도 각각 content-script를 실행해 SNS_COLLECT_REQUEST를 다시 보내고,
// 새로고침 버튼(force)은 하루 제한을 건너뛰기 때문에, 이 가드가 없으면
// 라운드가 겹쳐 탭이 두 배로 열린다(2026-08-30 실제 발생 -- 자연 방문으로
// 한 바퀴 돈 뒤 새로고침을 눌러 16개가 열림).
var ROUND_LOCK_MS = 90000;

function kstDateStr() {
  return new Intl.DateTimeFormat("en-CA", { timeZone: "Asia/Seoul" }).format(new Date());
}

chrome.runtime.onMessage.addListener(function (msg) {
  if (msg && msg.type === "SNS_COLLECT_REQUEST") {
    console.log("[SNS 인사이트] SNS_COLLECT_REQUEST 수신 (force=" + !!msg.force + ")");
    maybeRunFullRound(!!msg.force);
  }
});

function maybeRunFullRound(force) {
  chrome.storage.local.get(["lastFullRoundDate", "roundStartedAt"], function (res) {
    var today = kstDateStr();
    var now = Date.now();

    // 라운드 중복 방지 -- force든 아니든 무조건 먼저 본다. 새로고침 버튼은
    // "하루 한 번" 제한만 건너뛰는 것이지, 이미 도는 중인 라운드를 하나 더
    // 겹쳐 돌라는 뜻이 아니다.
    if (res.roundStartedAt && now - res.roundStartedAt < ROUND_LOCK_MS) {
      console.log("[SNS 인사이트] 방금 시작한 라운드가 아직 도는 중이라 건너뜀");
      return;
    }
    if (!force && res.lastFullRoundDate === today) {
      console.log("[SNS 인사이트] 오늘(" + today + ") 이미 한 바퀴 돌아서 건너뜀");
      return;
    }

    chrome.storage.local.set({ lastFullRoundDate: today, roundStartedAt: now });
    console.log(
      "[SNS 인사이트] 전체 수집 라운드 시작 -- " +
        DASHBOARD_PLATFORMS.length +
        "개를 최소화된 별도 창에서 조용히 엽니다"
    );

    // 사용자가 쓰던 창에 탭이 우수수 끼어드는 게 방해된다는 피드백(2026-08-30)으로,
    // 포커스 없는 최소화 창을 따로 만들어 거기서 열고 통째로 닫는다.
    // 작업 표시줄에 창 하나가 잠깐 생겼다 사라지는 정도로 존재감이 줄어든다.
    chrome.windows.create(
      { url: DASHBOARD_PLATFORMS, focused: false, state: "minimized" },
      function (win) {
        if (chrome.runtime.lastError || !win) {
          console.log(
            "[SNS 인사이트] 수집 창 생성 실패, 개별 백그라운드 탭으로 대체:",
            chrome.runtime.lastError && chrome.runtime.lastError.message
          );
          openAsBackgroundTabs();
          return;
        }
        console.log("[SNS 인사이트] 수집 창 열림 (windowId " + win.id + ")");
        setTimeout(function () {
          chrome.windows.remove(win.id, function () { void chrome.runtime.lastError; });
        }, TAB_CLOSE_DELAY_MS);
      }
    );
  });
}

// 최소화 창을 못 만드는 환경(예: 창 상태 제한)을 위한 대비책 -- 예전처럼
// 현재 창에 비활성 탭으로 열고 각각 닫는다.
function openAsBackgroundTabs() {
  DASHBOARD_PLATFORMS.forEach(function (url) {
    chrome.tabs.create({ url: url, active: false }, function (tab) {
      if (chrome.runtime.lastError || !tab) {
        console.log("[SNS 인사이트] 탭 생성 실패:", url, chrome.runtime.lastError && chrome.runtime.lastError.message);
        return;
      }
      setTimeout(function () {
        chrome.tabs.remove(tab.id, function () { void chrome.runtime.lastError; });
      }, TAB_CLOSE_DELAY_MS);
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
