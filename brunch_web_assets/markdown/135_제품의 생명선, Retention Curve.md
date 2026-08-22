---
layout: default
title: "제품의 생명선, Retention Curve"
category: '기획자의 프레임웍'
cover_image: 'https://img1.kakaocdn.net/thumb/R1280x0.fpng/?fname=http://t1.daumcdn.net/brunch/service/user/5lk/image/BnsMe-pk1geAJExVw7b4sPlcvU4.png'
date_string: 'May 20. 2025'
---

<!-- CAT_LINK_SCRIPT_START -->
<script>
document.addEventListener('DOMContentLoaded', function() {
    const catPill = document.querySelector('.cover-category-pill');
    if(catPill) {
        catPill.style.cursor = 'pointer';
        catPill.style.transition = 'all 0.2s ease';
        catPill.addEventListener('mouseenter', function() {
            this.style.backgroundColor = '#f5f3ee';
            this.style.color = '#080808';
        });
        catPill.addEventListener('mouseleave', function() {
            this.style.backgroundColor = 'transparent';
            this.style.color = '#f5f3ee';
        });
        catPill.addEventListener('click', function() {
            window.location.href = '/log.html?cat=' + encodeURIComponent('기획자의 프레임웍');
        });
    }
});
</script>
<!-- CAT_LINK_SCRIPT_END -->

사용자를 얻는 것보다 더 중요한 것은 사용자를 유지하는 것이다. 실리콘밸리의 성공한 스타트업들이 공통적으로 주목하는 '리텐션 커브(Retention Curve)'는 이런 철학에서 탄생했다. 이 프레임워크는 단순히 숫자로만 보이던 사용자 유지율을 시각적인 이야기로 전환한다.

리텐션 커브는 특정 기간(보통 일, 주, 월 단위)에 서비스를 시작한 사용자 집단(코호트)이 시간이 지남에 따라 얼마나 서비스에 남아있는지 보여주는 그래프다. 가로축은 시간(1일, 7일, 30일 등), 세로축은 사용자 잔존율(%)을 나타낸다. 이 커브는 제품의 '건강도'와 성장 가능성을 한눈에 진단할 수 있게 해준다.

