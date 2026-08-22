---
layout: default
title: "AI 성능의 열쇠, HBM은 무엇일까?"
category: 'AI의 언어들'
cover_image: 'https://img1.kakaocdn.net/thumb/R1280x0.fjpg/?fname=http://t1.daumcdn.net/brunch/service/user/5lk/image/JObnKEBRNb52fha0MD4UaBc-iME.jpg'
date_string: 'Apr 2. 2025'
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

AI 기술이 급속도로 발전하면서 방대한 데이터를 빠르게 처리할 수 있는 고성능 메모리의 중요성이 부각되고 있습니다. 특히 HBM(High Bandwidth Memory)은 기존 DRAM의 한계를 뛰어넘는 혁신적인 기술로 주목받고 있죠. 그런데 HBM이 정확히 뭐길래 AI 학습에 그렇게 필수적일까요? 오늘은 HBM의 탄생 배경부터 최신 동향, 그리고 AI 학습에서의 역할까지 살펴보도록 하겠습니다.

HBM은 사실 갑자기 튀어나온 신기술이 아닙니다. 2000년대 후반 AMD가 고성능 GPU용 메모리 솔루션을 고민하면서 HBM 개발에 착수했고, 비슷한 시기 SK하이닉스도 TSV(Through Silicon Via) 기술에 주목하며 HBM 연구에 뛰어들었죠. 두 회사의 협력으로 2013년 HBM이 JEDEC 표준으로 제정되었고, 2015년 AMD의 Fiji GPU와 함께 상용화되기 시작했습니다.

![Qi9AcEvkBjZJVOE3vTe102QKOj8dDSQS1iH_Nj5M5wwQqYK58ITAzpK2lkOhpajcVBVdwokM636jh0QGozmOkQ.webp](//img1.kakaocdn.net/thumb/R1280x0.fwebp/?fname=http://t1.daumcdn.net/brunch/service/user/5lk/image/VmdAoBcNuFXNpSKgF4HDf6IqfM0.webp)

그런데 왜 하필 AI 학습 얘기가 나올까요? 사실 HBM의 진가는 딥러닝이 대세로 떠오르면서 제대로 발휘되기 시작했습니다. 수천만 개의 파라미터를 다루는 거대한 신경망을 학습시키려면 어마어마한 양의 데이터를 읽고 써야 하거든요. 기존 그래픽카드에 쓰던 GDDR(Graphics Double Data Rate) 메모리로는 속도와 전력 효율 면에서 한계가 뚜렷했죠. 반면 HBM은 초당 1.2TB까지 데이터를 실어 나를 수 있는 엄청난 대역폭을 자랑합니다. 게다가 3D 적층 구조 덕분에 데이터 전송 경로가 짧아져 지연 시간도 크게 줄일 수 있습니다.

또 하나 HBM의 장점은 GPU와 아주 가까이 붙어 있다는 겁니다. 데이터가 연산 장치 코앞에 있으니 입출력 병목 현상이 확 줄어들죠. 여기에 공간 효율성까지 뛰어나 고성능 AI 가속기를 설계하는 데 안성맞춤입니다. 실제로 NVIDIA A100이나 H100 같은 최신 AI GPU는 HBM2를 대거 탑재하고 있습니다.

![19866_17350_459.png](//img1.kakaocdn.net/thumb/R1280x0.fpng/?fname=http://t1.daumcdn.net/brunch/service/user/5lk/image/dYIhCLRJX3Uo1O3PLNazqBdBFps.png)

물론 HBM이 만능은 아닙니다. DRAM 칩을 쌓아 올리는 3D 공정이 기술적으로 아주 까다롭거든요. 10층 이상 쌓으려면 열 문제도 만만치 않고요. 수율 때문에 생산 비용도 만만찮습니다. 그래도 이런 어려움 속에서 SK하이닉스는 12단 HBM3를 양산하는가 하면, 16단 HBM3E 샘플까지 내놓았죠. 경쟁사 삼성전자와 마이크론 역시 HBM4 개발에 박차를 가하고 있다고 합니다.

![120923596.1.jpg](//img1.kakaocdn.net/thumb/R1280x0.fjpg/?fname=http://t1.daumcdn.net/brunch/service/user/5lk/image/yzcqAbswg4LtHBvzFJas5B8WL4Q.jpg)

앞으로도 HBM은 AI 학습을 이끄는 핵심 메모리로 자리매김할 것 같습니다. 애초에 고대역, 저지연, 고효율을 요구하는 AI 워크로드에 맞춰 진화해왔으니까요. 물론 기술적 도전 과제도 만만치 않습니다. 수율 안정화, 전력 효율 개선, 맞춤형 설계 대응 같은 숙제를 풀어나가야 하죠. 그래도 HBM은 지금의 AI 시대를 연 일등공신임이 분명합니다.

여러분은 어떻게 생각하시나요? HBM 같은 메모리 기술이 AI 발전에 어떤 역할을 할 것 같나요? 앞으로 HBM을 넘어설 만한 혁신적인 아이디어는 없을까요? 다들 한번 상상해 보시면 좋겠네요. 메모리가 빨라져야 AI지능도 한층 더 높아질테니까요?

**AI시대에 알아야 할 UX의 언어는?**

<!-- CATEGORY_NAV_START -->
<style>
.category-nav-wrap { margin-top: 20px; margin-bottom: 20px; padding: 25px 40px; border-top: 1px solid rgba(245,243,238,0.1); display: flex; justify-content: space-between; align-items: center; font-family: 'Pretendard Variable', sans-serif; font-size: 14px; gap: 30px; width: 100vw; position: relative; left: 50%; transform: translateX(-50%); box-sizing: border-box; }
.cat-nav-item { display: flex; align-items: center; gap: 10px; text-decoration: none !important; color: #8f8b82; transition: color 0.2s; max-width: 45%; }
.cat-nav-item:hover { color: #f5f3ee; }
.cat-nav-item:hover .nav-title { color: #f5f3ee; text-decoration: underline; }
.cat-nav-label { font-size: 13px; color: #736f67; white-space: nowrap; font-weight: 300; }
.nav-title { font-weight: 400; color: #c9c8c2; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.cat-nav-right { margin-left: auto; justify-content: flex-end; text-align: right; }
</style>
<div class="category-nav-wrap">
  <a href="/brunch_web_assets/markdown/177_AI%20%EC%B9%A9%20%EC%84%B1%EB%8A%A5%EC%9D%98%20%ED%95%B5%EC%8B%AC%2C%20FLOPS%EC%99%80%20TOPS%20%EA%B7%B8%EB%A6%AC%EA%B3%A0.html" class="cat-nav-item cat-nav-left"><span class="cat-nav-label">'AI의 언어들'의 이전글</span><span class="nav-title">AI 칩 성능의 핵심, FLOPS와 TOPS 그리고..</span></a>
  <a href="/brunch_web_assets/markdown/191_AI%ED%95%98%EB%93%9C%EC%9B%A8%EC%96%B4%2C%20GPU%EC%99%80%20NPU%20%EA%B7%B8%EB%A6%AC%EA%B3%A0%20FPGA%EC%9D%98%20%EC%B0%A8%EC%9D%B4%EC%A0%90.html" class="cat-nav-item cat-nav-right"><span class="nav-title">AI하드웨어, GPU와 NPU 그리고 FPGA의 차이점</span><span class="cat-nav-label">'AI의 언어들'의 다음글</span></a>
</div>
<!-- CATEGORY_NAV_END -->
