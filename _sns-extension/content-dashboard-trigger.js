// 콘텐츠 인사이트 페이지(insight-7b3e9f2c/content-insight.html)의 "↻
// 새로고침" 버튼을 누르면 이 CustomEvent를 쏘도록 되어 있다. dashboard-
// trigger.js(SNS 인사이트용)와 완전히 같은 구조로, "신기한 아파트사전"
// 콘텐츠 채널(네이버 클립·인스타·스레드·페이스북·틱톡·X) 라운드를
// 강제로 요청한다(2026-09-01, "새로고침하면 실시간 데이터를 가져왔으면
// 한다"는 요청에 대응 -- 이 페이지 JS만으로는 로그인된 각 사이트를
// 읽을 수 없어서, 실제로 로그인된 이 확장이 백그라운드에서 각 페이지를
// 대신 열었다 닫아주는 방식으로 "최대한 실시간에 가깝게" 만든다).
(function () {
  window.addEventListener("simplifier-content-force-refresh", function () {
    chrome.runtime.sendMessage({ type: "CONTENT_COLLECT_REQUEST", force: true });
  });
})();
