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
    { test: /blog\.naver\.com/, key: "naver_blog", keywords: ["이웃", "서로이웃"] },
    { test: /rememberapp\.co\.kr/, key: "remember", keywords: ["팔로워"] },
    { test: /rocketpunch\.com/, key: "rocketpunch", keywords: ["팔로워"] },
  ];

  var rule = PLATFORM_RULES.filter(function (r) { return r.test.test(location.hostname); })[0];
  if (!rule) return;

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
      chrome.runtime.sendMessage({
        type: "SNS_CAPTURE",
        platform: rule.key,
        count: count,
        url: location.href,
        capturedAt: new Date().toISOString(),
      });
    } else if (attempts >= MAX_ATTEMPTS) {
      clearInterval(timer);
    }
  }, 1000);
})();
