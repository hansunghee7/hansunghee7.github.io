// SNS 인사이트 페이지(insight-7b3e9f2c/sns-insight.html)를 열면, 그 순간을
// "지금 확인하고 싶다"는 신호로 보고 background에 전체 수집 한 바퀴를
// 요청한다.
//
// 예약 작업(Windows 작업 스케줄러) 대신 이 방식을 쓰는 이유: 가족이 같이
// 쓰는 PC라 특정 시각(예: 밤 10시)에 이 PC가 켜져 있고 로그인되어 있다는
// 보장이 없다. 반면 "사장님이 이 대시보드를 열어서 확인하는 순간"은
// 정의상 PC가 켜져 있고 로그인되어 있는 게 보장된 시점이라 훨씬 확실하다.
(function () {
  chrome.runtime.sendMessage({ type: "SNS_INSIGHT_OPENED" });
})();
