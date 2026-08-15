---
layout: default
title: "CPO는 어떻게 일을 할까? Part 1.2 생산구조"
category: '스타트업 인사이트'
cover_image: 'https://img1.kakaocdn.net/thumb/R1280x0.fpng/?fname=http://t1.daumcdn.net/brunch/service/user/5lk/image/w-3sbJnyigaY2G1ovbzvecXRq2U.png'
date_string: 'Apr 11. 2024'
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
            window.location.href = '/log.html?cat=' + encodeURIComponent('스타트업 인사이트');
        });
    }
});
</script>
<!-- CAT_LINK_SCRIPT_END -->

<!-- POST_DATE_START -->
<div style="color: #888; font-size: 14px; margin-bottom: 40px; font-family: 'Noto Sans KR', sans-serif; font-weight: 300;">Apr 11. 2024</div>
<!-- POST_DATE_END -->

1.

여러분이 만약 스마트폰 SW 전문가인데, 어느 날 갑자기 스마트폰 제조 공장의 공장장이 되어서 공장 제조 프로세스를 설계하고, 제조 컨베이어벨트를 설치하고, 각 위치 별로 사람을 배치하고, 스마트폰 요구사항을 취합한 후 각 컨베이어 벨트에 배분을 하는 역할로 바뀐다면 어떨까 같은가?

이게 PO가 CPO가 되었을 때의 상황과 유사하다. 성공적인 제품기획을 하고 만드는 것 잘하지만, 회사의 사업 방향에 맞게 생산체계를 만드는 게 주 업무로 바뀌게 되면서 업무의 난이도가 갑자기 높아지는 상황이 된다. 나도 이 지점에서 멘붕을 겪었던 것 같다.

2.

애자일 또는 스크럼방법론은 책이나 온라인에 상세한 자료들이 있기에 단일 스쿼드를 셋업하고 운영하는 건 어느 정도 가능할 것이다. 코칭을 하다 보면 스쿼드를 운영을 하는 곳은 많으나 도입의도 대로 지켜지지 않은 곳이 많은데, 이 건 별도의 애자일의 기본개념을 설명하는 섹션에서 다루도록 하겠다.

나는 통상 스타트업에서는 스쿼드 조직을 구성하는 걸 선호한다. 과제가 생겼을 때마다 팀을 구성하는 것보다 협업효율이 올라가고, 프로덕트 로드맵에 대기 중인 다음과제를 PO와 UX가 사전에 준비하여 업무효율을 올릴 수 있기 때문이다. 그리고 PO와 TL들이 해당 스쿼드의 과제와 조직을 책임지고 운영하기 때문에 책임감이나 주도성이 높아지는 점도 크다.

만약 스쿼드 하나가 잘 셋업 되었다면 나는 컨베이어 벨트 트랙이 하나가 완성된다고 본다. 그러면 사업적 목표달성을 위한 프로덕트로드맵 백로그 초안과 협업부서 과제 인입상태와 프로덕트 & 테크인원수를 보고 트랙수(스쿼드 수)를 결정한다. 그리고 각 트랙 별로 어떤 역할을 맡길지 설계를 한다.

3.

스타트업B가 나에게 코칭의뢰가 들어온 이유는, 프로덕트 조직에서 차기 투자 유치를 위한 핵심 서비스가 계속 지연된다는 것이었다. 프로덕트팀과 같이 일을 하면서 파악을 해보니 주요 프로젝트와 제휴 과제 그리고 유관부서 요청과제 등이 뒤섞여서 프로덕트 조직으로 인입이 되는 상황이었다. 임팩트와 생산효율 등을 고려한 우선순위 조율이 안된 채로 개인기로 처리하다 보니 급하다고 요청이 들어오는 과제에 끌려다니게 되고, 그러다 보니 주요 프로젝트는 착수조차도 못하는 상황이었다.

