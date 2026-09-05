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

// 선택자가 깨져도 지금까지는 콘솔 로그만 남고 아무도 모르는 채로
// 지나갔다(조용한 실패). 같은 플랫폼이 MISS_WARN_THRESHOLD번 연속으로
// 실패하면(우연한 1회 로딩 지연과 구분하기 위해 1회가 아니라 연속 실패로
// 판단) 팝업에 경고를 띄우고 알림을 보낸다. 성공하면 그 플랫폼의 연속
// 실패 카운트는 바로 0으로 되돌린다.
var MISS_WARN_THRESHOLD = 2;

function notify(title, message) {
  chrome.notifications.create({
    type: "basic",
    iconUrl: "icons/icon128.png",
    title: title,
    message: message,
  });
}

function updateMissStreak(platform, missed) {
  chrome.storage.local.get(["selectorMissStreak", "selectorWarning"], function (res) {
    var streak = res.selectorMissStreak || {};
    streak[platform] = missed ? (streak[platform] || 0) + 1 : 0;
    chrome.storage.local.set({ selectorMissStreak: streak });

    if (missed && streak[platform] === MISS_WARN_THRESHOLD) {
      var warning = { platform: platform, streak: streak[platform], since: Date.now() };
      chrome.storage.local.set({ selectorWarning: warning });
      notify(
        "SNS 인사이트 — 선택자 확인 필요",
        (PLATFORM_LABELS[platform] || platform) + " 팔로워 수를 " + streak[platform] + "번 연속 못 찾았습니다. 페이지 구조가 바뀌었을 수 있어요."
      );
    } else if (!missed && res.selectorWarning && res.selectorWarning.platform === platform) {
      // 실패했던 플랫폼이 다시 성공하면 별도 확인 없이도 경고를 스스로 내린다.
      chrome.storage.local.remove("selectorWarning");
    }
  });
}

var PLATFORM_LABELS = {
  linkedin: "LinkedIn",
  facebook: "Facebook",
  instagram: "Instagram",
  threads: "Threads",
  naver_blog: "네이버블로그",
  brunch: "브런치",
  remember: "리멤버 커넥트",
  rocketpunch: "로켓펀치",
  naver_clip: "네이버클립(신기한 아파트사전)",
  content_instagram: "인스타그램(신기한 아파트사전)",
  content_threads: "스레드(신기한 아파트사전)",
  content_facebook: "페이스북(신기한 아파트사전)",
  content_tiktok: "틱톡(신기한 아파트사전)",
  content_x: "X(신기한 아파트사전)",
  claude_usage: "클로드 사용량",
};

