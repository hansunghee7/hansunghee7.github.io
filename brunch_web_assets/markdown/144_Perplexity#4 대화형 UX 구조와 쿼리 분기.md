---
layout: default
title: "Perplexity#4 대화형 UX 구조와 쿼리 분기"
category: '스타트업 인사이트'
cover_image: 'https://img1.kakaocdn.net/thumb/R1280x0.fpng/?fname=http://t1.daumcdn.net/brunch/service/user/5lk/image/7laS35X23ORe1nbycFX2aOa0W2k.png'
date_string: 'May 11. 2025'
---

퍼플렉시티의 놀라운 대화형 AI 경험 뒤에는 정교한 UX 설계와 쿼리 분기 전략이 자리 잡고 있습니다. 단순한 질의-응답을 넘어 마치 인간과 대화를 나누는 듯한 자연스러운 상호작용을 구현하기 위한 일련의 기술들을 살펴보겠습니다.

### 대화 세션 관리: 기억 vs Stateless 구조

먼저 대화 이력을 어떻게 관리할 것인가의 문제입니다. 크게 기억(Stateful) 구조와 Stateless 구조로 나눌 수 있는데요. 퍼플렉시티는 기본적으로 기억 구조를 채택하고 있습니다. 사용자와의 대화 내용을 세션 단위로 저장해 이전 맥락을 파악하고, 연속적인 질의에 응답할 수 있게 하는 거죠. 이는 개인화된 맞춤형 경험과 대화 흐름 유지에 최적화된 방식입니다. 반면 개인정보 보호나 단순 질의응답에 특화된 시나리오라면 Stateless 구조를 택할 수도 있겠죠. 각 입력을 독립적 이벤트로 처리하는 방식인데, 구현은 단순하지만 맥락을 반영하기 어렵다는 단점이 있습니다.