![a-1738677772446-2x.jpg](//img1.kakaocdn.net/thumb/R1280x0.fjpg/?fname=http://t1.daumcdn.net/brunch/service/user/5lk/image/7Pgc7PeeAp2EAKbHo_MTYr3f6jo.jpg)

리텐션 커브는 대개 세 가지 패턴으로 나타난다. 첫째, '빠른 하락 후 소멸'형은 사용자들이 빠르게 이탈하고 결국 거의 남지 않는 패턴으로, 제품-시장 적합성(PMF)에 실패한 경우다. 둘째, '빠른 하락 후 평탄화'형은 초기 이탈 후 일정 비율의 사용자가 장기간 남는 패턴으로, 핵심 사용자층을 확보한 상태다. 셋째, '완만한 하락 후 평탄화'형은 초기 이탈이 적고 높은 비율의 사용자가 유지되는 패턴으로, 강력한 PMF를 달성한 상태를 의미한다.

![0_ObQUvRFPNc2Y8YZo.png](//img1.kakaocdn.net/thumb/R1280x0.fpng/?fname=http://t1.daumcdn.net/brunch/service/user/5lk/image/0lXQLmjh8BOSZCO3m2Nj_zB19oo.png)

슬랙(Slack)은 이 프레임워크를 적극 활용한 기업이다. 그들은 리텐션 커브를 분석해 새로운 팀 멤버가 첫 주에 최소 2,000개의 메시지를 주고받을 때 장기 사용률이 급증한다는 사실을 발견했다. 이를 '아하 모먼트(Aha Moment)'로 정의하고, 이 경험을 강화하는 온보딩 과정을 설계해 사용자 유지율을 크게 개선했다.

넷플릭스도 리텐션 커브를 통해 사용자가 첫 30일 내에 최소 15시간 이상 콘텐츠를 시청할 때 장기 구독자로 전환될 확률이 높다는 사실을 발견했다. 이를 바탕으로 개인화된 추천 알고리즘을 강화하고, 신규 가입자의 빠른 콘텐츠 몰입을 유도하는 전략을 구사했다.

![1_NxnFAysAapMiNX3Atfw_Fw.png](//img1.kakaocdn.net/thumb/R1280x0.fpng/?fname=http://t1.daumcdn.net/brunch/service/user/5lk/image/fH6DssEbsJS8sk3WMzInh2mGKj0.png)

기획자가 리텐션 커브를 실전에 적용하는 방법은 다음과 같다. 먼저, 가입 시기나 유입 경로 등 다양한 기준으로 코호트를 나누고, 각 집단의 리텐션 커브를 그려 비교한다. 커브가 급격히 하락하는 구간에 주목해 온보딩, 첫 경험, 핵심 기능 노출 등의 문제점을 찾아 개선한다.

또한, 여러 코호트의 평균 리텐션 커브를 그려 전체 서비스 건강도를 진단하고, 평탄화되는 구간을 KPI로 삼아 장기 사용자 확보 전략을 수립한다. 특정 행동(예: 첫 구매, 친구 초대 등)과 리텐션 커브의 상관관계를 분석해 장기 잔존율을 높이는 핵심 경험을 강화하는 것도 중요하다.

리텐션 커브는 단순한 수치 이상의 인사이트를 제공한다. 이 커브의 모양은 제품의 미래를 예측하는 결정적 신호다. 스타트업 투자자들이 가장 먼저 보는 지표 중 하나가 리텐션 커브인 이유다. 결국 성장의 핵심은 신규 사용자 확보가 아니라, 기존 사용자의 장기적 충성도에 있기 때문이다.

<!-- CATEGORY_NAV_START -->
<style>
.category-nav-wrap { margin-top: 20px; margin-bottom: 20px; padding: 25px 40px; border-top: 1px solid rgba(245,243,238,0.1); display: flex; justify-content: space-between; align-items: center; font-family: 'Pretendard Variable', sans-serif; font-size: 14px; gap: 30px; width: 100vw; position: relative; left: 50%; transform: translateX(-50%); box-sizing: border-box; }
.cat-nav-item { display: flex; align-items: center; gap: 10px; text-decoration: none !important; color: #8f8b82; transition: color 0.2s; max-width: 45%; }
.cat-nav-item:hover { color: #f5f3ee; }
.cat-nav-item:hover .nav-title { color: #f5f3ee; text-decoration: underline; }
.cat-nav-label { font-size: 13px; color: #736f67; white-space: nowrap; font-weight: 300; }
.nav-title { font-weight: 400; color: #c9c8c2; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.cat-nav-right { margin-left: auto; justify-content: flex-end; text-align: right; }
</style>
<div class="category-nav-wrap">
  <a href="/brunch_web_assets/markdown/128_%EA%B3%A0%EA%B0%9D%EC%9D%80%20%EC%A0%9C%ED%92%88%EC%9D%84%20%27%EA%B3%A0%EC%9A%A9%27%ED%95%9C%EB%8B%A4%20%27JTBD%ED%94%84%EB%A0%88%EC%9E%84%EC%9B%8D%27.html" class="cat-nav-item cat-nav-left"><span class="cat-nav-label">'기획자의 프레임웍'의 이전글</span><span class="nav-title">고객은 제품을 '고용'한다. 'JTBD프레임웍</span></a>
  <a href="/brunch_web_assets/markdown/142_%27%EC%BD%94%ED%98%B8%ED%8A%B8%20%EB%B6%84%EC%84%9D%27%20%ED%8F%89%EA%B7%A0%EC%9D%98%20%ED%95%A8%EC%A0%95%EC%97%90%EC%84%9C%20%EB%B2%97%EC%96%B4%EB%82%98%EB%8A%94%20%EB%B2%95.html" class="cat-nav-item cat-nav-right"><span class="nav-title">코호트 분석' 평균의 함정에서 벗어나는 법</span><span class="cat-nav-label">'기획자의 프레임웍'의 다음글</span></a>
</div>
<!-- CATEGORY_NAV_END -->
