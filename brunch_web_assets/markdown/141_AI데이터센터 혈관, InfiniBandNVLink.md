---
layout: default
title: "AI데이터센터 혈관, InfiniBand/NVLink"
category: 'AI의 언어들'
cover_image: 'https://img1.kakaocdn.net/thumb/R1280x0.fgif/?fname=http://t1.daumcdn.net/brunch/service/user/5lk/image/pl-P3SzvsWaA3JVZqRFbPjTpW1U.gif'
date_string: 'May 14. 2025'
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
            window.location.href = '/log.html?cat=' + encodeURIComponent('AI의 언어들');
        });
    }
});
</script>
<!-- CAT_LINK_SCRIPT_END -->

<!-- POST_DATE_START -->
<div style="color: #888; font-size: 14px; margin-bottom: 40px; font-family: 'Noto Sans KR', sans-serif; font-weight: 300;">May 14. 2025</div>
<!-- POST_DATE_END -->

AI 기술이 폭발적으로 성장하면서 데이터센터의 네트워크 인프라도 급격한 변화를 겪고 있습니다. 특히 대규모 AI 모델을 학습시키려면 GPU 간의 초고속 데이터 전송이 필수적인데요. 여기서 두 가지 핵심 기술이 바로 NVLink와 InfiniBand입니다. 이 둘은 서로 다른 영역에서 최적의 성능을 발휘하는 상호보완적인 관계라고 할 수 있어요.

먼저 NVLink는 NVIDIA GPU만을 위한 전용 연결 기술이에요. 마치 GPU들이 바로 옆자리에 앉아 있는 것처럼 직접적이고 빠른 소통이 가능하죠. 최신 H100 GPU에서는 무려 900GB/s의 엄청난 대역폭을 자랑합니다. 게다가 NVLink로 연결된 GPU들은 메모리를 공유할 수 있어서 데이터를 복사하는 낭비도 줄일 수 있어요. 여기에 NVSwitch라는 혁신적인 스위치까지 더해지면서 멀티캐스트나 그래디언트 집계 같은 고급 기능까지 지원하게 됐죠.

![NVLink-types-scaled-1.jpg](//img1.kakaocdn.net/thumb/R1280x0.fjpg/?fname=http://t1.daumcdn.net/brunch/service/user/5lk/image/j_T2fVQEOoGU_nC5C43VWxxUk8g.jpg)

반면에 InfiniBand는 다양한 서버 노드를 하나로 묶어주는 광역 네트워크에요. RDMA라는 기술을 써서 원격 서버의 메모리에 직접 접근할 수 있게 해주죠. 최신 사양으로는 400Gbps, 숫자로는 50GB/s의 대역폭을 제공합니다. NVLink보다는 느리지만 훨씬 먼 거리를 커버할 수 있어요. 무엇보다 개방형 표준이라 여러 제조사의 장비를 조합해서 쓸 수 있다는 게 큰 장점이에요.

![infiniband.jpg](//img1.kakaocdn.net/thumb/R1280x0.fjpg/?fname=http://t1.daumcdn.net/brunch/service/user/5lk/image/bQBNvXwl0vE79u2HZ4CrAIHN4NA.jpg)

실제 AI 데이터센터에서는 이 둘을 적재적소에 배치해서 시너지를 극대화하고 있어요. 대표적인 게 OpenAI의 GPT-3 학습 사례인데요. NVSwitch 아키텍처를 도입한 결과 InfiniBand 대비 51.2배나 빠른 학습 속도를 달성했대요. 엄청난 성과죠? 요즘은 NVLink로 단일 노드의 GPU들을 촘촘히 연결하고, InfiniBand로 스토리지나 다른 노드들과 소통하는 하이브리드 구성이 트렌드라고 합니다.

물론 NVLink는 NVIDIA 전용이다 보니 초기 도입 비용이 만만치 않아요. 하지만 학습 시간을 확 단축시켜 주니 장기적으로는 오히려 이득이 될 수 있죠. InfiniBand는 개방성 덕에 경쟁 입찰로 원가를 절감하면서 유연하게 확장할 수 있고요. 앞으로는 NVLink의 차세대 버전이 1.8TB/s까지 속도를 높일 거라는 소식도 있어요. InfiniBand도 800Gbps 시대를 준비하면서 AI에 특화된 QoS 기능을 강화하고 있고요.

더 흥미로운 건 이 둘의 장점만 뽑아 결합한 융합 기술들이 등장하고 있다는 거예요. 엔비디아의 Spectrum-X 같은 차세대 네트워킹 플랫폼이 대표적인데, NVLink 수준의 성능과 이더넷 수준의 유연성을 동시에 제공한다고 해요. 덕분에 OpenAI의 야심찬 스타게이트 프로젝트에서도 채택되었다고 하네요.

![NVIDIA5-1024x523.png](//img1.kakaocdn.net/thumb/R1280x0.fpng/?fname=http://t1.daumcdn.net/brunch/service/user/5lk/image/auP2pbcG4_PsLUUkELaAYKjK3P4.png)

이처럼 NVLink와 InfiniBand는 AI 데이터센터의 동맥과 정맥 같은 존재예요. 서로 다른 방식으로 데이터의 흐름을 최적화하면서 거대한 AI 모델의 학습을 돕고 있죠. 앞으로는 작업의 특성에 맞게 이 둘을 전략적으로 배치하고 오케스트레이션 하는 것이 데이터센터 설계의 핵심 과제가 될 것 같아요. 더불어 둘의 융합을 통해 더욱 혁신적인 네트워크 기술이 탄생할 것으로 기대됩니다.

여러분은 데이터센터 네트워크에 대해 어떻게 생각하시나요? IT 인프라에 관심이 있으시다면 NVLink와 InfiniBand의 동향을 주의 깊게 살펴보시길 추천드려요. 단순히 배선을 깔아놓는 것 이상으로, 어떤 방식으로 연결하고 제어할 것인지가 AI의 성패를 가를 열쇠가 될 테니까요. 기술의 진화와 함께 데이터센터의 모습도 계속 달라질 텐데, 여러분도 그 변화의 흐름을 놓치지 마시기 바랍니다!

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
  <a href="/brunch_web_assets/markdown/134_AI%20%EB%AA%A8%EB%8D%B8%EC%9D%98%20%ED%95%99%EC%83%9D%EA%B3%BC%20%EC%A1%B8%EC%97%85%EC%83%9D%2C%20%ED%95%99%EC%8A%B5%EA%B3%BC%20%EC%B6%94%EB%A1%A0%EC%9D%98%20%EC%B0%A8%EC%9D%B4%EC%A0%90.html" class="cat-nav-item cat-nav-left"><span class="cat-nav-label">'AI의 언어들'의 이전글</span><span class="nav-title">AI 모델의 학생과 졸업생, 학습과 추론의 차이점</span></a>
  <a href="/brunch_web_assets/markdown/148_AI%EB%AA%A8%EB%8D%B8%20%ED%95%99%EC%8A%B5%EC%97%90%20%EB%82%A0%EA%B0%9C%EB%A5%BC%20%EB%8B%AC%EC%9E%90%20%ED%98%BC%ED%95%A9%20%EC%A0%95%EB%B0%80%EB%8F%84%EC%9D%98%20%EB%A7%88%EB%B2%95.html" class="cat-nav-item cat-nav-right"><span class="nav-title">AI모델 학습에 날개를 달자! 혼합 정밀도의 마법</span><span class="cat-nav-label">'AI의 언어들'의 다음글</span></a>
</div>
<!-- CATEGORY_NAV_END -->
