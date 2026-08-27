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

// ── 자동 채우기 파일럿 (Threads) ──────────────────────────────
// 멀티 퍼블리싱에서 "확장으로 채우기"를 누르면 이 탭이 URL 해시에
// #sfill=... 을 달고 열린다. 여기서 그 해시를 읽어 입력창에 텍스트를
// 채워주기만 하고, 게시 버튼은 절대 대신 누르지 않는다 -- 이미 검수한
// 글이라도, 마지막 제출은 사람이 직접 확인하고 눌러야 사고가 나도
// 되돌릴 수 있다.
//
// Threads의 실제 새 게시물 작성 화면을 직접 보고 만든 게 아니라 첫
// 시도라, 입력창을 못 찾거나 엉뚱한 곳에 채워지면 알려주면 고칠 수 있다.
(function () {
  var m = location.hash.match(/[#&]sfill=([^&]+)/);
  if (!m) return;
  var text = decodeURIComponent(m[1]);

  var attempts = 0;
  var MAX_ATTEMPTS = 60; // "새 게시물 작성"을 사람이 직접 열 시간까지 감안해 30초까지 기다림

  var timer = setInterval(function () {
    attempts++;
    // 화면에 떠 있는 contenteditable 중 실제로 보이는(화면에 렌더된) 첫
    // 번째를 입력창으로 본다 -- Threads 새 게시물 창은 보통 이 방식이다.
    var box = [].slice.call(document.querySelectorAll('[contenteditable="true"]')).filter(function (el) {
      var rect = el.getBoundingClientRect();
      return rect.width > 0 && rect.height > 0;
    })[0];

    if (box) {
      clearInterval(timer);
      box.focus();
      // execCommand로 넣어야 React 등이 실제 입력으로 인식한다
      // (innerText/textContent 직접 대입은 눈에는 보여도 내부 상태에 반영이 안 될 수 있음).
      document.execCommand("insertText", false, text);
      console.log("[SNS 인사이트] Threads 입력창에 텍스트를 채웠습니다 -- 내용 확인 후 직접 게시해주세요.");
    } else if (attempts >= MAX_ATTEMPTS) {
      clearInterval(timer);
      console.log("[SNS 인사이트] 입력창을 못 찾았습니다. '새 게시물 작성' 화면을 먼저 열어야 할 수 있습니다.");
    }
  }, 500);
})();
