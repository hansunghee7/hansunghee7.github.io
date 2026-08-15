---
layout: default
title: "Perplexity#5 자체 구축을 위한 로드맵"
category: '스타트업 인사이트'
cover_image: 'https://img1.kakaocdn.net/thumb/R1280x0.fjpg/?fname=http://t1.daumcdn.net/brunch/service/user/5lk/image/-AehHKNV0YOkhOpsssKNfto3KP0.jpg'
date_string: 'May 18. 2025'
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

Perplexity AI 기술 해부 시리즈의 마지막 시간입니다. 지금까지 Perplexity의 철학, 핵심 기술 아키텍처, BM25와 벡터 검색의 하이브리드 설계, RAG 시스템, 그리고 대화형 UX에 대해 알아보았습니다.

이번 글에서는 중소규모 팀이나 스타트업이 실제로 Perplexity 스타일의 서비스를 구축할 수 있는 단계별 로드맵을 제시해보겠습니다.

---

## Step 1. 인프라 구성

시작은 언어 모델과 벡터 데이터베이스 선택입니다. 초기 단계라면 GPT-3.5 Turbo 같은 API 모델을 활용하는 것이 인프라 관리 부담을 줄이고 빠른 출시에 유리합니다. 다만 장기적으로는 비용 증가와 데이터 제어권 이슈가 있을 수 있습니다.

민감 정보를 다루거나 커스텀 학습이 필요하다면 Llama, Falcon 같은 오픈소스 모델을 자체 호스팅하는 것도 방법입니다. 이땐 GPU 인스턴스 프로비저닝과 모델 압축(양자화) 기술 도입이 필수적이겠죠

벡터 DB는 Qdrant Cloud를 많이 추천합니다. 무료로 시작할 수 있고 실시간 업데이트에 최적화된 완전 관리형 서비스라고 하네요. 개발 단계에선 로컬 환경의 Chroma로 시작한 뒤, 프로덕션 전환 시점에 Qdrant로 마이그레이션하는 것도 현명한 선택이 될 수 있습니다.

## Step 2. 검색 백엔드 구현

검색엔진으로는 Elasticsearch를 활용합니다. 도큐먼트의 메타데이터와 본문을 인덱싱하고, 기본적인 BM25 검색을 지원하도록 세팅합니다.

벡터 임베딩은 비용 효율을 고려해 OpenAI의 'text-embedding-ada-002' 모델을 통상적으로 많이 사용합니다. LangChain으로 손쉽게 파이프라인을 구축할 수 있습니다.

향후 다국어 지원이 필요하다면 Cohere의 Multilingual 모델로, 도메인 특화가 목표라면 Sentence-BERT 파인튜닝으로 고도화하는 것도 방법이겠죠

## Step 3. RAG 엔진 통합

이제 Retriever, Reranker, Generator를 결합해 RAG 파이프라인을 완성할 차례입니다. Retriever는 BM25와 벡터 유사도를 결합한 하이브리드 검색으로, Reranker는 'microsoft/COCO-DR'같은 크로스 인코더 기반 재순위화 모델을 활용합니다. Generator는 비용 및 속도 면에서 GPT-3.5 Turbo로 시작하되, 정확도 요구 시 GPT-4로 전환하는 게 현명할 겁니다.

프롬프트 엔지니어링도 잊지 말아야 합니다. 역할과 출력 형식을 지정하는 시스템 프롬프트, 검색 문서를 컨텍스트로 제공하는 샷, 그리고 실제 질문으로 구성된 템플릿을 설계하는 겁니다.

## Step 4. 프론트엔드 UX 설계

사용자 경험 측면에서는 실시간성이 생명입니다. React에서 서버 전송 이벤트(SSE)를 활용해 답변을 점진적으로 스트리밍하는 걸 추천합니다.

로딩 중 스켈레톤 UI로 지연 경험을 최소화하고, 디바운싱으로 불필요한 API 호출을 줄이는 것도 잊지 말아야 합니다. 중간 결과 캐싱으로 반복 질의에 대한 응답 속도를 높일 수도 있을 겁니다.

## Step 5. 운영 및 피드백 루프

시스템이 잘 돌아간다고 끝이 아닙니다. 사용자 피드백을 지속 수집하고 모델 개선에 활용하는 것이 무엇보다 중요합니다.

피드백 로그에서 정답률이 85% 미만인 경우 개선이 필요한 신호로 볼 수 있어요. 500건 이하라면 프롬프트 수정으로 빠르게 대응하고, 5,000건 이상 축적 시는 파인튜닝을 통해 근본적인 성능 향상을 노려볼 만합니다

