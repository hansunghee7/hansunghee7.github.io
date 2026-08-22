---
layout: default
title: "CPO는 어떻게 일을 할까? Part 2. 수평적 관점"
category: '스타트업 인사이트'
cover_image: 'https://img1.kakaocdn.net/thumb/R1280x0.fpng/?fname=http://t1.daumcdn.net/brunch/service/user/5lk/image/bN12f_v__Mg07l-jvhrke3rHL1E.png'
date_string: 'Apr 7. 2024'
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
            window.location.href = '/log.html?cat=' + encodeURIComponent('스타트업 인사이트');
        });
    }
});
</script>
<!-- CAT_LINK_SCRIPT_END -->

CPO가 되었을 때 단일 스쿼드를 관리하던 PM/PO 때와는 수준이 다른 다양한 난감한 일들이 생긴다. 그중 가장 어려워하는 점은 Part 1의 '복수의 스쿼드가 효과적으로 돌아가는 생산 조직 체계를 구성하는 것'과 이번 Part2의 '프로덕트 조직과 유관 부서 간의 과제 인입 프로토콜을 만드는 것'이다.

 CPO가 되면 Part 1의 경영진 회의에서 결정된 프로덕트 로드맵 과제 외에 CEO를 비롯하여 여러 부서에서 업무요청이 들어온다. 이 것을 효과적으로 관리하지 않으면, 스프린트가 망가지던가 유관부서와의 사이가 망가지던가 둘 중의 하나의 결과로 귀결이 된다.

 아래는 내가 다양한 회사들을 거치면서 가장 효과적이었던 유관부서의 요구사항(과제)들이 생산라인에 유입되는 업무흐름이다.

---

 **수평적인 업무 흐름**

 1. CPO는 각 부서의 요구사항 백로그를 마케팅, CX, 세일즈 등의 유관부서들이 상시로 등록할 수 있는 채널을 만든다. 단, 이 백로그가 개발에 들어가는 바로 섞여서는 안 된다.(나 같은 경우는 유관부서들이 쉽게 쓸 수 있는 노션, 엑셀 등에 사서함, VOC대시보드, 114채널 등의 이름으로 만든다.)

 2. CPO는 CTO와 함께 상시 또는 정기적으로 유관부서 백로그를 리뷰하며, 시급도, 영향도, 개발사이즈를 러프하게 분석한다.

 3. 중요도가 높으나 사이즈가 큰 백로그는 프로덕트 로드맵으로 이동하여 관리하고, 시급도가 높으면서 개발이 간단한 건은 테크 쪽과 협의하며 개발스프린트에 포함시킨다.

 단, 간단 과제들 때문에 로드맵 과제들의 출시일정에 큰 영향을 주어서는 안 된다. 영향이 크면 로드맵과제로 이동을 시켜서 경영진 회의에서 우선순위를 정한다.

 4. 협업부서 요구사항 외에도 자체 프로덕트 개선사항, VOC 등의 전체 백로그를 서비스 영역 별로 분류한다. 그중 시급도와 사업적 중요도가 높은 건은 독립적으로 선진행하고, 그 외는 해당 영역 개선이 진행될 때 백로그를 참고해서 함께 반영되도록 한다.(경험적으로 봤을 때 프로덕트 개선과 협업부서 요구사항을 효과적으로 반영할 수 있는 방법이었다.)

 5. CPO는 경영진 회의에서 타 C레벨과 로드맵과제와 시급도가 높은 과제를 조율하고, 실무협의 정기미팅을 통해 실무레벨의 과제 진행 및 협업 프로토콜을 논의한다.

 6. CPO는 협업부서들의 정기미팅 / 산출자료 등을 통해 타 부서 활동을 대한 이해를 높이고 유지해야 한다.

 7. CPO는 협업부서 키맨들과 1on1, 티타임, 식사 등을 통해 프로덕트 쪽 상황과 백로그 우선순위 수립 정책울 공유하고, 타 부서의 업무방식, 애로상황 상황을 청취하면 더욱 좋다.

---

 프로덕트 만들기를 본인만이 주도하는 작가주의 정신으로 접근하거나, 여러 사람들의 이견 조율에 능숙하지 않은 사람은 이 수평적인 업무흐름 관리에 큰 어려움을 겪을 것이다.

 본인이 위 역할을 수행할 수 있도록, 위 프로세스를 도입하고 유관부서 사람들과 효과적인 소통을 하는 트레이닝을 하기를 바란다.

 여러분들 회사의 수평적인 업무흐름은 어떠한가요? 어려움이 있다면 댓글을 남겨주세요. :-)

<!-- CATEGORY_NAV_START -->
<style>
.category-nav-wrap { margin-top: 5px; margin-bottom: 40px; padding: 25px 40px; border-top: 1px solid rgba(245,243,238,0.1); display: flex; justify-content: space-between; align-items: center; font-family: 'Pretendard Variable', sans-serif; font-size: 14px; gap: 30px; width: 100vw; position: relative; left: 50%; transform: translateX(-50%); box-sizing: border-box; }
.cat-nav-item { display: flex; align-items: center; gap: 10px; text-decoration: none !important; color: #8f8b82; transition: color 0.2s; max-width: 45%; }
.cat-nav-item:hover { color: #f5f3ee; }
.cat-nav-item:hover .nav-title { color: #f5f3ee; text-decoration: underline; }
.cat-nav-label { font-size: 13px; color: #736f67; white-space: nowrap; font-weight: 300; }
.nav-title { font-weight: 400; color: #c9c8c2; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.cat-nav-right { margin-left: auto; justify-content: flex-end; text-align: right; }
</style>
<div class="category-nav-wrap">
  <a href="/brunch_web_assets/markdown/422_CPO%EB%8A%94%20%EC%96%B4%EB%96%BB%EA%B2%8C%20%EC%9D%BC%EC%9D%84%20%ED%95%A0%EA%B9%8C%20Part%203%20%ED%9D%90%EB%A6%84%EC%9D%98%20%EA%B2%B0%ED%95%A9.html" class="cat-nav-item cat-nav-left"><span class="cat-nav-label">'스타트업 인사이트'의 이전글</span><span class="nav-title">CPO는 어떻게 일을 할까? Part 3. 흐름의 결합</span></a>
  <a href="/brunch_web_assets/markdown/424_CPO%EB%8A%94%20%EC%96%B4%EB%96%BB%EA%B2%8C%20%EC%9D%BC%EC%9D%84%20%ED%95%A0%EA%B9%8C%20Part%201%20%EC%88%98%EC%A7%81%EC%A0%81%20%EA%B4%80%EC%A0%90.html" class="cat-nav-item cat-nav-right"><span class="nav-title">CPO는 어떻게 일을 할까? Part 1. 수직적 관점</span><span class="cat-nav-label">'스타트업 인사이트'의 다음글</span></a>
</div>
<!-- CATEGORY_NAV_END -->
