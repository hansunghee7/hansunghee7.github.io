// claude-usage.html(스튜디오)의 "↻ 새로고침" 버튼이 이 CustomEvent를
// 쏘면, background.js에 클로드 사용량만 지금 바로 다시 확인해달라고
// 요청한다. dashboard-trigger.js(SNS 인사이트용)와 같은 패턴이지만
// 대상 라운드가 다르다 -- 여기서는 5개 SNS를 다 돌 필요 없이 클로드
// 사용량 페이지 하나만 연다.
(function () {
  window.addEventListener("simplifier-claude-usage-refresh", function () {
    try {
      chrome.runtime.sendMessage({ type: "CLAUDE_USAGE_COLLECT_REQUEST", force: true });
    } catch (e) {
      console.log("[클로드 사용량] 확장 연결 끊김(탭을 새로고침하면 복구됩니다):", e);
    }
  });
})();
