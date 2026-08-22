---
layout: default
title: "칸반, 애자일의 Just In Time"
category: 'PO의 프레임웍'
cover_image: 'https://img1.kakaocdn.net/thumb/R1280x0.fjpg/?fname=http://t1.daumcdn.net/brunch/service/user/5lk/image/ah7ovuKnMstNcpqJXN9ZMHJTd2U.jpg'
date_string: 'Mar 28. 2025'
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
            window.location.href = '/log.html?cat=' + encodeURIComponent('PO의 프레임웍');
        });
    }
});
</script>
<!-- CAT_LINK_SCRIPT_END -->

안녕하세요, 애자일을 사랑하는 여러분! 오늘은 애자일과 DevOps의 핵심 프레임워크 중 하나인 '칸반'에 대해 이야기를 나누고자 합니다.

칸반은 Toyota에서 시작된 JIT(Just-In-Time) 생산 방식에 뿌리를 두고 있어요. 마치 슈퍼마켓에서 상품을 적시에 진열하듯, 칸반은 필요할 때 정확한 양의 작업이 이뤄지도록 흐름을 관리합니다.

![0*1fOoDoDSERuyIuVX](//img1.kakaocdn.net/thumb/R1280x0.fwebp/?fname=http://t1.daumcdn.net/brunch/service/user/5lk/image/qXZy77MqeJTqzoKqcH7Byubq_YA)

칸반의 핵심은 바로 '시각화'입니다. 모든 작업은 카드 형태로 칸반 보드에 표시되죠. 덕분에 진행 상황이 투명하게 공유되고, 병목 지점도 빠르게 발견할 수 있습니다. 또한 WIP(Work In Progress) 제한을 둬서 한 번에 처리하는 작업량을 최적화합니다. 이는 멀티태스킹을 줄이고 업무에 집중할 수 있게 해주죠.

![600px-Kanban_board_example.jpg](//img1.kakaocdn.net/thumb/R1280x0.fjpg/?fname=http://t1.daumcdn.net/brunch/service/user/5lk/image/S8MmeCGNy_41bfcM8bMUezQO3O8.jpg)

칸반 팀은 주기적으로 사이클 타임, 누적 흐름도 등의 지표를 살펴보며 지속적 개선을 도모합니다. 병목 현상의 원인을 찾고 개선점을 모색하는 거예요.

소프트웨어 개발에서 칸반은 효율적이고 유연한 작업 방식을 가능케 합니다. 개발팀은 우선순위에 따라 동적으로 일감을 가져가 처리하고, 고객에게 더 빠른 제공이 가능해집니다.

스크럼과는 달리 칸반은 고정된 주기나 역할이 없어요. 대신 계획의 유연성과 지속적 흐름에 초점을 맞춥니다. 물론 둘의 장점을 결합한 스크럼반(Scrumban)이라는 접근법도 있죠.

![Scrum-vs-Kanban-1-scaled.webp](//img1.kakaocdn.net/thumb/R1280x0.fwebp/?fname=http://t1.daumcdn.net/brunch/service/user/5lk/image/QgbvAwb9cojJ0OttjotdN6DVock.webp)

처음 칸반을 도입할 때는 칠판을 활용해도 좋아요. 하지만 본격적으로 적용하려면 Jira와 같은 가상 보드 도구가 필수적입니다. 이를 통해 팀원 간 협업과 소통이 원활해지죠.

지금까지 칸반의 기본 개념과 장점들을 살펴봤는데요. 칸반은 팀에게 직관적이고 신속한 워크플로우를 제공합니다. 함께 애자일의 컨베이어벨트, 칸반을 적용해보시죠.

<!-- CATEGORY_NAV_START -->
<style>
.category-nav-wrap { margin-top: 30px; margin-bottom: 0px; padding: 25px 40px; border-top: 1px solid rgba(245,243,238,0.1); display: flex; justify-content: space-between; align-items: center; font-family: 'Pretendard Variable', sans-serif; font-size: 14px; gap: 30px; width: 100vw; position: relative; left: 50%; transform: translateX(-50%); box-sizing: border-box; }
.cat-nav-item { display: flex; align-items: center; gap: 10px; text-decoration: none !important; color: #8f8b82; transition: color 0.2s; max-width: 45%; }
.cat-nav-item:hover { color: #f5f3ee; }
.cat-nav-item:hover .nav-title { color: #f5f3ee; text-decoration: underline; }
.cat-nav-label { font-size: 13px; color: #736f67; white-space: nowrap; font-weight: 300; }
.nav-title { font-weight: 400; color: #c9c8c2; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.cat-nav-right { margin-left: auto; justify-content: flex-end; text-align: right; }
</style>
<div class="category-nav-wrap">
  <a href="/brunch_web_assets/markdown/182_%EC%95%A0%EC%9E%90%EC%9D%BC%20vs%20%EC%9B%8C%ED%84%B0%ED%8F%B4%2C%20PO%EA%B0%80%20%EC%95%8C%EC%95%84%EC%95%BC%20%ED%95%A0%20%EB%AA%A8%EB%93%A0%20%EA%B2%83.html" class="cat-nav-item cat-nav-left"><span class="cat-nav-label">'PO의 프레임웍'의 이전글</span><span class="nav-title">애자일 vs 워터폴, PO가 알아야 할 모든 것</span></a>
  <a href="/brunch_web_assets/markdown/197_%EC%8A%A4%ED%81%AC%EB%9F%BC%20%EB%A7%88%EC%8A%A4%ED%84%B0%20vs%20%ED%94%84%EB%A1%9C%EC%A0%9D%ED%8A%B8%20%EB%A7%A4%EB%8B%88%EC%A0%80%27%20%EC%B0%A8%EC%9D%B4%EB%8A%94.html" class="cat-nav-item cat-nav-right"><span class="nav-title">스크럼 마스터 vs 프로젝트 매니저' 차이는?</span><span class="cat-nav-label">'PO의 프레임웍'의 다음글</span></a>
</div>
<!-- CATEGORY_NAV_END -->