인원수를 보았을 때 2개 트랙(스쿼드)의 구성이 가능하여, 한쪽 트랙은 목표일정이 중요한 프로젝트를 담당하는 스쿼드(1번)로, 다른 쪽은 제휴사 일정에 따라 변동성이 큰 과제나 일정 중요도가 높지 않은 유관부서 요청과제를 담당하는 스쿼드(2번)로 역할을 부여했다. 해당 생산구조로 업무를 진행하니, 1번 스쿼드는 예상했던 일정에 가깝게 투자유치를 위한 프로젝트가 출시되었고, 2번 스쿼드는 제휴업무와 내부요청 프로세스 체계를 정리할 수 있게 되었다.

프로덕트 조직의 생산조직 체계는 위와 같이 사업목적에 맞게 구성을 해야 하며, 사업 상황에 따라 2번 스쿼드도 프로젝트에 투입될 수 있게 유연성을 가지게 운영을 해야 한다. 그리고 스쿼드 인력 변화와 사업아이템 인입현황에 따라 생산체계를 지속적으로 조율해 주는 것도 중요하다.

<!-- PROMO_BANNER_START -->
<div style="margin-top: 60px;">
<!-- OG_CARD_START -->
<a href="https://www.yes24.com/product/goods/193444437" target="_blank" style="display:flex; border:1px solid #e1e1e1; background-color:#fff; overflow:hidden; text-decoration:none !important; color:inherit; margin:20px 0; height:160px; transition:border-color 0.2s; font-family:'Noto Sans KR', sans-serif; border-radius: 8px;" onmouseover="this.style.borderColor='#111111'" onmouseout="this.style.borderColor='#e1e1e1'">
    <div style="flex:1; padding:25px 30px; display:flex; flex-direction:column; overflow:hidden;">
        <div style="font-size:22px; font-weight:300; color:#333; margin-bottom:12px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; letter-spacing:-0.5px;">UX의 언어들 | 한성희 | 파지트 - 예스24</div>
        <div style="font-size:14px; font-weight:300; color:#888; line-height:1.6; overflow:hidden; text-overflow:ellipsis; display:-webkit-box; -webkit-line-clamp:2; -webkit-box-orient:vertical; word-break:keep-all;">일상 속 UX의 발견UX 세계를 향한 친절한 안내서 『UX의 언어들』은 일상 속에 스며든 UX를 UX 디자이너의 시선으로 풀어내며, 우리가 이를 어떻게 경험하고 소비하는지 넷플릭스, 카카오 등 친숙한 사례를 통해 UX의 세계로 안내한다.UX는 제품, 서비스, ...</div>
        <div style="margin-top:auto; font-size:13px; font-weight:300; color:#999;">www.yes24.com</div>
    </div>
    <div style="width:25%; min-width:160px; background:url('https://image.yes24.com/goods/193444437/xl') center/cover no-repeat; border-left:1px solid #e1e1e1;"></div>
</a>
<!-- OG_CARD_END --></div>
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
  <a href="/brunch_web_assets/markdown/413_%ED%95%9C%EC%BD%94%EC%B9%98%EC%9D%98%20%27%EC%95%A0%EC%9E%90%EC%9D%BC%20%EC%99%9C%20%ED%95%98%EA%B2%8C%20%EB%90%98%EC%97%88%EC%9D%84%EA%B9%8C%27.html" class="cat-nav-item cat-nav-left"><span class="cat-nav-label">'스타트업 인사이트'의 이전글</span><span class="nav-title">한코치의 '애자일 왜 하게 되었을까?</span></a>
  <a href="/brunch_web_assets/markdown/420_CPO%EB%8A%94%20%EC%96%B4%EB%96%BB%EA%B2%8C%20%EC%9D%BC%EC%9D%84%20%ED%95%A0%EA%B9%8C%20Part11%20%EC%82%AC%EC%97%85%EB%AA%A9%ED%91%9C%EC%88%98%EB%A6%BD.html" class="cat-nav-item cat-nav-right"><span class="nav-title">CPO는 어떻게 일을 할까? Part1.1 사업목표수립</span><span class="cat-nav-label">'스타트업 인사이트'의 다음글</span></a>
</div>
<!-- CATEGORY_NAV_END -->
