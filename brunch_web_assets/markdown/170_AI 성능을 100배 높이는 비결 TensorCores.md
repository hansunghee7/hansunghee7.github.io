---
layout: default
title: "AI 성능을 100배 높이는 비결 TensorCores"
category: 'AI의 언어들'
cover_image: 'https://img1.kakaocdn.net/thumb/R1280x0.fjpg/?fname=http://t1.daumcdn.net/brunch/service/user/5lk/image/edLooyRSoImKgHowBhppDrmveNU.jpg'
date_string: 'Apr 16. 2025'
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
            window.location.href = '/log.html?cat=' + encodeURIComponent('AI의 언어들');
        });
    }
});
</script>
<!-- CAT_LINK_SCRIPT_END -->

AI 기술이 날로 발전하면서 딥러닝 모델의 규모도 엄청나게 커지고 있습니다. 수천억 개의 파라미터를 학습시키려면 어마어마한 연산량이 필요한데요. 그 중심에는 바로 '행렬 곱셈(Matrix Multiplication)'이 자리잡고 있습니다. 행렬 곱셈이 AI 성능을 좌우한다고 해도 과언이 아닐 정도로 중요한 역할을 하고 있죠.

![maxresdefault.jpg](//img1.kakaocdn.net/thumb/R1280x0.fjpg/?fname=http://t1.daumcdn.net/brunch/service/user/5lk/image/X3qSKucWLT6XWy99gHoTv-SnRLM.jpg)

그런데 최근 들어 행렬 곱셈의 새로운 히어로가 등장했습니다. 바로 NVIDIA의 'Tensor Cores'인데요. 기존 GPU가 단일 정밀도 연산에 특화된 것과 달리, Tensor Cores는 혼합 정밀도를 지원하면서 행렬 곱셈 속도를 비약적으로 끌어올렸습니다. 단일 클럭 주기 안에 FP16 4x4 행렬 두 개를 곱하고 FP32 행렬에 누적하는 방식으로 말이죠.

이게 왜 대단하냐고요? Tensor Cores는 CUDA 코어 대비 무려 128배나 빠른 처리량(Throughput)을 자랑합니다. 특히 CNN이나 RNN에서 많이 쓰이는 GEMM(General Matrix Multiplication) 연산을 가속화해서 학습 시간을 크게 단축시키거든요. 게다가 불필요한 연산은 아예 건너뛰는 희소 연산(Sparse Operation)까지 지원해서 에너지 효율까지 높였습니다.

![Nvidias-Tensor-Cores.jpg](//img1.kakaocdn.net/thumb/R1280x0.fjpg/?fname=http://t1.daumcdn.net/brunch/service/user/5lk/image/zXtpA-eKQNynzzNlF4Z5gONlCNc.jpg)

물론 CUDA 코어도 여전히 중요합니다. 정확도가 생명인 모델 검증 같은 작업에서는 싱글 프리시전의 CUDA 코어가 빛을 발하니까요. 하지만 행렬 곱셈이 지배적인 대규모 AI 모델에서는 Tensor Cores의 위력이 발휘될 수밖에 없습니다. 실제로 NVIDIA A100 GPU는 Tensor Cores 덕분에 동일 전력 대비 10배 높은 성능을 보여준다고 해요.

Tensor Cores가 업계 스탠다드로 자리 잡으면서 AI 프레임워크들도 적극적으로 지원에 나서고 있습니다. CUDA 딥러닝 라이브러리인 cuDNN은 Convolution 연산을 GEMM으로 변환해서 Tensor Cores를 활용하고 있고요. TensorRT는 연산 그래프를 최적화하고 레이어를 병합해서 지연 시간을 최소화합니다. 덕분에 우리는 더 빠르고 효율적인 AI 모델을 만날 수 있게 된 거죠.

행렬 곱셈 가속화의 혜택은 비단 서버용 GPU뿐만 아니라 모바일 기기에서도 체감할 수 있습니다. 예를 들어 삼성 엑시노스 칩에 내장된 NPU(Neural Processing Unit)는 Tensor Cores와 유사한 원리로 BERT 추론 속도를 2배 끌어올렸다고 해요. 이제 AI 어시스턴트의 응답 속도가 50밀리초 미만으로 줄어든 데에는 행렬 곱셈 최적화 기술이 한 몫 했다고 볼 수 있겠네요.

![image.png](//img1.kakaocdn.net/thumb/R1280x0.fpng/?fname=http://t1.daumcdn.net/brunch/service/user/5lk/image/ScEL0j0wr889Up6zV5-9bQ7cyc4.png)

앞으로도 AI 기술은 계속해서 발전할 것이고, 그 중심에는 언제나 행렬 곱셈이 있을 것입니다. Transformer나 GPT 같은 대형 모델들이 GPU와 행렬 곱셈 병렬화 기술 없이는 상상조차 못 했을 테니까요. 물론 도전 과제도 만만치 않습니다. 파라미터 수가 늘어날수록 연산량도 기하급수적으로 증가하고, 고성능 연산을 뒷받침할 HBM 같은 고대역 메모리 수요도 폭발할 테니까요.

하지만 걱정은 접어두죠. Tensor Cores를 필두로 한 행렬 곱셈 가속화 기술이 한발 앞서 우리를 인도해 줄 테니까요. 앞으로 NVIDIA, AMD, 인텔, 구글 같은 대형 테크 기업들이 내놓을 새로운 AI 칩들의 행렬 곱셈 성능이 어떻게 진화할지 지켜보는 것만으로도 흥분되지 않나요? 우리가 상상하는 것보다 더 놀라운 미래가 펼쳐질 지도 모르겠네요.

<!-- PROMO_BANNER_START -->
<div style="margin-top: 80px; margin-bottom: 20px;">
  <div style="display: flex; align-items: center; justify-content: center; gap: 20px; width: 100%; margin-bottom: 20px;">
    <div style="flex: 1; height: 1px; background-color: rgba(245,243,238,0.1);"></div>
    <span style="font-family: 'Boska', serif; font-style: italic; font-size: 16px; color: #8f8b82; letter-spacing: 0.5px; white-space: nowrap;">Simplifier Choice</span>
    <div style="flex: 1; height: 1px; background-color: rgba(245,243,238,0.1);"></div>
  </div>
<a href="https://www.yes24.com/product/goods/193444437" target="_blank" style="display:flex; border:1px solid rgba(245,243,238,0.08); background-color:#111; overflow:hidden; text-decoration:none !important; color:#f5f3ee; margin:20px 0; height:160px; transition:border-color 0.2s; font-family:'Pretendard Variable', sans-serif; border-radius: 8px;" onmouseover="this.style.borderColor='rgba(245,243,238,0.4)'" onmouseout="this.style.borderColor='rgba(245,243,238,0.08)'">
    <div style="flex:1; padding:25px 30px; display:flex; flex-direction:column; overflow:hidden;">
        <div style="font-size:20px; font-weight:500; color:#f5f3ee; margin-bottom:12px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; letter-spacing:-0.5px;">UX의 언어들 | 한성희 | 파지트 - 예스24</div>
        <div style="font-size:14px; font-weight:300; color:#8f8b82; line-height:1.6; overflow:hidden; text-overflow:ellipsis; display:-webkit-box; -webkit-line-clamp:2; -webkit-box-orient:vertical; word-break:keep-all;">일상 속 UX의 발견UX 세계를 향한 친절한 안내서 『UX의 언어들』은 일상 속에 스며든 UX를 UX 디자이너의 시선으로 풀어내며, 우리가 이를 어떻게 경험하고 소비하는지 넷플릭스, 카카오 등 친숙한 사례를 통해 UX의 세계로 안내한다.UX는 제품, 서비스, ...</div>
        <div style="margin-top:auto; font-size:13px; font-weight:300; color:#736f67;">www.yes24.com</div>
    </div>
    <div style="width:25%; min-width:160px; background:url('https://image.yes24.com/goods/193444437/xl') center/cover no-repeat; border-left:1px solid #e1e1e1;"></div>
</a>
</div>
<!-- PROMO_BANNER_END -->


<!-- CATEGORY_NAV_START -->
<style>
.category-nav-wrap { margin-top: 60px; padding: 25px 40px; border-top: 1px solid rgba(245,243,238,0.1); display: flex; justify-content: space-between; align-items: center; font-family: 'Pretendard Variable', sans-serif; font-size: 14px; gap: 30px; width: 100vw; position: relative; left: 50%; transform: translateX(-50%); box-sizing: border-box; }
.cat-nav-item { display: flex; align-items: center; gap: 10px; text-decoration: none !important; color: #8f8b82; transition: color 0.2s; max-width: 45%; }
.cat-nav-item:hover { color: #f5f3ee; }
.cat-nav-item:hover .nav-title { color: #f5f3ee; text-decoration: underline; }
.cat-nav-label { font-size: 13px; color: #736f67; white-space: nowrap; font-weight: 300; }
.nav-title { font-weight: 400; color: #c9c8c2; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.cat-nav-right { margin-left: auto; justify-content: flex-end; text-align: right; }
</style>
<div class="category-nav-wrap">
  <a href="/brunch_web_assets/markdown/162_AI%20%EC%84%B1%EB%8A%A5%EC%9D%98%20%EC%88%A8%EC%9D%80%20%EC%98%81%EC%9B%85%2C%20FP16%2C%20BF16%2C%20FP8.html" class="cat-nav-item cat-nav-left"><span class="cat-nav-label">'AI의 언어들'의 이전글</span><span class="nav-title">AI 성능의 숨은 영웅, FP16, BF16, FP8</span></a>
  <a href="/brunch_web_assets/markdown/177_AI%20%EC%B9%A9%20%EC%84%B1%EB%8A%A5%EC%9D%98%20%ED%95%B5%EC%8B%AC%2C%20FLOPS%EC%99%80%20TOPS%20%EA%B7%B8%EB%A6%AC%EA%B3%A0.html" class="cat-nav-item cat-nav-right"><span class="nav-title">AI 칩 성능의 핵심, FLOPS와 TOPS 그리고..</span><span class="cat-nav-label">'AI의 언어들'의 다음글</span></a>
</div>
<!-- CATEGORY_NAV_END -->