---

이상의 5단계 로드맵은 약 12주 내에 초기 프로토타입부터 프로덕션 서비스까지 점진적 개발을 가능케 하는 추천 사례입니다. Perplexity의 놀라운 기술들을 오픈소스와 클라우드 서비스를 활용해 구현해보는 거죠.

물론 실전에선 더 많은 난관이 기다리고 있겠지만, 이 가이드가 RAG 시스템으로의 여정에 나침반이 되어주길 바랍니다. 작게 시작해서 빠르게 실험하고 개선해 나가다 보면, 어느새 우리만의 Perplexity를 마주하게 될 겁니다. 제가 코칭하는 회사도 하나씩 하나씩 PoC를 통해 완성도 있는 서비스를 만들어가고 있거든요.

인공지능 기술의 민주화가 가속화되는 지금, 작은 팀의 도전과 혁신이 그 어느 때보다 의미 있는 시대라 생각합니다. Perplexity에서 영감을 얻어 세상에 임팩트를 만들어낼 여러분의 프로젝트를 응원하겠습니다!

<!-- PROMO_BANNER_START -->
<div style="margin-top: 80px; margin-bottom: 20px;">
  <div style="display: flex; align-items: center; justify-content: center; gap: 20px; width: 100%; margin-bottom: 20px;">
    <div style="flex: 1; height: 1px; background-color: #e1e1e1;"></div>
    <span style="font-family: 'Playfair Display', 'Georgia', serif; font-style: italic; font-size: 16px; color: #888; letter-spacing: 0.5px; white-space: nowrap;">Simplifier Choice</span>
    <div style="flex: 1; height: 1px; background-color: #e1e1e1;"></div>
  </div>
<a href="https://www.yes24.com/product/goods/193444437" target="_blank" style="display:flex; border:1px solid #e1e1e1; background-color:#fff; overflow:hidden; text-decoration:none !important; color:inherit; margin:20px 0; height:160px; transition:border-color 0.2s; font-family:'Noto Sans KR', sans-serif; border-radius: 8px;" onmouseover="this.style.borderColor='#111111'" onmouseout="this.style.borderColor='#e1e1e1'">
    <div style="flex:1; padding:25px 30px; display:flex; flex-direction:column; overflow:hidden;">
        <div style="font-size:22px; font-weight:300; color:#333; margin-bottom:12px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; letter-spacing:-0.5px;">ìë¹ì¤ ì´ì©ì ëí´ ìë´ ëë¦½ëë¤. - ìì¤24</div>
        <div style="font-size:14px; font-weight:300; color:#888; line-height:1.6; overflow:hidden; text-overflow:ellipsis; display:-webkit-box; -webkit-line-clamp:2; -webkit-box-orient:vertical; word-break:keep-all;"></div>
        <div style="margin-top:auto; font-size:13px; font-weight:300; color:#999;">www.yes24.com</div>
    </div>
    
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
  <a href="/brunch_web_assets/markdown/136_%EB%82%B4%EA%B0%80%20%EA%B2%AA%EB%8A%94%20%EB%B6%88%ED%8E%B8%ED%95%A8%EC%9D%B4%20%EC%82%AC%EC%97%85%20%EC%95%84%EC%9D%B4%ED%85%9C%EC%9D%B4%EB%8B%A4%2C%20%27%EB%94%94%EC%8A%A4%EC%BD%94%EB%93%9C%27.html" class="cat-nav-item cat-nav-left"><span class="cat-nav-label">'스타트업 인사이트'의 이전글</span><span class="nav-title">내가 겪는 불편함이 사업 아이템이다, '디스코드</span></a>
  <a href="/brunch_web_assets/markdown/143_%EC%97%90%EC%96%B4%EB%A7%A4%ED%8A%B8%EC%97%90%EC%84%9C%20%EC%8B%9C%EC%9E%91%EB%90%9C%2C%20%EC%97%90%EC%96%B4%EB%B9%84%EC%95%A4%EB%B9%84%EC%9D%98%20%EB%AC%B4%EC%9E%90%EB%B3%B8%20%EC%B0%BD%EC%97%85%20%EC%A0%84%EB%9E%B5.html" class="cat-nav-item cat-nav-right"><span class="nav-title">에어매트에서 시작된, 에어비앤비의 무자본 창업 전략</span><span class="cat-nav-label">'스타트업 인사이트'의 다음글</span></a>
</div>
<!-- CATEGORY_NAV_END -->
