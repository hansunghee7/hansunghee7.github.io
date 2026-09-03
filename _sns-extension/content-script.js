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
    // 2026-09-02~03: 클립이 2개로 늘고 실제 조회수 반응이 보이기 시작해
    // 개별 조회수도 시도했다. 처음엔 인스타/틱톡과 같은 href 기반
    // (listHrefPattern)으로 짰는데 실측(2026-09-03, 사장님이 개발자도구로
    // 카드 하나를 직접 열어 확인)해보니 클립 카드는 `<a href>`가 아니라
    // `<button aria-label="캡션">`이고, href 자체가 없어 0건으로 조용히
    // 실패했다. 대신 카드 안에 조회수가 `<span>조회수</span><span>404</span>`
    // 형태로 라벨+숫자 형제 span으로 정확히 있어서, 그 라벨 텍스트로
    // 찾는 labelCapture 방식으로 바꿨다(collectLabeledCards). 진짜 링크가
    // 없어 완벽한 고유 id가 없으므로 캡션(aria-label) 해시를 id로 쓴다 --
    // 같은 캡션이면 매번 같은 id가 나와 upsert가 정상 동작한다.
    { test: /clip\.naver\.com/, key: "naver_clip", hrefContains: "simkihanapt", multi: true,
      fields: { followers: ["팔로워"], following: ["팔로잉"], content_count: ["콘텐츠"] },
      labelCapture: "조회수" },
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
  // 인스타·틱톡 둘 다 이미지를 지연 로딩(lazy-load)한다 -- <img src>가
  // 처음엔 1x1 투명 gif 같은 자리표시자이고, 진짜 주소는 data-src류
  // 속성이나 srcset에 먼저 들어가 있는 경우가 많다(2026-09-01, 실제
  // 캡처해보니 틱톡은 자리표시자 data: URL이, 인스타는 <img> 자체가 아예
  // 안 잡혀서 빈 값이 저장된 걸 확인). data-src류를 먼저 보고, 그래도
  // 없으면 배경이미지(background-image: url(...))로 그리는 타일도 있어
  // 그것까지 마지막으로 본다.
  function extractImgUrl(container) {
    var img = container.querySelector("img");
    if (img) {
      var attrs = ["data-src", "data-lazy-src", "data-original", "data-srcset", "srcset", "src"];
      for (var i = 0; i < attrs.length; i++) {
        var v = img.getAttribute(attrs[i]);
        if (!v) continue;
        if (attrs[i].indexOf("srcset") !== -1) v = v.split(",")[0].trim().split(/\s+/)[0];
        if (v && v.indexOf("data:image") !== 0) {
          return { url: v, alt: img.alt || null };
        }
      }
    }
    var candidates = Array.prototype.slice.call(container.querySelectorAll("*")).concat(container);
    for (var j = 0; j < candidates.length; j++) {
      var bg = getComputedStyle(candidates[j]).backgroundImage;
      var bgMatch = /url\((['"]?)(.*?)\1\)/.exec(bg || "");
      if (bgMatch && bgMatch[2] && bgMatch[2].indexOf("data:image") !== 0) {
        return { url: bgMatch[2], alt: null };
      }
    }
    return null;
  }

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
      var thumb = extractImgUrl(a);
      // 화면 밖(스크롤 안 된 곳)에 있는 타일은 지연 로딩이 아예 안
      // 트리거돼서 몇 초를 기다려도 썸네일이 안 채워진다(2026-09-01,
      // 실측 -- 그리드 두 번째 항목이 계속 비었음). 이 페이지가 사용자
      // 눈에 안 보이는 상태(백그라운드 라운드로 열렸을 때만 해당,
      // document.hidden)일 때만 그 타일을 화면 안으로 스크롤해 로딩을
      // 유도한다 -- 사용자가 직접 보고 있는 탭에서 화면이 제멋대로
      // 튀는 걸 막기 위한 안전장치.
      if (!thumb && document.hidden) {
        try { a.scrollIntoView({ block: "center" }); } catch (e) { /* ignore */ }
      }
      // 캡션이 보통 썸네일 img의 alt에 들어있지만, 가끔(2026-09-01 실측,
      // 인스타 릴스 1건) alt가 비어 있는 항목이 있다 -- 그럴 땐 링크 자체의
      // aria-label·title 속성에 같은 캡션이 들어있는 경우가 많아 대신 쓴다.
      var titleText = (thumb && thumb.alt) || a.getAttribute("aria-label") || a.getAttribute("title") || null;
      items.push({
        id: id,
        views: views,
        url: href.indexOf("http") === 0 ? href : location.origin + href,
        thumbnail: thumb ? thumb.url : null,
        title: titleText,
      });
    });
    return items;
  }

  // 진짜 링크가 없는 카드(네이버 클립)에서 쓰는 안정적인 id 생성기 --
  // 캡션 문자열이 같으면 항상 같은 값이 나오는 짧은 해시(djb2)다.
  function hashString(s) {
    var h = 5381;
    for (var i = 0; i < s.length; i++) h = ((h << 5) + h + s.charCodeAt(i)) | 0;
    return (h >>> 0).toString(36);
  }

  // href 대신 "라벨 span + 숫자 span" 형제 구조로 콘텐츠 카드를 찾는다
  // (네이버 클립 전용, 2026-09-03). 라벨 텍스트를 가진 span을 전부 찾고,
  // 바로 다음 형제에서 숫자를 읽는다. 카드를 식별할 href가 없어 카드를
  // 감싼 요소의 aria-label(캡션)을 대신 id 원본으로 쓴다.
  function collectLabeledCards(labelText) {
    var labelSpans = Array.prototype.slice.call(document.querySelectorAll("span")).filter(function (s) {
      return (s.textContent || "").trim() === labelText;
    });
    var seen = {};
    var items = [];
    labelSpans.forEach(function (span) {
      var numEl = span.nextElementSibling;
      var text = numEl ? (numEl.textContent || "").trim() : "";
      var numMatch = new RegExp(NUMBER).exec(text);
      if (!numMatch) return;
      var views = parseAbbrevNumber(numMatch[1], numMatch[2]);
      if (views == null) return;
      var card = span.closest("button[aria-label]") || span.closest("[aria-label]");
      var caption = card ? (card.getAttribute("aria-label") || "").trim() : "";
      if (!caption) return;
      var id = hashString(caption);
      if (seen[id]) return;
      seen[id] = true;
      var thumb = card ? extractImgUrl(card) : null;
      if (!thumb && card && document.hidden) {
        try { card.scrollIntoView({ block: "center" }); } catch (e) { /* ignore */ }
      }
      items.push({
        id: id,
        views: views,
        url: location.href,
        thumbnail: thumb ? thumb.url : null,
        title: caption,
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
      // 조회수만 찾았다고 바로 끝내지 않는다 -- 썸네일이 지연 로딩이라
      // 첫 시도엔 없다가 몇 초 뒤에 채워지는 경우가 많아서(2026-09-01
      // 실측), 아직 썸네일 없는 항목이 있으면 시간이 남아있는 한 계속
      // 재시도하고, 그래도 안 채워지면 시간 다 됐을 때 있는 그대로 보낸다.
      var missingThumb = items.length && items.some(function (it) { return !it.thumbnail; });
      if ((items.length && !missingThumb) || listAttempts >= LIST_MAX_ATTEMPTS) {
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

  if (rule.labelCapture) {
    var labelAttempts = 0;
    var LABEL_MAX_ATTEMPTS = 15;

    var labelTimer = setInterval(function () {
      labelAttempts++;
      var items = collectLabeledCards(rule.labelCapture);
      var missingThumb = items.length && items.some(function (it) { return !it.thumbnail; });
      if ((items.length && !missingThumb) || labelAttempts >= LABEL_MAX_ATTEMPTS) {
        clearInterval(labelTimer);
        if (items.length) {
          console.log("[SNS 인사이트]", rule.key, "콘텐츠 리스트", items.length, "개 찾음(라벨 방식) -> 기록 전송");
          chrome.runtime.sendMessage({
            type: "CONTENT_LIST_CAPTURE",
            platform: rule.key,
            items: items,
            capturedAt: new Date().toISOString(),
          });
        } else {
          console.log("[SNS 인사이트]", rule.key, "콘텐츠 리스트 못 찾음 -- 라벨 방식 (" + LABEL_MAX_ATTEMPTS + "초 시도)");
        }
      }
    }, 1000);
  }

  if (rule.multi || rule.listHrefPattern || rule.labelCapture) {
    // 전부 채널 콘텐츠 전용 흐름이라, 아래 회사 계정용 단일값 추출로는
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
