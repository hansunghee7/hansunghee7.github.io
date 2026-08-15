---
layout: default
title: "ZeRO, 메모리최적화로 AI 비즈니스의 한계를 넓히다"
category: 'AI의 언어들'
cover_image: 'https://img1.kakaocdn.net/thumb/R1280x0.fjpg/?fname=http://t1.daumcdn.net/brunch/service/user/5lk/image/ic-v5rmlHY0e9DeykvxoDtYA7M0.jpg'
date_string: 'Jun 18. 2025'
---

AI 모델이 점점 거대해지면서 기업들은 메모리 한계라는 도전에 직면하고 있습니다. 마이크로소프트 DeepSpeed 팀이 개발한 Zero Redundancy Optimizer(ZeRO)는 메모리 병목 현상을 혁신적으로 해결하여, 더 많은 기업이 대형 AI 모델 개발에 참여할 수 있는 가능성을 넓혔습니다.

![1_AHOACmpEgXaIxzK-UjjTOw.png](//img1.kakaocdn.net/thumb/R1280x0.fpng/?fname=http://t1.daumcdn.net/brunch/service/user/5lk/image/ND3OOHIfUgpQwYSYlv1_0W9zYf8.png)

ZeRO는 단순한 기술 최적화를 넘어 AI 비즈니스 생태계에 중요한 변화를 가져오고 있습니다. 기존에는 GPT-3와 같은 대형 모델을 개발하려면 막대한 인프라 투자가 필요했지만, ZeRO는 이 진입장벽을 낮추고 있습니다. 물론 GPT-4급 초거대 모델은 여전히 상당한 자본과 인프라가 필요하지만, 10억~100억 파라미터급 모델은 더 접근하기 쉬워졌습니다.

비즈니스 관점에서 ZeRO는 GPU 메모리 활용 효율을 크게 높이는 가치를 제공합니다. ZeRO-3 단계에서는 GPU 수에 비례해 메모리 효율이 향상되어, 64개 GPU를 사용한다면 이론적으로 64배의 메모리 절감이 가능합니다. 이는 같은 하드웨어로 더 큰 모델을 학습할 수 있게 하고, 기존 대비 3~5배 이상의 비용 효율성을 제공합니다.

ZeRO의 핵심은 기존 데이터 병렬 학습의 메모리 중복 문제를 해결하는 것입니다. 일반적인 데이터 병렬 방식에서는 각 GPU가 전체 모델을 복제하여 메모리가 낭비되지만, ZeRO는 모델 상태를 여러 GPU에 분산 저장하여 중복을 제거합니다. 이 방식은 세 단계로 진행됩니다. ZeRO-1은 옵티마이저 상태만 분산하여 메모리 사용량을 최대 4배 절감하고, ZeRO-2는 그래디언트까지 분산하여 최대 8배 절감하며, ZeRO-3는 파라미터까지 분산하여 GPU 수에 비례한 메모리 절감을 제공합니다.

마이크로소프트는 ZeRO를 활용해 Turing-NLG(170억 파라미터) 모델을 개발했습니다. 공식 발표에 따르면, 이 모델은 256개 GPU로 효율적인 학습이 가능했으며, 기존 Megatron-LM만 사용했다면 1024개 GPU가 필요했을 것입니다. 이는 ZeRO가 실제 대규모 프로젝트에서 메모리 효율성을 크게 높일 수 있음을 보여주는 사례입니다.

![GRACE-2023-BlogHeroFeature-1400x788-1.png](//img1.kakaocdn.net/thumb/R1280x0.fpng/?fname=http://t1.daumcdn.net/brunch/service/user/5lk/image/fbHSgo9Va4EzJNnpEvlRv3Y7mbU.png)

ZeRO 도입을 위해서는 단계적 접근이 필요합니다.

1. 먼저 현재 AI 모델의 메모리 요구사항을 분석하고 목표 모델 크기를 정의한 후 비용-효율성을 분석합니다. 2. 다음으로 PyTorch 기반 워크플로우에 DeepSpeed 라이브러리를 통합하고 ZeRO-1부터 시작하여 필요에 따라 확장합니다.

3. 마지막으로 학습 속도와 메모리 사용량을 지속적으로 모니터링하고 필요에 따라 하이브리드 접근법을 채택합니다.

ZeRO는 AI 모델 개발의 진입장벽을 낮추고 있으며, 더 많은 기업이 10억~100억 파라미터급 모델에 도전할 수 있게 되었습니다. 다만, 수천억~수조 파라미터 모델은 여전히 막대한 인프라와 기술력이 필요하므로, "누구나 초거대 모델 개발이 가능하다"고 보기는 어렵습니다.

결론적으로, ZeRO는 AI 모델 학습의 메모리 효율성을 크게 향상시켜 대형 모델 개발의 진입장벽을 낮추는 중요한 기술입니다. 특히 중견기업과 연구 기관에게 ZeRO는 제한된 리소스로도 더 크고 강력한 AI 모델을 개발할 수 있는 가능성을 열어주는 의미 있는 발전입니다.https://www.yes24.com/product/goods/193444437
<!-- PROMO_BANNER_START -->
<div class="promo-banner" style="margin-top: 60px; padding: 35px 20px; background: #111111; border-radius: 12px; font-family: 'Noto Sans KR', sans-serif;">
    <h4 style="color: #ffffff; margin-top: 0; margin-bottom: 5px; font-weight: 500; font-size: 18px; text-align: center;">🚀 Simplifier's Pick</h4>
    <p style="color: #aaaaaa; font-size: 14px; margin-bottom: 25px; font-weight: 300; text-align: center;">인사이트를 더 깊게 만나보세요</p>
<!-- OG_CARD_START -->
<a href="https://www.yes24.com/product/goods/193444437" target="_blank" style="display:flex; border:1px solid #e1e1e1; background-color:#fff; overflow:hidden; text-decoration:none !important; color:inherit; margin:20px 0; height:160px; transition:border-color 0.2s; font-family:'Noto Sans KR', sans-serif;" onmouseover="this.style.borderColor='#111111'" onmouseout="this.style.borderColor='#e1e1e1'">
    <div style="flex:1; padding:25px 30px; display:flex; flex-direction:column; overflow:hidden;">
        <div style="font-size:22px; font-weight:300; color:#333; margin-bottom:12px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; letter-spacing:-0.5px;">UX의 언어들 | 한성희 | 파지트 - 예스24</div>
        <div style="font-size:14px; font-weight:300; color:#888; line-height:1.6; overflow:hidden; text-overflow:ellipsis; display:-webkit-box; -webkit-line-clamp:2; -webkit-box-orient:vertical; word-break:keep-all;">일상 속 UX의 발견UX 세계를 향한 친절한 안내서 『UX의 언어들』은 일상 속에 스며든 UX를 UX 디자이너의 시선으로 풀어내며, 우리가 이를 어떻게 경험하고 소비하는지 넷플릭스, 카카오 등 친숙한 사례를 통해 UX의 세계로 안내한다.UX는 제품, 서비스, ...</div>
        <div style="margin-top:auto; font-size:13px; font-weight:300; color:#999;">www.yes24.com</div>
    </div>
    <div style="width:25%; min-width:160px; background:url('https://image.yes24.com/goods/193444437/xl') center/cover no-repeat; border-left:1px solid #e1e1e1;"></div>
</a>
<!-- OG_CARD_END --><!-- OG_CARD_START -->
<a href="https://trevar.ink/Vmammm" target="_blank" style="display:flex; border:1px solid #e1e1e1; background-color:#fff; overflow:hidden; text-decoration:none !important; color:inherit; margin:20px 0; height:160px; transition:border-color 0.2s; font-family:'Noto Sans KR', sans-serif;" onmouseover="this.style.borderColor='#111111'" onmouseout="this.style.borderColor='#e1e1e1'">
    <div style="flex:1; padding:25px 30px; display:flex; flex-direction:column; overflow:hidden;">
        <div style="font-size:22px; font-weight:300; color:#333; margin-bottom:12px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; letter-spacing:-0.5px;">기획자들은 어떤 사고방식과 역량을 갖춰야 할까요?  | 독서모임 | 기획자들의 비밀 서재 | 트레바리</div>
        <div style="font-size:14px; font-weight:300; color:#888; line-height:1.6; overflow:hidden; text-overflow:ellipsis; display:-webkit-box; -webkit-line-clamp:2; -webkit-box-orient:vertical; word-break:keep-all;">진짜 기획을 '잘' 한다는 것 "프로덕트 매니저부터 요기요 CPO, 빗썸 CCO, 현재 Simplifier를 창업하기까지 제 일은 늘 문제를 해결하는 것에서부터 시작되었습니다.</div>
        <div style="margin-top:auto; font-size:13px; font-weight:300; color:#999;">trevar.ink</div>
    </div>
    <div style="width:25%; min-width:160px; background:url('https://trevar.ink/api/og?template=leader-club&image=https%3A%2F%2Fr29hmvkwcd.execute-api.ap-northeast-2.amazonaws.com%2Fimages%2Fbooks%2F9788947547567&title=%EA%B8%B0%ED%9A%8D%EC%9E%90%EB%93%A4%EC%9D%98+%EB%B9%84%EB%B0%80+%EC%84%9C%EC%9E%AC&leaderName=%ED%95%9C%EC%84%B1%ED%9D%AC&bg=D1D0CB&fg=000000') center/cover no-repeat; border-left:1px solid #e1e1e1;"></div>
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
  <a href="/brunch_web_assets/markdown/096_%EB%B9%84%EC%A6%88%EB%8B%88%EC%8A%A4%20%EA%B2%BD%EC%9F%81%EB%A0%A5%EC%97%90%20%EC%A0%80%EC%A0%84%EB%A0%A5%20NPU%EA%B0%80%20%EC%A4%91%EC%9A%94%ED%95%9C%20%EC%9D%B4%EC%9C%A0.html" class="cat-nav-item cat-nav-left"><span class="cat-nav-label">'AI의 언어들'의 이전글</span><span class="nav-title">비즈니스 경쟁력에 저전력 NPU가 중요한 이유</span></a>
  <a href="/brunch_web_assets/markdown/111_AI%ED%95%99%EC%8A%B5%20%ED%81%B4%EB%9D%BC%EC%9A%B0%EB%93%9C%20%EC%82%BC%EA%B5%AD%EC%A7%80%20AWSGoogleAzure.html" class="cat-nav-item cat-nav-right"><span class="nav-title">AI학습 클라우드 삼국지 AWS/Google/Azure</span><span class="cat-nav-label">'AI의 언어들'의 다음글</span></a>
</div>
<!-- CATEGORY_NAV_END -->