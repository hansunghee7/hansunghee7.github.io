// 각 SNS 프로필 페이지를 열 때, 화면에 보이는 텍스트에서 팔로워 수 등을
// 찾아 background로 보냅니다. class명 같은 화면 구조가 아니라 "팔로워
// 890"처럼 사람이 읽는 글자 패턴으로 찾기 때문에, 사이트가 화면을
// 리뉴얼해도 눈에 숫자가 보이는 한 웬만하면 계속 동작합니다.
//
// 다만 이 방식은 처음 시도라 사이트별로 실제 문구/순서가 제 예상과
// 다를 수 있습니다. 안 잡히는 사이트가 있으면 그 페이지에서 실제로
// 어떻게 쓰여있는지 알려주시면 패턴을 맞춰 고칠 수 있습니다.

(function () {
  var PLATFORM_RULES = [
    // ── "심플리파이어" 회사 계정(값 1개, SNS_CAPTURE) ──────────────
    { test: /linkedin\.com/, key: "linkedin", keywords: ["팔로워", "followers"] },
    { test: /facebook\.com/, key: "facebook", keywords: ["팔로워", "친구", "followers", "friends"], hrefContains: "simplifier.seoul" },
    { test: /instagram\.com/, key: "instagram", keywords: ["followers", "팔로워"], hrefContains: "simplifier_seoul" },
    // 2026-09-01: 이 규칙에 hrefContains가 없어서 "신기한 아파트사전" 스레드를
    // 방문했을 때도 회사 스레드로 잘못 잡혀(팔로워 1로) sns-insight.json에
    // 오염된 값이 들어간 사고가 있었다. manifest 매치 패턴도 같이 좁혔다.
    { test: /threads\.(com|net)/, key: "threads", keywords: ["followers", "팔로워"], hrefContains: "simplifier_seoul" },
    // 네이버 블로그는 manifest의 매치 패턴을 도메인 전체로 넓혀뒀다(구형 블로그가
    // 프레임 안에 실제 화면을 넣는 구조라 all_frames로 안쪽 프레임도 봐야 해서).
    // 그 대신 다른 사람 블로그를 구경할 때 잘못 기록되지 않도록 URL에
    // "simplifiers"가 있을 때만 동작하게 hrefContains로 한 번 더 좁힌다.
    { test: /blog\.naver\.com/, key: "naver_blog", keywords: ["블로그 이웃", "서로이웃", "이웃"], hrefContains: "simplifiers" },
    { test: /rememberapp\.co\.kr/, key: "remember", keywords: ["팔로워"] },
    { test: /rocketpunch\.com/, key: "rocketpunch", keywords: ["팔로워"] },
    { test: /brunch\.co\.kr/, key: "brunch", keywords: ["팔로워"] },

    // ── "신기한 아파트사전" 콘텐츠 채널 요약(값 여러 개, multi,
    // CHANNEL_SUMMARY_CAPTURE) ──────────────────────────────────
    // 회사 계정과 완전히 다른 채널이라 결과를 다른 파일
    // (assets/data/naver-content.json의 channels)에 쓴다. 게시물별
    // 개별 성과(조회수 등)는 플랫폼마다 화면이 다 달라 공수가 커서
    // 보류하고, 지금은 프로필에 보이는 채널 요약 수치만 읽는다
    // (2026-09-01). 클립이 로그인 세션을 요구하는 비공개 API라 서버
    // 자동화로 못 읽는다는 걸 확인한 것과 같은 이유로, 나머지 플랫폼도
    // 전부 "실제 로그인한 브라우저로 화면에 보이는 값 읽기" 방식을 쓴다.
    { test: /clip\.naver\.com/, key: "naver_clip", hrefContains: "simkihanapt", multi: true,
      fields: { followers: ["팔로워"], following: ["팔로잉"], content_count: ["콘텐츠"] } },
    // 인스타 릴스·틱톡은 프로필/그리드 화면에 게시물별 조회수가 진짜
    // 링크(href)와 함께 텍스트로 그대로 보여서(2026-09-01, 사장님이
    // 릴스 화면 캡처로 확인해주심), 클립과 달리 개별 성과도 같이
    // 읽는다(listHrefPattern, CONTENT_LIST_CAPTURE) -- 채널 요약(multi)
    // 캡처와 같은 페이지 방문에서 별도로 함께 돈다.
    { test: /instagram\.com/, key: "content_instagram", hrefContains: "sinkihanapt", multi: true,
      fields: { followers: ["followers", "팔로워"], content_count: ["posts", "게시물"] },
      listHrefPattern: /\/reel\/([^/?#]+)/ },
    { test: /threads\.(com|net)/, key: "content_threads", hrefContains: "sinkihanapt", multi: true,
      fields: { followers: ["followers", "팔로워"] } },
    { test: /facebook\.com/, key: "content_facebook", hrefContains: "61593748241305", multi: true,
      fields: { followers: ["팔로워", "팔로우", "followers"] } },
    { test: /tiktok\.com/, key: "content_tiktok", hrefContains: "sinkihanapt", multi: true,
      fields: { followers: ["Followers", "팔로워"], following: ["Following", "팔로잉"], likes: ["Likes", "좋아요"] },
      listHrefPattern: /\/video\/(\d+)/ },
    // x.com은 도메인이 짧아 unanchored 정규식을 쓰면 다른 도메인의
    // 일부(예: netflix.com)에도 우연히 걸릴 수 있어 앵커를 건다.
    { test: /(^|\.)x\.com$/, key: "content_x", hrefContains: "sinkihanapt", multi: true,
      fields: { followers: ["Followers", "followers"], following: ["Following", "following"] } },
  ];

  var rule = PLATFORM_RULES.filter(function (r) {
    return r.test.test(location.hostname) && (!r.hrefContains || location.href.indexOf(r.hrefContains) !== -1);
  })[0];
  if (!rule) return;

  // 회사 계정 8곳 중 아무 한 곳이라도 들어오면, 이 페이지만 잡고 끝내지
  // 않고 나머지도 백그라운드로 같이 돈다(오늘 이미 돌았으면 background가
  // 건너뜀 -- 하루 한 번이면 충분) -- 굳이 SNS 인사이트 대시보드까지
  // 들어가지 않아도 평소 SNS 쓰는 것만으로 전체 데이터가 자연스럽게
  // 쌓이게 하기 위함. "신기한 아파트사전" 콘텐츠 채널(multi: true인
  // 규칙 전부)은 이 회사 계정 라운드와 무관하므로 건너뛴다.
  if (!rule.multi) {
    chrome.runtime.sendMessage({ type: "SNS_COLLECT_REQUEST" });
  }

  var NUMBER = "([\\d][\\d,\\.]*)\\s*(천|만|K|k|M|m)?";

  function parseAbbrevNumber(numStr, suffix) {
    var n = parseFloat(numStr.replace(/,/g, ""));
    if (isNaN(n)) return null;
    if (suffix === "천") n *= 1000;
    else if (suffix === "만") n *= 10000;
    else if (suffix === "K" || suffix === "k") n *= 1000;
    else if (suffix === "M" || suffix === "m") n *= 1000000;
    return Math.round(n);
  }

  function findCount(text, keyword) {
    // "총 팔로워 890" / "팔로워 1.6천" 처럼 라벨이 먼저 오는 경우
    var labelFirst = new RegExp(keyword + "\\D{0,6}" + NUMBER, "i").exec(text);
    if (labelFirst) return parseAbbrevNumber(labelFirst[1], labelFirst[2]);

    // "890 followers" 처럼 숫자가 먼저 오는 경우
    var numberFirst = new RegExp(NUMBER + "\\s*" + keyword, "i").exec(text);
    if (numberFirst) return parseAbbrevNumber(numberFirst[1], numberFirst[2]);

    return null;
  }

  function tryExtract() {
    var text = document.body ? document.body.innerText : "";
    for (var i = 0; i < rule.keywords.length; i++) {
      var count = findCount(text, rule.keywords[i]);
      if (count !== null && count >= 0) return count;
    }
    return null;
  }

  // 채널 요약(팔로워·팔로잉·콘텐츠 수 등 여러 값)은 값 하나만 찾는
  // tryExtract()로는 안 되어, 필드별로 키워드 후보를 돌며 전부 찾는다.
  function tryExtractMulti(fields) {
    var text = document.body ? document.body.innerText : "";
    var result = {};
    var foundAny = false;
    Object.keys(fields).forEach(function (field) {
      var keywords = fields[field];
      var n = null;
      for (var i = 0; i < keywords.length && n === null; i++) {
        n = findCount(text, keywords[i]);
      }
      result[field] = n;
      if (n !== null) foundAny = true;
    });
    return foundAny ? result : null;
  }

  // 릴스·영상처럼 여러 개가 그리드로 보이는 콘텐츠는 href(진짜 링크)로
  // 항목을 구분하고, 그 링크 안에 같이 보이는 숫자(조회수)를 읽는다.
  // 팔로워처럼 "라벨 + 숫자"가 아니라 숫자 하나만 덩그러니 있는 경우가
  // 많아 키워드 없이 첫 숫자를 그대로 쓴다.
  function collectListItems(hrefPattern) {
    var anchors = Array.prototype.slice.call(document.querySelectorAll("a[href]"));
    var seen = {};
    var items = [];
    anchors.forEach(function (a) {
      var href = a.getAttribute("href") || "";
      var m = hrefPattern.exec(href);
      if (!m) return;
      var id = m[1];
      if (seen[id]) return;
      var text = (a.innerText || "").trim();
      var numMatch = new RegExp(NUMBER).exec(text);
      if (!numMatch) return;
      var views = parseAbbrevNumber(numMatch[1], numMatch[2]);
      if (views == null) return;
      seen[id] = true;
      items.push({
        id: id,
        views: views,
        url: href.indexOf("http") === 0 ? href : location.origin + href,
      });
    });
    return items;
  }

  if (rule.multi) {
    var fieldNames = Object.keys(rule.fields);
    var multiAttempts = 0;
    var MULTI_MAX_ATTEMPTS = 20; // SPA가 데이터를 다 불러올 때까지 최대 20초 기다림

    var multiTimer = setInterval(function () {
      multiAttempts++;
      var result = tryExtractMulti(rule.fields);
      var allFound = result && fieldNames.every(function (f) { return result[f] !== null; });
      if (allFound || (result && multiAttempts >= MULTI_MAX_ATTEMPTS)) {
        clearInterval(multiTimer);
        console.log("[SNS 인사이트]", rule.key, "감지:", result, "-> 기록 전송");
        chrome.runtime.sendMessage({
          type: "CHANNEL_SUMMARY_CAPTURE",
          platform: rule.key,
          fields: result,
          url: location.href,
          capturedAt: new Date().toISOString(),
        });
      } else if (!result && multiAttempts >= MULTI_MAX_ATTEMPTS) {
        clearInterval(multiTimer);
        console.log("[SNS 인사이트]", rule.key, "패턴을 못 찾음 (" + MULTI_MAX_ATTEMPTS + "초 시도)");
        chrome.runtime.sendMessage({ type: "SNS_COLLECT_FAILED", platform: rule.key, url: location.href });
      }
    }, 1000);
  }

  if (rule.listHrefPattern) {
    var listAttempts = 0;
    var LIST_MAX_ATTEMPTS = 15;

    var listTimer = setInterval(function () {
      listAttempts++;
      var items = collectListItems(rule.listHrefPattern);
      if (items.length || listAttempts >= LIST_MAX_ATTEMPTS) {
        clearInterval(listTimer);
        if (items.length) {
          console.log("[SNS 인사이트]", rule.key, "콘텐츠 리스트", items.length, "개 찾음 -> 기록 전송");
          chrome.runtime.sendMessage({
            type: "CONTENT_LIST_CAPTURE",
            platform: rule.key,
            items: items,
            capturedAt: new Date().toISOString(),
          });
        } else {
          console.log("[SNS 인사이트]", rule.key, "콘텐츠 리스트 못 찾음 (" + LIST_MAX_ATTEMPTS + "초 시도)");
        }
      }
    }, 1000);
  }

  if (rule.multi || rule.listHrefPattern) {
    // 둘 다 채널 콘텐츠 전용 흐름이라, 아래 회사 계정용 단일값 추출로는
    // 안 내려간다.
    return;
  }

  var attempts = 0;
  var MAX_ATTEMPTS = 20; // SPA가 데이터를 다 불러올 때까지 최대 20초 기다림

  var timer = setInterval(function () {
    attempts++;
    var count = tryExtract();
    if (count !== null) {
      clearInterval(timer);
      console.log("[SNS 인사이트]", rule.key, "감지:", count, "-> 기록 전송");
      chrome.runtime.sendMessage({
        type: "SNS_CAPTURE",
        platform: rule.key,
        count: count,
        url: location.href,
        capturedAt: new Date().toISOString(),
      });
    } else if (attempts >= MAX_ATTEMPTS) {
      clearInterval(timer);
      console.log("[SNS 인사이트]", rule.key, "패턴을 못 찾음 (" + MAX_ATTEMPTS + "초 시도) -- 팔로워 수 문구가 바뀌었을 수 있음");
      // 이전엔 여기서 콘솔 로그만 남기고 끝났다 -- background/popup은 이
      // 페이지가 실패했는지 전혀 알 방법이 없었다(조용한 실패). 실패도
      // 명시적으로 알려서 연속 실패 시 팝업에서 경고할 수 있게 한다.
      chrome.runtime.sendMessage({ type: "SNS_COLLECT_FAILED", platform: rule.key, url: location.href });
    }
  }, 1000);
})();
