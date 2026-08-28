// SNS 인사이트 페이지(insight-7b3e9f2c/sns-insight.html)의 "↻ 새로고침"
// 버튼을 누르면 이 CustomEvent를 쏘도록 되어 있다. content-script는 페이지의
// window 이벤트를 그대로 들을 수 있으므로(격리된 JS 실행환경이지만 DOM/이벤트는
// 공유), 그걸 받아서 background에 전체 수집 한 바퀴를 "강제로" 요청한다
// (쿨다운 무시 -- 사용자가 명시적으로 지금 다시 확인해달라는 뜻이므로).
//
// 예전엔 이 페이지를 "열기만 해도" 자동으로 돌았는데, 스튜디오 메뉴를
// 옮겨다닐 때마다(=이 페이지를 열 때마다) 매번 8개를 새로 도는 게 과했다는
// 피드백으로 없앴다 -- 이제는 새로고침을 실제로 눌렀을 때만 돈다. (8개 중
// 아무 SNS나 직접 방문할 때 도는 것은 content-script.js의 별개 로직으로,
// 스튜디오 메뉴 이동과 무관한 실제 SNS 사용이라 그대로 둔다.)
(function () {
  window.addEventListener("simplifier-sns-force-refresh", function () {
    chrome.runtime.sendMessage({ type: "SNS_COLLECT_REQUEST", force: true });
  });
})();
