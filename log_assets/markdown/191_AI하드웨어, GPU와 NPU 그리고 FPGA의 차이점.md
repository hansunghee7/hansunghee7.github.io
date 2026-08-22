---
layout: default
title: "AI하드웨어, GPU와 NPU 그리고 FPGA의 차이점"
category: 'AI의 언어들'
cover_image: 'https://img1.kakaocdn.net/thumb/R1280x0.fjpg/?fname=http://t1.daumcdn.net/brunch/service/user/5lk/image/URr71IKtgoT9AtijOL_yceq1l60.jpg'
date_string: 'Mar 26. 2025'
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

요즘 AI 하드웨어 시장을 보면 GPU, NPU, FPGA가 치열하게 경쟁하고 있습니다. 어떤 가속기를 쓰느냐에 따라 AI 모델의 성능이 크게 달라지기 때문이라고 합니다. 학습(Training)용과 추론(Inference)용도 하드웨어 종류에 따라 성능이 크게 달라진다고 합니다. 이번 글에서는 AI 하드웨어가속기들의 차이점과 용도에 대해 쉽게 정리해보려고 합니다.

## 학습과 추론처리의 차이

일단 AI 모델이 현실 세계에서 동작하려면 학습과 추론이라는 두 단계를 거쳐야 합니다. 학습은 대량의 데이터를 모델에 밀어 넣어서 모델의 파라미터를 조정하는 과정이죠. 컴퓨터 비전이나 자연어 처리 같은 복잡한 태스크는 파라미터가 수십억 개에 달하기 때문에 어마어마한 연산량이 필요합니다. 그래서 GPU나 구글 TPU 같은 고성능 가속기를 동원해서 병렬로 처리하는 거죠.

![ai_difference_between_deep_learning_training_inference.jpg](//img1.kakaocdn.net/thumb/R1280x0.fjpg/?fname=http://t1.daumcdn.net/brunch/service/user/5lk/image/BJdzPnC7MCUKoAopQtIlii3ABjs.jpg)

반면에 추론은 이미 학습된 모델을 가지고 새로운 데이터에 대한 예측을 내놓는 과정입니다. 추론할 때는 실시간성이 중요하기 때문에 저전력으로 빠르게 연산할 수 있는 NPU나 FPGA가 각광받고 있습니다. 스마트폰 AI나 자율주행처럼 현장에서 즉각 판단을 내려야 하는 경우에는 더더욱 그렇죠.

## GPU, NPU, FPGA의 특징

그럼 GPU, NPU, FPGA는 각각 어떤 특징이 있을까요? 먼저 GPU는 그래픽 처리용으로 개발된 범용 프로세서입니다. 수천 개의 코어를 병렬로 돌릴 수 있어서 복잡한 AI 모델도 쉽게 학습시킬 수 있습니다. NVIDIA의 CUDA나 AMD의 ROCm 같은 소프트웨어 플랫폼도 잘 갖춰져 있고요. 다만 전력 소모가 크고 발열이 심해서 대규모 데이터센터에 적합합니다.

![cpu+gpu-01.png](//img1.kakaocdn.net/thumb/R1280x0.fpng/?fname=http://t1.daumcdn.net/brunch/service/user/5lk/image/TFUwfRU6BI_EBE_xgTL4jyQ1Dgk.png)

NPU는 AI 전용으로 설계된 프로세서입니다. 딥러닝에서 많이 쓰이는 행렬 연산을 아주 빠르고 효율적으로 처리하도록 최적화되어 있죠. GPU보다 전력 효율이 훨씬 높아서 모바일 기기나 IoT 환경에 적합합니다. 애플이 아이폰에 탑재한 뉴럴 엔진이나 구글 TPU 같은 게 대표적이죠. 다만 GPU처럼 만능은 아닙니다. AI 연산에만 특화되어 있다 보니 활용 폭이 좁기 때문입니다.

![71bb10eb8641e.png](//img1.kakaocdn.net/thumb/R1280x0.fpng/?fname=http://t1.daumcdn.net/brunch/service/user/5lk/image/FQ0wEuGDG37Pp5mEJk_1boR3X0k.png)

FPGA는 현장에서 프로그래밍 가능한 반도체입니다. 어떻게 설계하느냐에 따라 다양한 용도로 쓸 수 있죠. 특정 AI 태스크에 맞춰 최적화하기에 좋습니다. 고주파수 트레이딩이나 실시간 의료 영상 분석 같은 분야에서 효과적이에요. 전력 소모도 GPU보다 훨씬 적고요. 그런데 로직 설계가 어렵고 개발 비용이 높은 게 단점입니다. ASIC만큼 전문적이지도 않고요.

![fpga-implementaion-flow-diagram:1920-1080?wid=864&hei=486&fmt=webp-alpha](//img1.kakaocdn.net/thumb/R1280x0.fwebp/?fname=http://t1.daumcdn.net/brunch/service/user/5lk/image/H0FXpHp93_bqRw48ZkXzMh1Ujbc)

## AI 하드웨어 선택과 미래

결국 AI 하드웨어는 쓰임새에 따라 선택하는 것이 중요합니다. 대규모 학습이 필요하다면 GPU나 구글 TPU 같은 고성능 가속기를 써야겠죠. 저전력으로 실시간 추론을 해야 한다면 NPU나 FPGA가 낫고요.

![img1.jpg](//img1.kakaocdn.net/thumb/R1280x0.fjpg/?fname=http://t1.daumcdn.net/brunch/service/user/5lk/image/FYZl7UYQAlrPGtkbHrDDPBFWl3Y.jpg)

앞으로 AI 모델은 계속 진화할 겁니다. 하드웨어와 소프트웨어가 긴밀하게 연계되어야만 최고의 성능을 끌어낼 수 있기 때문이죠. NVIDIA나 구글, 애플 같은 선두 기업들이 어떤 AI 칩을 내놓을지 눈여겨볼 일입니다. 최적의 하드웨어로 무장해야 AI 경쟁에서 살아남을 수 있으니까요. 우리 모두 관심 있게 지켜보면 좋겠습니다.

**AI시대에 알아야 할 UX의 언어는?**

<!-- CATEGORY_NAV_START -->
<div class="category-nav-wrap">
  <a href="/log_assets/markdown/184_AI%20%EC%84%B1%EB%8A%A5%EC%9D%98%20%EC%97%B4%EC%87%A0%2C%20HBM%EC%9D%80%20%EB%AC%B4%EC%97%87%EC%9D%BC%EA%B9%8C.html" class="cat-nav-item cat-nav-left"><span class="cat-nav-label">'AI의 언어들'의 이전글</span><span class="nav-title">AI 성능의 열쇠, HBM은 무엇일까?</span></a>
  <a href="/log_assets/markdown/199_AI%EC%8B%9C%EB%8C%80%20%EC%8A%88%ED%8D%BC%EC%BB%B4%ED%93%A8%ED%84%B0%EA%B0%80%20%ED%95%84%EC%9A%94%ED%95%9C%20%EC%9D%B4%EC%9C%A0.html" class="cat-nav-item cat-nav-right"><span class="nav-title">AI시대 슈퍼컴퓨터가 필요한 이유</span><span class="cat-nav-label">'AI의 언어들'의 다음글</span></a>
</div>
<!-- CATEGORY_NAV_END -->
