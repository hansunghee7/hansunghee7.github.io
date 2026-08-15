---
layout: default
title: "Perplexity #1 검색의 한계를 넘어서"
category: '스타트업 인사이트'
cover_image: 'https://img1.kakaocdn.net/thumb/R1280x0.fjpg/?fname=http://t1.daumcdn.net/brunch/service/user/5lk/image/zElxWkUx4Jed427xLvwKEbFV7YU.jpg'
date_string: 'Apr 20. 2025'
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
<div style="color: #888; font-size: 14px; margin-bottom: 40px; font-family: 'Noto Sans KR', sans-serif; font-weight: 300;">Apr 20. 2025</div>
<!-- POST_DATE_END -->

안녕하세요, 스타트업 성공코치 한성희입니다. 오늘부터 5주간 '검색의 재정의'를 이끌고 있는 Perplexity AI의 기술을 심층 분석하는 시리즈를 시작합니다.

### **기존 검색 엔진의 구조적 한계**

구글이 검색 시장을 장악한 지 20년이 넘었습니다. 그동안 PageRank 알고리즘과 수많은 개선에도 불구하고, 전통적인 검색 엔진은 몇 가지 근본적인 한계에 부딪혔습니다.

첫째, 링크 기반 랭킹의 한계입니다. 구글의 PageRank는 다른 웹사이트로부터 받는 링크의 수와 품질을 기준으로 웹페이지의 중요도를 평가합니다. 이 방식은 SEO(검색 엔진 최적화)를 통한 조작이 가능하여, 실제 품질보다 최적화된 콘텐츠가 상위에 노출되는 문제가 있습니다.

둘째, 키워드 매칭에 대한 지나친 의존입니다. 기존 검색 엔진은 사용자가 입력한 키워드와 웹페이지에 있는 단어의 일치도를 중심으로 결과를 제공합니다. 이는 사용자의 의도를 정확히 파악하지 못하는 경우가 많습니다. "애플 주가 어떻게 될까?"라는 질문에 단순히 '애플'과 '주가'가 포함된 수많은 링크를 나열하는 것이 과연 최선일까요?

셋째, 정보 과부하의 문제입니다. 검색 결과로 수백만 개의 링크가 제공되지만, 정작 사용자는 첫 페이지의 몇 개 링크만 확인합니다. 정보의 홍수 속에서 사용자는 여전히 갈증을 느끼고 있습니다.