![image.png](//img1.kakaocdn.net/thumb/R1280x0.fpng/?fname=http://t1.daumcdn.net/brunch/service/user/5lk/image/IZTKLproT_F5GRZmy9J0pfY65X8.png)

### 쿼리 리라이팅과 요약의 적용 시점

사용자의 자연어 입력을 그대로 언어 모델에 던지기엔 품질 저하의 위험이 있습니다. 그래서 퍼플렉시티는 두 가지 전처리 과정을 거칩니다. 하나는 쿼리 리라이팅으로, 사용자 입력을 언어 모델이 이해하기 좋은 형태로 변환하는 작업입니다. 입력 직후, 검색이나 언어 모델에 전달하기 전에 수행되죠. 또 하나는 쿼리 요약인데요. 길고 복잡해진 대화 흐름에서, 그간의 맥락을 압축해 언어 모델에 함께 제공하는 역할을 합니다. 대화 중간중간, 언어 모델 호출 직전에 적용하면 컨텍스트를 효율적으로 전달할 수 있습니다.

![F8-iFxfaEAA77Nc.jpg](//img1.kakaocdn.net/thumb/R1280x0.fjpg/?fname=http://t1.daumcdn.net/brunch/service/user/5lk/image/533ST6--Wi1V1K742kXk9O6Uf-o.jpg)

### 답변 UI 설계의 핵심 요소

언어 모델의 출력을 가공 없이 내보내는 것은 좋은 사용자 경험이 아닙니다. 퍼플렉시티는 답변의 구조와 디자인에도 많은 공을 들입니다. 가장 중요한 건 원출처 표시입니다. 응답 내 각 정보 블록마다 출처(URL, 문서명 등)를 명시해 신뢰도와 투명성을 확보하는 거죠. 사용자는 원본을 직접 확인할 수 있게 됩니다. 두 번째로 응답 내 하이라이트 구조도 눈여겨볼 만합니다. 핵심 문장, 키워드, 인용구 등을 시각적으로 강조해 계층화하는 것인데요. 먼저 중요 정보를 파악하고 싶은 사용자의 니즈를 반영한 디자인이라 할 수 있겠네요. 마지막으로 Follow-up Suggestion도 퍼플렉시티만의 특징입니다. 답변을 제시한 후, 대화를 이어나갈 만한 관련 질문이나 탐색 옵션을 함께 제안하는 거죠. 언어 모델이 이런 연관 질의를 자동으로 생성해 제시함으로써, 대화의 흐름을 자연스럽게 이어갈 수 있게 돕습니다.

![perplexity_sponsored_questions.png](//img1.kakaocdn.net/thumb/R1280x0.fpng/?fname=http://t1.daumcdn.net/brunch/service/user/5lk/image/DnBQFtxcTpGs6a2tS27pUx9ZenA.png)

### 실시간성을 위한 응답 스트리밍

웹 프론트엔드와 언어 모델 API를 연결할 때, 단순히 응답 전체를 한 번에 받아오는 것은 사용자 경험 면에서 좋지 않습니다. 퍼플렉시티는 실시간 응답 스트리밍 기법을 적용해 이를 개선합니다. 보통 서버 전송 이벤트(SSE)나 웹소켓을 활용해 언어 모델의 출력을 토큰 또는 문장 단위로 나눠 전송하는데요. 프론트엔드는 이를 받아 점진적으로 UI에 반영하게 됩니다. 스켈레톤 UI나 로딩 인디케이터 등을 활용하면 자연스러운 응답 생성 과정을 연출할 수 있죠. 사용자 입장에선 마치 AI가 실시간으로 타이핑하며 대화에 응답하는 느낌을 받게 됩니다. 단순히 완성된 응답이 툭 떨어지는 것과는 사뭇 다른 경험이라고 볼 수 있겠네요.

![image.png](//img1.kakaocdn.net/thumb/R1280x0.fpng/?fname=http://t1.daumcdn.net/brunch/service/user/5lk/image/374LlWSqZG57D2uVZa4c4M_NA8I.png)

퍼플렉시티의 대화형 UX와 쿼리 분기 로직은 사용자와 AI의 상호작용을 한 차원 높이는 역할을 합니다. 기억 구조로 맥락을 유지하고, 쿼리 리라이팅과 요약으로 언어 모델 입력을 최적화하며, 구조화되고 투명한 응답 디자인으로 신뢰를 확보하는 거죠. 여기에 실시간 스트리밍으로 자연스러운 대화 흐름까지 구현해낸다면, 이는 단순한 챗봇을 넘어 진정한 의미의 AI 어시스턴트에 가까워질 것입니다.

물론 이런 UX를 완성하기까지는 수많은 고민과 실험이 필요할 거예요. 무엇보다 사용자의 니즈와 행동 패턴에 대한 깊이 있는 이해가 바탕이 돼야 하고요. 언어 모델의 특성에 맞는 입출력 처리 전략, 시각 디자인과 브랜드 아이덴티티와의 조화 등도 세심하게 설계해야 할 부분이겠죠. 하지만 퍼플렉시티의 사례는 분명 이 분야의 이정표가 될 것입니다. 단순 기능을 넘어 사용자의 마음을 사로잡는 AI 경험. 퍼플렉시티가 추구하는 이 가치가 자연어 AI 시장의 진화를 이끌어갈 것으로 기대합니다.

여러분도 이 과정에 동참해 보시는 건 어떨까요? 기술과 사용자 경험의 접점에서, 우리가 상상하는 미래의 AI가 하나둘 현실로 다가올 테니까요.https://www.yes24.com/product/goods/193444437
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
.category-nav-wrap { margin-top: 80px; padding: 25px 40px; border-top: 1px solid #e1e1e1; display: flex; justify-content: space-between; align-items: center; font-family: 'Noto Sans KR', sans-serif; font-size: 14px; color: #888; gap: 30px; width: 100vw; position: relative; left: 50%; transform: translateX(-50%); box-sizing: border-box; }
.cat-nav-item { display: flex; align-items: center; gap: 10px; text-decoration: none !important; color: #666; transition: color 0.2s; max-width: 45%; }
.cat-nav-item:hover { color: #111; }
.cat-nav-item:hover .nav-title { color: #111; text-decoration: underline; }
.cat-nav-label { font-size: 13px; color: #999; white-space: nowrap; font-weight: 300; }
.nav-title { font-weight: 400; color: #333; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.cat-nav-right { margin-left: auto; justify-content: flex-end; text-align: right; }
</style>
<div class="category-nav-wrap">
  <a href="/brunch_web_assets/markdown/143_%EC%97%90%EC%96%B4%EB%A7%A4%ED%8A%B8%EC%97%90%EC%84%9C%20%EC%8B%9C%EC%9E%91%EB%90%9C%2C%20%EC%97%90%EC%96%B4%EB%B9%84%EC%95%A4%EB%B9%84%EC%9D%98%20%EB%AC%B4%EC%9E%90%EB%B3%B8%20%EC%B0%BD%EC%97%85%20%EC%A0%84%EB%9E%B5.html" class="cat-nav-item cat-nav-left"><span class="cat-nav-label">'스타트업 인사이트'의 이전글</span><span class="nav-title">에어매트에서 시작된, 에어비앤비의 무자본 창업 전략</span></a>
  <a href="/brunch_web_assets/markdown/150_Slack%EC%9D%98%20%EC%9C%A0%EB%A3%8C%EC%A0%84%ED%99%98%EC%9D%98%20%EB%A7%A4%EC%A7%81%20%EB%AA%A8%EB%A8%BC%ED%8A%B8.html" class="cat-nav-item cat-nav-right"><span class="nav-title">Slack의 유료전환의 "매직 모먼트</span><span class="cat-nav-label">'스타트업 인사이트'의 다음글</span></a>
</div>
<!-- CATEGORY_NAV_END -->