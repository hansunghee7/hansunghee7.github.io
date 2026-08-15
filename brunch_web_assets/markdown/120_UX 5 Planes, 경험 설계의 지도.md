---
layout: default
title: "UX 5 Planes, 경험 설계의 지도"
category: '기획자의 프레임웍'
cover_image: 'https://img1.kakaocdn.net/thumb/R1280x0.fpng/?fname=http://t1.daumcdn.net/brunch/service/user/5lk/image/2P81qCe8gde1BjobwZ-zjL-o9NA.png'
date_string: 'Jun 3. 2025'
---

<!-- CAT_LINK_SCRIPT_START -->
<script>
document.addEventListener('DOMContentLoaded', function() {
    const catPill = document.querySelector('.cover-category-pill');
    if(catPill) {
        catPill.style.cursor = 'pointer';
        catPill.style.transition = 'all 0.2s ease';
        catPill.addEventListener('mouseenter', function() {
            this.style.backgroundColor = '#fff';
            this.style.color = '#111';
        });
        catPill.addEventListener('mouseleave', function() {
            this.style.backgroundColor = 'transparent';
            this.style.color = '#fff';
        });
        catPill.addEventListener('click', function() {
            window.location.href = '/log.html?cat=' + encodeURIComponent('기획자의 프레임웍');
        });
    }
});
</script>
<!-- CAT_LINK_SCRIPT_END -->

<!-- POST_DATE_START -->
<div style="color: #888; font-size: 14px; margin-bottom: 40px; font-family: 'Noto Sans KR', sans-serif; font-weight: 300;">Jun 3. 2025</div>
<!-- POST_DATE_END -->

2002년, 웹사이트와 앱이 점점 복잡해지면서 한 가지 문제가 대두되고 있었다. 사용자 경험을 어떻게 체계적으로 설계할 것인가? 제시 제임스 개럿(Jesse James Garrett)은 이 문제에 대한 명쾌한 답을 제시했다. 바로 'UX 5 Planes 모델'이다.

이 모델은 사용자 경험을 다섯 개의 층(Plane)으로 나누어 체계적으로 접근하는 프레임워크다. 마치 건물을 짓듯 아래에서 위로, 추상적인 단계에서 구체적인 단계로 차례차례 쌓아 올라간다. 각 층은 서로 유기적으로 연결되어 있으며, 하위 층의 결정이 상위 층에 영향을 미친다.

첫 번째 층인 '전략(Strategy)'은 모든 것의 출발점이다. "사용자와 비즈니스가 얻고자 하는 것은 무엇인가?"라는 근본적인 질문에 답한다. 여기서 사용자 요구사항, 비즈니스 목표, 페르소나가 정의된다.

두 번째 층인 '범위(Scope)'는 "무엇을 만들 것인가?"를 결정한다. 기능 목록, 콘텐츠 요구사항, 사용자 스토리가 이 단계의 산출물이다.

세 번째 층인 '구조(Structure)'는 정보와 기능이 어떻게 조직되고, 사용자 흐름이 어떻게 될지를 설계한다. 정보구조도, 사용자 플로우, 사이트맵이 만들어진다.

네 번째 층인 '뼈대(Skeleton)'는 정보와 UI 요소가 어떻게 배치될지를 결정한다. 와이어프레임, 내비게이션 설계, 인터페이스 설계가 이 단계의 핵심이다.

마지막 층인 '표면(Surface)'은 시각적 완성 단계로, 비주얼 디자인, UI 시안, 프로토타입이 탄생한다.