![](//img1.kakaocdn.net/thumb/R1280x0.fpng/?fname=https://t1.daumcdn.net/brunch/service/user/5lk/image/oJSRAog0AIQl4aN20nHWSZRLfTU.png)

### **생성형 AI 시대의 새로운 정보 탐색 기준**

ChatGPT의 등장으로 사람들은 정보를 얻는 새로운 방식을 경험했습니다. 링크를 클릭하고 내용을 판단하는 과정 없이, 질문에 대한 직접적인 답변을 받을 수 있게 된 것입니다. 하지만 생성형 AI에도 명확한 한계가 있었습니다.

가장 큰 문제는 최신성입니다. GPT-4와 같은 대규모 언어 모델은 특정 시점까지의 데이터로 학습되며, 그 이후의 정보는 알지 못합니다. 또한 출처 검증이 불가능하다는 점도 중요한 한계입니다. AI가 제공하는 정보가 어디서 왔는지 추적할 수 없어 신뢰성 문제가 발생합니다.

이러한 상황에서 등장한 것이 바로 Perplexity AI입니다. Perplexity는 검색 엔진의 최신 정보 접근성과 생성형 AI의 자연어 이해 및 답변 생성 능력을 결합해 "Real-time, trustworthy, cited answers"라는 비전을 실현하고자 합니다.

![](//img1.kakaocdn.net/thumb/R1280x0.fjpg/?fname=https://t1.daumcdn.net/brunch/service/user/5lk/image/a3DRN0AoZlFZsNW41DzcLJv0gO0.jpg)

### **Perplexity의 탄생 배경과 철학**

Perplexity AI는 2022년 8월 캘리포니아에서 설립되었습니다. 창업자 아라빈드 스리니바스(Aravind Srinivas)는 구글 브레인 출신으로, OpenAI에서 연구원으로 일한 경험이 있습니다. 그는 검색의 미래가 단순한 링크 나열이 아닌, 질문에 대한 직접적인 답변 제공에 있다고 확신했습니다.

Perplexity의 철학은 다음 세 가지로 요약됩니다:

정보의 실시간성(Real-time): 최신 정보를 포함한 답변 제공

신뢰성(Trustworthy): 검증 가능한 정보만을 기반으로 한 답변

출처 명시(Cited): 모든 정보의 출처를 투명하게 공개

이 철학을 기술적으로 구현하기 위해 Perplexity는 RAG(Retrieval-Augmented Generation) 아키텍처를 채택했습니다. 이는 검색(Retrieval)과 생성(Generation)을 결합한 접근법으로, 웹에서 실시간으로 정보를 검색하고 이를 바탕으로 AI가 응답을 생성하는 방식입니다.

![](//img1.kakaocdn.net/thumb/R1280x0.fpng/?fname=https://t1.daumcdn.net/brunch/service/user/5lk/image/Si92b-5e_E_4W0hlMcz4B-_0xd8.png)

### **RAG: 검색과 생성의 결합**

RAG는 단순히 기술적 접근법을 넘어 정보 소비 방식의 패러다임 전환을 의미합니다. 기존에는 검색 결과로 제공된 여러 웹페이지를 사용자가 직접 읽고 종합하는 '정보 수집 과정'이 필요했습니다. Perplexity는 이 과정을 AI가 대신 수행하고, 사용자에게는 요약된 답변만 제공함으로써 인지 부하를 줄였습니다.

RAG가 가진 강점은 다음과 같습니다:

최신 정보 접근: 실시간 웹 검색을 통해 최신 정보를 포함할 수 있음

출처 추적 가능: 정보의 출처를 명확히 제시하여 신뢰성 확보

환각(Hallucination) 감소: 검색된 사실에 기반한 답변으로 AI의 창작 억제

이러한 접근법은 특히 금융, 의학, 법률과 같이 정확성과 최신성이 중요한 분야에서 큰 가치를 발휘합니다.

### **혁신적인 UX: 대화형 검색 경험**

Perplexity는 기술적 혁신뿐만 아니라 사용자 경험(UX) 측면에서도 큰 변화를 가져왔습니다. 기존 검색 엔진이 '검색창 → 결과 페이지 → 링크 클릭 → 내용 확인'이라는 다단계 과정을 요구했다면, Perplexity는 대화하듯 질문하고 바로 답변을 받는 단순한 흐름을 제공합니다.

특히 주목할 만한 UX 요소는 다음과 같습니다:

실시간 답변 생성: 타이핑되는 것처럼 답변이 생성되어 기다림의 지루함 감소

출처 링크 인라인 표시: 답변 내용 중 관련 부분에 직접 출처 링크 제공

후속 질문 제안: 현재 주제와 관련된 추가 질문을 자동으로 제안

대화 맥락 유지: 이전 질문과 답변을 기억하여 맥락 기반 응답 생성

이러한 대화형 인터페이스는 검색을 '질의응답'에서 '대화'로 발전시켰습니다. 사용자는 마치 지식이 풍부한 전문가와 대화하는 듯한 경험을 하게 됩니다.

![](//img1.kakaocdn.net/thumb/R1280x0.fjpg/?fname=https://t1.daumcdn.net/brunch/service/user/5lk/image/TI5I2mg7JvgJp_gKg8W6cJkSsA8.jpg)

### **실제 비즈니스 적용 가능성**

Perplexity의 접근법은 다양한 비즈니스 영역에서 응용될 수 있습니다:

기업 내부 지식베이스: 회사 문서, 매뉴얼, 정책 등을 RAG 모델로 연동하여 직원들이 자연어로 질문하고 답변받을 수 있는 시스템

고객 지원 시스템: 제품 설명서, FAQ, 이전 지원 사례 등을 기반으로 고객 질문에 정확하고 출처가 명시된 답변 제공

산업 특화 검색 엔진: 의료, 법률, 금융 등 특정 도메인에 특화된 지식 검색 시스템

이러한 응용은 단순히 기존 검색 엔진을 대체하는 것이 아니라, 정보 접근성과 활용도를 획기적으로 높이는 방향으로 발전할 것입니다.

다음 편에서는 Perplexity의 핵심 기술 아키텍처를 자세히 분석하겠습니다. BM25와 같은 전통적인 검색 알고리즘부터 벡터 검색, RAG 구현 방식까지 실전적인 관점에서 살펴보겠습니다.

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
  <a href="/brunch_web_assets/markdown/165_Perplexity%20%232%20%EA%B2%80%EC%83%89%20%EC%8B%9C%EC%8A%A4%ED%85%9C%EC%9D%98%20%EA%B5%AC%EC%A1%B0%20%EC%84%A4%EA%B3%84.html" class="cat-nav-item cat-nav-left"><span class="cat-nav-label">'스타트업 인사이트'의 이전글</span><span class="nav-title">Perplexity #2 검색 시스템의 구조 설계</span></a>
  <a href="/brunch_web_assets/markdown/172_%EC%8A%A4%ED%83%80%ED%8A%B8%EC%97%85%20%EC%B0%BD%EC%97%85%EC%9D%80%20%EC%96%B4%EB%96%BB%EA%B2%8C%20%ED%95%98%EB%82%98%EC%9A%94.html" class="cat-nav-item cat-nav-right"><span class="nav-title">스타트업 창업은 어떻게 하나요?</span><span class="cat-nav-label">'스타트업 인사이트'의 다음글</span></a>
</div>
<!-- CATEGORY_NAV_END -->
