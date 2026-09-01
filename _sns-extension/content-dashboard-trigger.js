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
    // 확장을 chrome://extensions에서 새로고침한 직후, 이미 열려 있던
    // 탭의 content-script는 예전 연결을 그대로 문 채로 남아 "고아"
    // 상태가 된다 -- 이때 chrome.runtime 자체가 없어져 sendMessage가
    // 예외를 던진다(2026-09-01 실제 발생 확인: "Cannot read properties
    // of undefined (reading 'sendMessage')"). 탭을 새로고침하면 바로
    // 없어지는 일시적 상태라 조용히 무시한다 -- 사용자가 굳이 에러
    // 팝업을 볼 필요는 없다.
    try {
      chrome.runtime.sendMessage({ type: "CONTENT_COLLECT_REQUEST", force: true });
    } catch (e) {
      console.log("[SNS 인사이트] 확장 연결 끊김(탭을 새로고침하면 복구됩니다):", e);
    }
  });
})();
