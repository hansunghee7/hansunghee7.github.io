// SNS 인사이트 페이지(insight-7b3e9f2c/sns-insight.html)를 열면, 그 순간을
// "지금 확인하고 싶다"는 신호로 보고 background에 전체 수집 한 바퀴를
// 요청한다.
//
// 예약 작업(Windows 작업 스케줄러) 대신 이 방식을 쓰는 이유: 가족이 같이
// 쓰는 PC라 특정 시각(예: 밤 10시)에 이 PC가 켜져 있고 로그인되어 있다는
// 보장이 없다. 반면 "사장님이 이 대시보드를 열어서 확인하는 순간"은
// 정의상 PC가 켜져 있고 로그인되어 있는 게 보장된 시점이라 훨씬 확실하다.
(function () {
  chrome.runtime.sendMessage({ type: "SNS_COLLECT_REQUEST" });

  // 페이지 자체(sns-insight.html)의 "↻ 새로고침" 버튼을 누르면 이
  // CustomEvent를 쏘도록 되어 있다. content-script는 페이지의 window
  // 이벤트를 그대로 들을 수 있으므로(격리된 JS 실행환경이지만 DOM/이벤트는
  // 공유), 그걸 받아서 background에 "강제로" 수집해달라고 요청한다 --
  // 방금 열었어도 사용자가 명시적으로 다시 눌렀다는 뜻이라 쿨다운을 넘긴다.
  window.addEventListener("simplifier-sns-force-refresh", function () {
    chrome.runtime.sendMessage({ type: "SNS_COLLECT_REQUEST", force: true });
  });
})();