![1_onwMt3XG1X1BwSdqM-X16g.png](//img1.kakaocdn.net/thumb/R1280x0.fpng/?fname=http://t1.daumcdn.net/brunch/service/user/5lk/image/8codnZLVPVM5DQWEaYoNSsPbm_k.png)

구글은 이 프레임워크를 신규 서비스 기획에 적극 활용한다. 전략 단계에서 철저한 사용자 리서치와 비즈니스 목표를 정의하고, 범위 단계에서 MVP를 도출한다. 구조와 뼈대 단계에서는 빠른 프로토타이핑과 사용자 테스트를 반복하며, 표면 단계에서 브랜드 가이드라인에 맞춘 완성된 UI/UX를 만들어낸다.

에어비앤비는 사용자 여정 맵과 페르소나 정의를 전략 단계에서 진행하고, 각 단계별 산출물을 명확히 문서화하여 디자이너, 개발자, 기획자 간의 협업을 극대화한다. 국내 IT기업인 네이버와 카카오도 서비스 기획 시 5 Planes 모델을 도입해 각 단계별 산출물을 명확히 구분하고, 단계별 리뷰 및 피드백 과정을 체계화하여 품질을 높이고 있다.

![1_sWyyVWbBI72Jw2W3jhPXLQ.png](//img1.kakaocdn.net/thumb/R1280x0.fpng/?fname=http://t1.daumcdn.net/brunch/service/user/5lk/image/lQsYFynZAsa77aVDYk2q8Fb0hdg.png)

기획자가 이 프레임워크를 실전에 적용하려면 몇 가지 원칙을 기억해야 한다. 각 단계별 산출물을 미리 정의하고 체크리스트를 활용해 누락 없이 진행해야 한다. 기획, 디자인, 개발 등 각 역할별로 어느 단계에서 어떤 산출물이 필요한지 명확히 공유하면 커뮤니케이션 오류를 줄일 수 있다. 또한 각 단계에서 산출물을 빠르게 만들고 실제 사용자나 이해관계자와 피드백을 주고받으며 유연하게 수정해야 한다.

무엇보다 전략 단계부터 항상 '사용자에게 어떤 가치를 줄 것인가'를 중심에 두고, 각 단계별 의사결정에 반영해야 한다. 각 단계별 산출물을 문서화하고 팀 내외부에 공유하여 프로젝트의 일관성과 품질을 높이는 것도 중요하다.

제시 제임스 개럿은 이렇게 말했다.

"각 단계에서 내리는 결정이 상위 단계의 선택지를 제한하거나 확장할 수 있다. 각 단계가 서로 유기적으로 연결되어 있기 때문에, 프로젝트의 성공을 위해서는 단계별 산출물의 일관성과 유연성을 모두 확보해야 한다."

UX 5 Planes 모델은 복잡한 사용자 경험을 체계적으로 설계할 수 있는 강력한 나침반이다. 이 지도를 따라 한 단계씩 차근차근 올라가다 보면, 사용자와 비즈니스 모두 만족하는 경험을 설계할 수 있다.

**UX 설계에 대한 더 많은 질문이 궁금하다면...**

[**기획자의 질문법 - 예스24**

기획자가 던지는 질문조직이 만들어내는 결과이 책은 기획의 본질을 다시 묻는다. ‘이 기획은 왜 필요한가?’ ‘누구의 행동을 바꾸고 싶은가?’ ‘우리가 말하는 성공은 구체적으로 무엇인가

<!-- PROMO_BANNER_START -->
<div style="margin-top: 80px; margin-bottom: 20px;">
  <div style="display: flex; align-items: center; justify-content: center; gap: 20px; width: 100%; margin-bottom: 20px;">
    <div style="flex: 1; height: 1px; background-color: #e1e1e1;"></div>
    <span style="font-family: 'Playfair Display', 'Georgia', serif; font-style: italic; font-size: 16px; color: #888; letter-spacing: 0.5px; white-space: nowrap;">Simplifier Choice</span>
    <div style="flex: 1; height: 1px; background-color: #e1e1e1;"></div>
  </div>
<a href="https://www.yes24.com/product/goods/193444437" target="_blank" style="display:flex; border:1px solid #e1e1e1; background-color:#fff; overflow:hidden; text-decoration:none !important; color:inherit; margin:20px 0; height:160px; transition:border-color 0.2s; font-family:'Noto Sans KR', sans-serif; border-radius: 8px;" onmouseover="this.style.borderColor='#111111'" onmouseout="this.style.borderColor='#e1e1e1'">
    <div style="flex:1; padding:25px 30px; display:flex; flex-direction:column; overflow:hidden;">
        <div style="font-size:22px; font-weight:300; color:#333; margin-bottom:12px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; letter-spacing:-0.5px;">UX의 언어들 | 한성희 | 파지트 - 예스24</div>
        <div style="font-size:14px; font-weight:300; color:#888; line-height:1.6; overflow:hidden; text-overflow:ellipsis; display:-webkit-box; -webkit-line-clamp:2; -webkit-box-orient:vertical; word-break:keep-all;">일상 속 UX의 발견UX 세계를 향한 친절한 안내서 『UX의 언어들』은 일상 속에 스며든 UX를 UX 디자이너의 시선으로 풀어내며, 우리가 이를 어떻게 경험하고 소비하는지 넷플릭스, 카카오 등 친숙한 사례를 통해 UX의 세계로 안내한다.UX는 제품, 서비스, ...</div>
        <div style="margin-top:auto; font-size:13px; font-weight:300; color:#999;">www.yes24.com</div>
    </div>
    <div style="width:25%; min-width:160px; background:url('https://image.yes24.com/goods/193444437/xl') center/cover no-repeat; border-left:1px solid #e1e1e1;"></div>
</a>
</div>
<!-- PROMO_BANNER_END -->


<!-- CATEGORY_NAV_START -->
<style>
.category-nav-wrap { margin-top: 60px; padding: 25px 40px; border-top: 1px solid #e1e1e1; display: flex; justify-content: space-between; align-items: center; font-family: 'Noto Sans KR', sans-serif; font-size: 14px; color: #888; gap: 30px; width: 100vw; position: relative; left: 50%; transform: translateX(-50%); box-sizing: border-box; }
.cat-nav-item { display: flex; align-items: center; gap: 10px; text-decoration: none !important; color: #666; transition: color 0.2s; max-width: 45%; }
.cat-nav-item:hover { color: #111; }
.cat-nav-item:hover .nav-title { color: #111; text-decoration: underline; }
.cat-nav-label { font-size: 13px; color: #999; white-space: nowrap; font-weight: 300; }
.nav-title { font-weight: 400; color: #333; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.cat-nav-right { margin-left: auto; justify-content: flex-end; text-align: right; }
</style>
<div class="category-nav-wrap">
  <a href="/brunch_web_assets/markdown/112_%27%ED%8F%AC%ED%84%B0%EC%9D%98%205%20Forces%27%20%EC%A0%84%EC%9F%81%ED%84%B0%EB%A5%BC%20%EB%B6%84%EC%84%9D%ED%95%98%EB%8A%94%20%EB%B2%95.html" class="cat-nav-item cat-nav-left"><span class="cat-nav-label">'기획자의 프레임웍'의 이전글</span><span class="nav-title">포터의 5 Forces' 전쟁터를 분석하는 법</span></a>
  <a href="/brunch_web_assets/markdown/128_%EA%B3%A0%EA%B0%9D%EC%9D%80%20%EC%A0%9C%ED%92%88%EC%9D%84%20%27%EA%B3%A0%EC%9A%A9%27%ED%95%9C%EB%8B%A4%20%27JTBD%ED%94%84%EB%A0%88%EC%9E%84%EC%9B%8D%27.html" class="cat-nav-item cat-nav-right"><span class="nav-title">고객은 제품을 '고용'한다. 'JTBD프레임웍</span><span class="cat-nav-label">'기획자의 프레임웍'의 다음글</span></a>
</div>
<!-- CATEGORY_NAV_END -->
