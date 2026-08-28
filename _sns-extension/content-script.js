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
    { test: /rememberapp\.co\.kr/, key: "remember", keywords: ["팔로워"] },
    { test: /rocketpunch\.com/, key: "rocketpunch", keywords: ["팔로워"] },
    { test: /brunch\.co\.kr/, key: "brunch", keywords: ["팔로워"] },
  ];

  var rule = PLATFORM_RULES.filter(function (r) {
    return r.test.test(location.hostname) && (!r.hrefContains || location.href.indexOf(r.hrefContains) !== -1);
  })[0];
  if (!rule) return;

  // 8곳 중 아무 한 곳이라도 들어오면, 이 페이지만 잡고 끝내지 않고
  // 나머지 7곳도 백그라운드로 같이 돈다(20분 쿨다운은 background가 관리) --
  // 굳이 SNS 인사이트 대시보드까지 들어가지 않아도 평소 SNS 쓰는 것만으로
  // 전체 데이터가 자연스럽게 쌓이게 하기 위함.
  chrome.runtime.sendMessage({ type: "SNS_COLLECT_REQUEST" });

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
    }
  }, 1000);
})();