chrome.runtime.onMessage.addListener(function (msg) {
  if (msg && msg.type === "SNS_CAPTURE") {
    handleCapture(msg);
    updateMissStreak(msg.platform, false);
  }

  if (msg && msg.type === "SNS_COLLECT_FAILED") {
    pushLog({ platform: msg.platform, count: null, capturedAt: new Date().toISOString(), status: "miss" });
    updateMissStreak(msg.platform, true);
  }

  if (msg && msg.type === "CHANNEL_SUMMARY_CAPTURE") {
    handleChannelSummaryCapture(msg);
    updateMissStreak(msg.platform, false);
  }

  if (msg && msg.type === "CLAUDE_USAGE_CAPTURE") {
    handleClaudeUsageCapture(msg);
    updateMissStreak(msg.platform, false);
  }

  if (msg && msg.type === "CONTENT_LIST_CAPTURE") {
    handleContentListCapture(msg);
    updateMissStreak(msg.platform, false);
  }

  if (msg && msg.type === "DISMISS_SELECTOR_WARNING") {
    chrome.storage.local.get(["selectorMissStreak", "selectorWarning"], function (res) {
      var streak = res.selectorMissStreak || {};
      if (res.selectorWarning) streak[res.selectorWarning.platform] = 0;
      chrome.storage.local.set({ selectorMissStreak: streak });
      chrome.storage.local.remove("selectorWarning");
    });
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
  // 2026-09-05: 클로드 사용량(5시간·주간 한도 %)도 같은 "최소화된 창에서
  // 조용히 열고 닫기" 인프라를 그대로 재사용한다 -- SNS와 무관한 데이터지만
  // 별도 라운드를 새로 만드는 것보다 이미 있는 걸 쓰는 게 더 싸다. 기록은
  // assets/data/claude-usage.json으로 따로 쓴다(sns-insight.json과 안 섞임).
  // 이 URL로 바로 이동하면 사용량 설정 모달이 자동으로 열린다(사장님 확인).
  "https://claude.ai/code#settings/usage",
];

// "신기한 아파트사전" 콘텐츠 채널 라운드 -- content-insight.html의
// 새로고침 버튼이 "실시간처럼" 동작하길 바란다는 요청(2026-09-01)으로,
// SNS 인사이트의 강제 새로고침과 같은 방식을 여기도 만든다. 유튜브·
// 네이버 블로그는 GitHub Actions 크론이 담당해서(공개 페이지라 서버가
// 읽을 수 있음) 여기 안 넣는다 -- 그 둘을 지금 당장 갱신하려면 공개
// 페이지에 GitHub 토큰을 심어야 해서(위험) 여전히 크론 주기(하루 2번)를
// 따른다.
var CONTENT_ROUND_PLATFORMS = [
  "https://clip.naver.com/@simkihanapt",
  "https://www.instagram.com/sinkihanapt/reels/",
  "https://threads.com/@sinkihanapt",
  "https://www.facebook.com/profile.php?id=61593748241305",
  "https://www.tiktok.com/@sinkihanapt",
  "https://x.com/sinkihanapt",
];

var TAB_CLOSE_DELAY_MS = 22000; // content-script가 최대 20초까지 찾으니 여유 두고 닫음

// 한 라운드가 도는 동안 들어오는 추가 요청을 무시하는 창. 라운드가 연
// 탭들도 각각 content-script를 실행해 *_COLLECT_REQUEST를 다시 보내고,
// 새로고침 버튼(force)은 하루 제한을 건너뛰기 때문에, 이 가드가 없으면
// 라운드가 겹쳐 탭이 두 배로 열린다(2026-08-30 실제 발생 -- 자연 방문으로
// 한 바퀴 돈 뒤 새로고침을 눌러 16개가 열림). 회사 SNS 라운드와 콘텐츠
// 채널 라운드는 서로 다른 저장소 키를 써서 독립적으로 잠긴다.
var ROUND_LOCK_MS = 90000;

function kstDateStr() {
  return new Intl.DateTimeFormat("en-CA", { timeZone: "Asia/Seoul" }).format(new Date());
}

chrome.runtime.onMessage.addListener(function (msg) {
  if (msg && msg.type === "SNS_COLLECT_REQUEST") {
    console.log("[SNS 인사이트] SNS_COLLECT_REQUEST 수신 (force=" + !!msg.force + ")");
    maybeRunRound(DASHBOARD_PLATFORMS, "lastFullRoundDate", "roundStartedAt", !!msg.force, "전체 수집");
  }
  if (msg && msg.type === "CONTENT_COLLECT_REQUEST") {
    console.log("[SNS 인사이트] CONTENT_COLLECT_REQUEST 수신 (force=" + !!msg.force + ")");
    maybeRunRound(CONTENT_ROUND_PLATFORMS, "lastContentRoundDate", "contentRoundStartedAt", !!msg.force, "콘텐츠 채널");
  }
});

// 회사 SNS 라운드·콘텐츠 채널 라운드가 여는 URL 목록만 다르고 나머지
// 로직(하루 한 번 제한, 중복 실행 방지, 최소화 창으로 조용히 열기)은
// 완전히 같아서 하나로 합쳤다(2026-09-01, 콘텐츠 채널 라운드를 추가하며
// 일반화).
// chrome.storage.local.get으로 "이미 도는 중인지" 확인하고 나서야
// chrome.storage.local.set으로 잠그기 때문에(둘 다 비동기), 그 짧은
// 틈에 두 번째 요청이 끼어들면 둘 다 "안 도는 중"으로 읽어 라운드가
// 겹쳐 도는 문제가 있었다(2026-09-02, 콘텐츠 채널 라운드에서 같은
// 플랫폼이 다른 값으로 짧은 간격을 두고 두 번 기록되며 GitHub 커밋이
// 충돌하는 걸로 발견). 스토리지 왕복 전에 메모리 플래그로 동기적으로
// 먼저 잠가 그 틈을 없앤다 -- 서비스워커가 재시작돼 이 메모리가
// 사라지는 드문 경우엔 아래 스토리지 기반 체크가 그대로 잡아준다.
var roundLockMemory = {};

function maybeRunRound(platforms, dateKey, startedAtKey, force, label) {
  var nowSync = Date.now();
  if (roundLockMemory[startedAtKey] && nowSync - roundLockMemory[startedAtKey] < ROUND_LOCK_MS) {
    console.log("[SNS 인사이트] " + label + " -- 방금 시작한 라운드가 아직 도는 중이라 건너뜀(메모리 잠금)");
    return;
  }
  roundLockMemory[startedAtKey] = nowSync;

  var storageKeys = [dateKey, startedAtKey];
  chrome.storage.local.get(storageKeys, function (res) {
    var today = kstDateStr();
    var now = Date.now();

    // 라운드 중복 방지 -- force든 아니든 무조건 먼저 본다. 새로고침 버튼은
    // "하루 한 번" 제한만 건너뛰는 것이지, 이미 도는 중인 라운드를 하나 더
    // 겹쳐 돌라는 뜻이 아니다.
    if (res[startedAtKey] && now - res[startedAtKey] < ROUND_LOCK_MS) {
      console.log("[SNS 인사이트] " + label + " -- 방금 시작한 라운드가 아직 도는 중이라 건너뜀");
      return;
    }
    if (!force && res[dateKey] === today) {
      console.log("[SNS 인사이트] " + label + " -- 오늘(" + today + ") 이미 한 바퀴 돌아서 건너뜀");
      return;
    }

    var toSet = {};
    toSet[dateKey] = today;
    toSet[startedAtKey] = now;
    chrome.storage.local.set(toSet);
    console.log("[SNS 인사이트] " + label + " 라운드 시작 -- " + platforms.length + "개를 최소화된 별도 창에서 조용히 엽니다");

    // 사용자가 쓰던 창에 탭이 우수수 끼어드는 게 방해된다는 피드백(2026-08-30)으로,
    // 포커스 없는 최소화 창을 따로 만들어 거기서 열고 통째로 닫는다.
    // 작업 표시줄에 창 하나가 잠깐 생겼다 사라지는 정도로 존재감이 줄어든다.
    chrome.windows.create(
      { url: platforms, focused: false, state: "minimized", width: 1440, height: 960 },
      function (win) {
        if (chrome.runtime.lastError || !win) {
          console.log(
            "[SNS 인사이트] " + label + " -- 수집 창 생성 실패, 개별 백그라운드 탭으로 대체:",
            chrome.runtime.lastError && chrome.runtime.lastError.message
          );
          openAsBackgroundTabs(platforms);
          return;
        }
        console.log("[SNS 인사이트] " + label + " -- 수집 창 열림 (windowId " + win.id + ")");
        setTimeout(function () {
          chrome.windows.remove(win.id, function () { void chrome.runtime.lastError; });
        }, TAB_CLOSE_DELAY_MS);
      }
    );
  });
}

// 최소화 창을 못 만드는 환경(예: 창 상태 제한)을 위한 대비책 -- 예전처럼
// 현재 창에 비활성 탭으로 열고 각각 닫는다.
function openAsBackgroundTabs(platforms) {
  platforms.forEach(function (url) {
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

// ── "신기한 아파트사전" 콘텐츠 파일(assets/data/naver-content.json)
// 쓰기 ────────────────────────────────────────────────────────
// sns-insight.json(팔로워 수 시계열, "심플리파이어" 회사 계정용)과는
// 다른 파일에 쓰므로 commitQueue/pendingCaptures와 완전히 분리된
// 큐·저장소 키를 쓴다. 여기에 두 종류의 캡처가 들어온다:
//   1) 채널 요약(팔로워 등 값 몇 개) -- CHANNEL_SUMMARY_CAPTURE
//   2) 콘텐츠 리스트(릴스·영상별 조회수 여러 개) -- CONTENT_LIST_CAPTURE
// 둘 다 "파일을 GET → 수정 → PUT"이라는 같은 뼈대를 쓰므로
// commitToContentFile 하나로 공통 처리하고, 실제로 data를 어떻게
// 바꾸는지만 각자(applyFn)로 넘긴다 -- 2026-09-01, 콘텐츠 리스트 캡처를
// 추가하면서 채널 요약 커밋 함수와 중복되지 않게 일반화했다.
var CONTENT_DATA_PATH = "assets/data/naver-content.json";
var CLAUDE_USAGE_DATA_PATH = "assets/data/claude-usage.json";
var contentCommitQueue = Promise.resolve();

function enqueueContentCommit(token, commitFn, capture) {
  contentCommitQueue = contentCommitQueue.then(function () {
    return commitFn(token, capture, 0);
  });
  return contentCommitQueue;
}

function primaryCount(capture) {
  return capture.fields && capture.fields.followers != null ? capture.fields.followers : null;
}

function handleChannelSummaryCapture(capture) {
  console.log("[SNS 인사이트] 채널 요약 캡처 수신:", capture.platform, capture.fields);
  chrome.storage.local.get(["githubToken"], function (res) {
    if (!res.githubToken) {
      queuePendingContent("channel_summary", capture);
      pushLog({ platform: capture.platform, count: primaryCount(capture), capturedAt: capture.capturedAt, status: "pending" });
      return;
    }
    enqueueContentCommit(res.githubToken, commitChannelSummaryCapture, capture);
  });
}

// 클로드 사용량 -- SNS 데이터와 무관해 별도 파일(claude-usage.json)에
// 쓰지만, 커밋 큐(enqueueContentCommit)는 commitFn을 인자로 받는 범용
// 함수라 그대로 재사용한다(새 큐 변수를 안 만들어도 됨).
function handleClaudeUsageCapture(capture) {
  console.log("[SNS 인사이트] 클로드 사용량 캡처 수신:", capture.fields);
  chrome.storage.local.get(["githubToken"], function (res) {
    if (!res.githubToken) {
      queuePendingContent("claude_usage", capture);
      pushLog({ platform: "claude_usage", capturedAt: capture.capturedAt, status: "pending" });
      return;
    }
    enqueueContentCommit(res.githubToken, commitClaudeUsageCapture, capture);
  });
}

// 필터로 걸러진 개수가 있으면 팝업 로그에 그대로 문구로 남긴다(2026-09-03)
// -- 전에는 이걸 몰라서 "왜 개수가 이상하지"를 매번 개발자도구로 확인해야
// 했다. 0이면 안 붙여서(대부분의 경우) 로그를 안 어지럽힌다.
function filteredNote(capture) {
  return capture.filteredCount ? capture.filteredCount + "개 비공개 제외" : null;
}

function handleContentListCapture(capture) {
  console.log("[SNS 인사이트] 콘텐츠 리스트 캡처 수신:", capture.platform, capture.items.length + "개");
  chrome.storage.local.get(["githubToken"], function (res) {
    if (!res.githubToken) {
      queuePendingContent("content_list", capture);
      pushLog({ platform: capture.platform, count: capture.items.length, capturedAt: capture.capturedAt, status: "pending", note: filteredNote(capture), unit: "건" });
      return;
    }
    enqueueContentCommit(res.githubToken, commitContentListCapture, capture);
  });
}

function queuePendingContent(kind, capture) {
  chrome.storage.local.get(["pendingContentCaptures"], function (res) {
    var pending = res.pendingContentCaptures || [];
    pending.push({ kind: kind, capture: capture });
    chrome.storage.local.set({ pendingContentCaptures: pending });
  });
}

// GET → applyFn(data)로 수정 → PUT의 공통 뼈대. applyFn은 data를 직접
// 바꾸고(posts/clips/channels는 이미 채워져 있음이 보장됨), logMeta는
// 커밋 메시지와 pushLog에 남길 로그 항목을 준다.
//
// 큐(enqueueContentCommit)로 우리 자신의 8개끼리 순서는 보장했는데도,
// 콘텐츠 채널 라운드(플랫폼 6개, 캡처 8개)에서 첫 번째(naver_clip)만
// 성공하고 나머지 7개가 전부 "충돌 재시도 초과"로 실패하는 게 실제로
// 재현됐다(2026-09-02). 원인은 GitHub Contents API의 읽기 지연 --
// 직전 PUT이 성공한 직후에 곧바로 GET을 하면, 그 GET이 아직 그 PUT을
// 반영 못 한 오래된 sha를 돌려줄 때가 있다. 그러면 다음 PUT은 그 오래된
// sha로 시도하게 돼 매번 409가 난다(재시도도 다시 GET하니 똑같이 걸림).
// 매번 새로 GET하는 대신, 방금 우리가 쓴 sha·내용을 메모리에 기억해뒀다가
// 다음 커밋은 GET 없이 그걸 그대로 이어 쓴다. 실제로 외부에서(예: GitHub
// Actions 새벽 수집) 파일이 바뀌어 캐시가 틀렸을 때만(PUT이 409) 캐시를
// 버리고 새로 GET해서 재시도한다.
var contentFileCache = null; // { sha, data }
var claudeUsageFileCache = null; // { sha, data } -- claude-usage.json 전용, 위 캐시와 별개 파일

function commitToContentFile(token, applyFn, logMeta, retryCount, forceRefetch) {
  var url = "https://api.github.com/repos/" + REPO + "/contents/" + CONTENT_DATA_PATH;

  var readPromise = contentFileCache && !forceRefetch
    ? Promise.resolve({ sha: contentFileCache.sha, data: JSON.parse(JSON.stringify(contentFileCache.data)) })
    : fetch(url, { headers: ghHeaders(token) })
        .then(function (r) {
          if (r.status === 404) return { notFound: true };
          if (!r.ok) {
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
          return { sha: sha, data: data };
        });

  return readPromise
    .then(function (state) {
      var data = state.data;
      data.posts = data.posts || {};
      data.clips = data.clips || {};
      data.channels = data.channels || {};

      applyFn(data);
      data.updated_at = new Date().toISOString();

      var newContentStr = JSON.stringify(data, null, 2);
      var b64 = btoa(unescape(encodeURIComponent(newContentStr)));

      var body = { message: logMeta.commitMessage, content: b64 };
      if (state.sha) body.sha = state.sha;

      return fetch(url, {
        method: "PUT",
        headers: Object.assign({ "Content-Type": "application/json" }, ghHeaders(token)),
        body: JSON.stringify(body),
      }).then(function (putRes) { return { putRes: putRes, data: data }; });
    })
    .then(function (result) {
      var putRes = result.putRes;
      if (putRes.status === 409) {
        contentFileCache = null;
        if (retryCount < 3) {
          return new Promise(function (resolve) {
            setTimeout(resolve, 800 + Math.random() * 800);
          }).then(function () {
            return commitToContentFile(token, applyFn, logMeta, retryCount + 1, true);
          });
        }
        pushLog(Object.assign({}, logMeta.logEntry, { status: "error", note: "충돌 재시도 초과" }));
        return;
      }
      if (putRes.ok) {
        return putRes.json().then(function (putBody) {
          contentFileCache = { sha: putBody && putBody.content && putBody.content.sha, data: result.data };
          pushLog(Object.assign({}, logMeta.logEntry, { status: "success" }));
        });
      }
      return putRes.json().catch(function () { return {}; }).then(function (body) {
        var note = "HTTP " + putRes.status + (body && body.message ? " - " + body.message : "");
        pushLog(Object.assign({}, logMeta.logEntry, { status: "error", note: note }));
      });
    })
    .catch(function (e) {
      pushLog(Object.assign({}, logMeta.logEntry, { status: "error", note: String((e && e.message) || e) }));
    });
}

// 클로드 사용량 -- sns-insight.json과 같은 모양(플랫폼별 날짜 시계열)이라
// 그 파일의 commitCapture를 흉내내지만, 대상 파일이 다르고 한 번에 값
// 3개(session_5h/weekly_all/weekly_fable)를 같이 쓴다는 점이 달라 별도
// 함수로 뒀다. commitToContentFile(naver-content.json 전용)과도 파일이
// 달라 독립적인 GET/PUT·캐시(claudeUsageFileCache)를 쓴다.
function commitClaudeUsageCapture(token, capture, retryCount, forceRefetch) {
  var url = "https://api.github.com/repos/" + REPO + "/contents/" + CLAUDE_USAGE_DATA_PATH;

  var readPromise = claudeUsageFileCache && !forceRefetch
    ? Promise.resolve({ sha: claudeUsageFileCache.sha, data: JSON.parse(JSON.stringify(claudeUsageFileCache.data)) })
    : fetch(url, { headers: ghHeaders(token) })
        .then(function (r) {
          if (r.status === 404) return { notFound: true };
          if (!r.ok) {
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
          return { sha: sha, data: data };
        });

  return readPromise
    .then(function (state) {
      var data = state.data;
      var day = todayStr();

      ["session_5h", "weekly_all", "weekly_fable"].forEach(function (key) {
        if (capture.fields[key] == null) return;
        if (!data[key]) data[key] = [];
        var series = data[key];
        var todayEntry = series.filter(function (e) { return e.date === day; })[0];
        if (todayEntry) {
          todayEntry.pct = capture.fields[key];
          todayEntry.capturedAt = capture.capturedAt;
        } else {
          series.push({ date: day, pct: capture.fields[key], capturedAt: capture.capturedAt });
        }
        series.sort(function (a, b) { return a.date < b.date ? -1 : 1; });
      });

      var newContentStr = JSON.stringify(data, null, 2);
      var b64 = btoa(unescape(encodeURIComponent(newContentStr)));

      var body = {
        message: "chore: 클로드 사용량 자동 기록 (" + day + ") [skip ci]",
        content: b64,
      };
      if (state.sha) body.sha = state.sha;

      return fetch(url, {
        method: "PUT",
        headers: Object.assign({ "Content-Type": "application/json" }, ghHeaders(token)),
        body: JSON.stringify(body),
      }).then(function (putRes) { return { putRes: putRes, data: data }; });
    })
    .then(function (result) {
      var putRes = result.putRes;
      if (putRes.status === 409) {
        claudeUsageFileCache = null;
        if (retryCount < 3) {
          return new Promise(function (resolve) {
            setTimeout(resolve, 800 + Math.random() * 800);
          }).then(function () {
            return commitClaudeUsageCapture(token, capture, retryCount + 1, true);
          });
        }
        pushLog({ platform: "claude_usage", capturedAt: capture.capturedAt, status: "error", note: "충돌 재시도 초과" });
        return;
      }
      if (putRes.ok) {
        return putRes.json().then(function (putBody) {
          claudeUsageFileCache = { sha: putBody && putBody.content && putBody.content.sha, data: result.data };
          pushLog({ platform: "claude_usage", count: capture.fields.session_5h, capturedAt: capture.capturedAt, status: "success" });
        });
      }
      return putRes.json().catch(function () { return {}; }).then(function (body) {
        var note = "HTTP " + putRes.status + (body && body.message ? " - " + body.message : "");
        pushLog({ platform: "claude_usage", capturedAt: capture.capturedAt, status: "error", note: note });
      });
    })
    .catch(function (e) {
      pushLog({ platform: "claude_usage", capturedAt: capture.capturedAt, status: "error", note: String((e && e.message) || e) });
    });
}

function commitChannelSummaryCapture(token, capture, retryCount) {
  var day = todayStr();
  return commitToContentFile(token, function (data) {
    var channel = data.channels[capture.platform] = data.channels[capture.platform] || { history: [] };
    channel.url = capture.url;

    var entry = Object.assign({ date: day }, capture.fields);
    var history = channel.history;
    var todayEntry = history.filter(function (e) { return e.date === day; })[0];
    if (todayEntry) {
      Object.assign(todayEntry, entry);
    } else {
      history.push(entry);
    }
    history.sort(function (a, b) { return a.date < b.date ? -1 : 1; });
  }, {
    commitMessage: "chore: " + capture.platform + " 채널 요약 자동 기록 (" + day + ") [skip ci]",
    logEntry: { platform: capture.platform, count: primaryCount(capture), capturedAt: capture.capturedAt },
  }, retryCount);
}

// 릴스·영상 등 콘텐츠 리스트(id·조회수·URL 여러 개)를 data.clips에
// 기록한다. 플랫폼이 섞여도 id가 겹치지 않도록 "platform_id" 형태로
// 키를 만든다. content-insight.html의 기존 videoCardHtml/renderClips가
// 이 모양(history/url/views)을 이미 그대로 그릴 수 있어 페이지 쪽은
// 안 고쳐도 된다.
function commitContentListCapture(token, capture, retryCount) {
  var day = todayStr();
  return commitToContentFile(token, function (data) {
    capture.items.forEach(function (item) {
      var id = capture.platform + "_" + item.id;
      var entry = data.clips[id] = data.clips[id] || { history: [] };
      entry.url = item.url;
      entry.platform = capture.platform;
      if (item.thumbnail) entry.thumbnail = item.thumbnail;
      if (item.title) entry.title = item.title;

      var dayEntry = { date: day, views: item.views };
      var history = entry.history;
      var todayEntry = history.filter(function (e) { return e.date === day; })[0];
      if (todayEntry) {
        Object.assign(todayEntry, dayEntry);
      } else {
        history.push(dayEntry);
      }
      history.sort(function (a, b) { return a.date < b.date ? -1 : 1; });
    });
  }, {
    commitMessage: "chore: " + capture.platform + " 콘텐츠 " + capture.items.length + "개 자동 기록 (" + day + ") [skip ci]",
    logEntry: { platform: capture.platform, count: capture.items.length, capturedAt: capture.capturedAt, note: filteredNote(capture), unit: "건" },
  }, retryCount);
}

// popup에서 로그인 성공 직후 호출 -- 쌓여있던 캡처를 한꺼번에 반영.
function flushPending() {
  chrome.storage.local.get(["githubToken", "pendingCaptures", "pendingContentCaptures"], function (res) {
    if (!res.githubToken) return;
    if (res.pendingCaptures && res.pendingCaptures.length) {
      var pending = res.pendingCaptures;
      chrome.storage.local.set({ pendingCaptures: [] });
      pending.forEach(function (capture) {
        enqueueCommit(res.githubToken, capture);
      });
    }
    if (res.pendingContentCaptures && res.pendingContentCaptures.length) {
      var pendingContent = res.pendingContentCaptures;
      chrome.storage.local.set({ pendingContentCaptures: [] });
      pendingContent.forEach(function (entry) {
        var commitFn = entry.kind === "content_list" ? commitContentListCapture
          : entry.kind === "claude_usage" ? commitClaudeUsageCapture
          : commitChannelSummaryCapture;
        enqueueContentCommit(res.githubToken, commitFn, entry.capture);
      });
    }
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

// commitToContentFile과 같은 이유(GitHub Contents API의 PUT 직후 GET
// 읽기 지연)로 같은 캐시 방식을 쓴다 -- 자세한 설명은 위 주석 참고.
var snsFileCache = null; // { sha, data }

function commitCapture(token, capture, retryCount, forceRefetch) {
  var url = "https://api.github.com/repos/" + REPO + "/contents/" + DATA_PATH;

  var readPromise = snsFileCache && !forceRefetch
    ? Promise.resolve({ sha: snsFileCache.sha, data: JSON.parse(JSON.stringify(snsFileCache.data)) })
    : fetch(url, { headers: ghHeaders(token) })
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
          return { sha: sha, data: data };
        });

  return readPromise
    .then(function (state) {
      var data = state.data;

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
      if (state.sha) body.sha = state.sha;

      return fetch(url, {
        method: "PUT",
        headers: Object.assign({ "Content-Type": "application/json" }, ghHeaders(token)),
        body: JSON.stringify(body),
      }).then(function (putRes) { return { putRes: putRes, data: data }; });
    })
    .then(function (result) {
      var putRes = result.putRes;
      if (putRes.status === 409) {
        snsFileCache = null;
        if (retryCount < 3) {
          // 캐시가 없어서 새로 GET했는데도 409면(캐시 무효화 직후 재시도),
          // 진짜 외부 요인(예: 그 사이 GitHub Actions가 같은 파일에 커밋)일
          // 가능성이 크다.
          return new Promise(function (resolve) {
            setTimeout(resolve, 800 + Math.random() * 800);
          }).then(function () {
            return commitCapture(token, capture, retryCount + 1, true);
          });
        }
        pushLog({ platform: capture.platform, count: capture.count, capturedAt: capture.capturedAt, status: "error", note: "충돌 재시도 초과" });
        return;
      }
      if (putRes.ok) {
        return putRes.json().then(function (putBody) {
          snsFileCache = { sha: putBody && putBody.content && putBody.content.sha, data: result.data };
          pushLog({ platform: capture.platform, count: capture.count, capturedAt: capture.capturedAt, status: "success" });
        });
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
