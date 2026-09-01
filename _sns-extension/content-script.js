// 각 SNS 프로필 페이지를 열 때, 화면에 보이는 텍스트에서 팔로워 수를
// 찾아 background로 보냅니다. class명 같은 화면 구조가 아니라 "팔로워
// 890"처럼 사람이 읽는 글자 패턴으로 찾기 때문에, 사이트가 화면을
// 리뉴얼해도 눈에 팔로워 수가 보이는 한 웬만하면 계속 동작합니다.
//
// 다만 이 방식은 처음 시도라 사이트별로 실제 문구/순서가 제 예상과
// 다를 수 있습니다. 안 잡히는 사이트가 있으면 그 페이지에서 실제로
// 어떻게 쓰여있는지 알려주시면 패턴을 맞춰 고칠 수 있습니다.

(function () {
  var PLATFORM_RULES = [
    { test: /linkedin\.com/, key: "linkedin", keywords: ["팔로워", "followers"] },
    { test: /facebook\.com/, key: "facebook", keywords: ["팔로워", "친구", "followers", "friends"] },
    { test: /instagram\.com/, key: "instagram", keywords: ["followers", "팔로워"] },
    { test: /threads\.(com|net)/, key: "threads", keywords: ["followers", "팔로워"] },
    // 네이버 블로그는 manifest의 매치 패턴을 도메인 전체로 넓혀뒀다(구형 블로그가
    // 프레임 안에 실제 화면을 넣는 구조라 all_frames로 안쪽 프레임도 봐야 해서).
    // 그 대신 다른 사람 블로그를 구경할 때 잘못 기록되지 않도록 URL에
    // "simplifiers"가 있을 때만 동작하게 hrefContains로 한 번 더 좁힌다.
    { test: /blog\.naver\.com/, key: "naver_blog", keywords: ["블로그 이웃", "서로이웃", "이웃"], hrefContains: "simplifiers" },
    // 네이버 클립은 "심플리파이어"가 아니라 다른 채널(신기한 아파트사전,
    // content-insight.html)용이라 별도 흐름(NAVER_CLIP_CHANNEL_MULTI)으로
    // 처리한다 -- 팔로워 하나가 아니라 팔로워·팔로잉·콘텐츠 수 3개를 같이
    // 읽어야 해서, 아래 tryExtract()가 아니라 별도 함수(tryExtractClipChannel)를
    // 쓴다. 클립별 개별 조회수는 API가 로그인 세션을 요구해 서버 자동화로는
    // 못 읽는다는 걸 확인했고(scripts/fetch_naver_content.py 참고), 실제로
    // 클립이 1개뿐이라 지금은 채널 요약 수치만 읽는다(2026-09-01).
    { test: /clip\.naver\.com/, key: "naver_clip_channel", hrefContains: "simkihanapt", multi: true },
    { test: /rememberapp\.co\.kr/, key: "remember", keywords: ["팔로워"] },
    { test: /rocketpunch\.com/, key: "rocketpunch", keywords: ["팔로워"] },
    { test: /brunch\.co\.kr/, key: "brunch", keywords: ["팔로워"] },
  ];

  var rule = PLATFORM_RULES.filter(function (r) {
    return r.test.test(location.hostname) && (!r.hrefContains || location.href.indexOf(r.hrefContains) !== -1);
  })[0];
  if (!rule) return;

  // 8곳 중 아무 한 곳이라도 들어오면, 이 페이지만 잡고 끝내지 않고
  // 나머지 7곳도 백그라운드로 같이 돈다(오늘 이미 돌았으면 background가
  // 건너뜀 -- 하루 한 번이면 충분) -- 굳이 SNS 인사이트 대시보드까지
  // 들어가지 않아도 평소 SNS 쓰는 것만으로 전체 데이터가 자연스럽게
  // 쌓이게 하기 위함. 네이버 클립(신기한 아파트사전, 다른 채널)은 이
  // "심플리파이어" 회사 계정 라운드와 무관하므로 건너뛴다.
  if (rule.key !== "naver_clip_channel") {
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

  // 네이버 클립 채널 요약(팔로워·팔로잉·콘텐츠 수 3개를 한 번에)은 값
  // 하나만 찾는 tryExtract()로는 안 되어 별도 루프를 돈다.
  if (rule.multi && rule.key === "naver_clip_channel") {
    var CLIP_FIELDS = { followers: "팔로워", following: "팔로잉", contentCount: "콘텐츠" };

    function tryExtractClipChannel() {
      var text = document.body ? document.body.innerText : "";
      var result = {};
      var foundAny = false;
      Object.keys(CLIP_FIELDS).forEach(function (field) {
        var n = findCount(text, CLIP_FIELDS[field]);
        result[field] = n;
        if (n !== null) foundAny = true;
      });
      return foundAny ? result : null;
    }

    var clipAttempts = 0;
    var CLIP_MAX_ATTEMPTS = 20;

    var clipTimer = setInterval(function () {
      clipAttempts++;
      var result = tryExtractClipChannel();
      var allFound = result && result.followers !== null && result.following !== null && result.contentCount !== null;
      if (allFound || (result && clipAttempts >= CLIP_MAX_ATTEMPTS)) {
        clearInterval(clipTimer);
        console.log("[SNS 인사이트] naver_clip_channel 감지:", result, "-> 기록 전송");
        chrome.runtime.sendMessage({
          type: "NAVER_CLIP_CHANNEL_CAPTURE",
          followers: result.followers,
          following: result.following,
          contentCount: result.contentCount,
          url: location.href,
          capturedAt: new Date().toISOString(),
        });
      } else if (!result && clipAttempts >= CLIP_MAX_ATTEMPTS) {
        clearInterval(clipTimer);
        console.log("[SNS 인사이트] naver_clip_channel 패턴을 못 찾음 (" + CLIP_MAX_ATTEMPTS + "초 시도)");
        chrome.runtime.sendMessage({ type: "SNS_COLLECT_FAILED", platform: rule.key, url: location.href });
      }
    }, 1000);
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
