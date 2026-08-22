---
layout: default
title: "Predictive UX, 사용자의 다음 행동은?"
category: 'UX의 언어들'
cover_image: 'https://img1.kakaocdn.net/thumb/R1280x0.fpng/?fname=http://t1.daumcdn.net/brunch/service/user/5lk/image/BCavakU4xyEfZjvmV2kcIpnlpF0.png'
date_string: 'Jul 25. 2025'
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
            window.location.href = '/log.html?cat=' + encodeURIComponent('UX의 언어들');
        });
    }
});
</script>
<!-- CAT_LINK_SCRIPT_END -->

"사용자가 원하는 것을 사용자보다 먼저 알 수 있다면?"

이제는 공상과학 영화의 이야기가 아닙니다. 아마존이 주문 전에 미리 상품을 배송지 근처로 옮겨두고, 넷플릭스가 시청 패턴을 분석해 다음에 볼 영화를 추천하는 것처럼, Predictive UX는 이미 우리 생활 속에 깊숙이 들어와 있습니다.

Predictive UX는 2010년대 초 빅데이터와 머신러닝 기술이 발전하면서 본격적으로 등장했습니다. 구글이 2012년 Google Now를 출시하며 사용자의 위치, 시간, 검색 기록을 분석해 필요한 정보를 선제적으로 제공한 것이 출발점이었습니다. 이후 스마트폰의 센서 데이터, IoT 기기의 확산, 그리고 AI 기술의 발전으로 사용자 행동 예측의 정확도가 급격히 높아졌습니다. 현재는 단순한 추천을 넘어 사용자의 감정 상태, 컨텍스트, 향후 니즈까지 예측하여 선제적으로 대응하는 수준에 이르렀습니다.

![https%3A%2F%2Fsubstack-post-media.s3.amazonaws.com%2Fpublic%2Fimages%2Fdeb44162-bc26-400a-98a3-28a8ad98ef08_1200x675.jpeg](//img1.kakaocdn.net/thumb/R1280x0.fwebp/?fname=http://t1.daumcdn.net/brunch/service/user/5lk/image/DiCc4bj8H5kk_WwSfLRFs8Vt10I.jpeg)

스포티파이는 사용자의 음악 청취 패턴, 시간대, 요일, 날씨, 위치 정보를 종합 분석해 "Discover Weekly", "Daily Mix" 등 개인화된 플레이리스트를 생성합니다. 심지어 운동할 때, 출퇴근할 때, 휴식할 때 등 상황별로 최적화된 음악을 추천합니다. 우버는 사용자의 이동 패턴을 학습해 평소 출근 시간이나 공항 이용 시점을 예측하고, 미리 차량을 대기시켜 대기 시간을 줄입니다.

구글 지도는 교통 상황, 사용자의 일정, 과거 이동 패턴을 분석해 집에 갈 시간이나 약속 장소로 출발해야 할 시간을 자동으로 알려줍니다. 심지어 주차 공간이 부족한 지역에서는 미리 주차장 정보를 제공하기도 합니다. 아마존은 사용자의 구매 이력과 검색 행동을 분석해 구매 가능성이 높은 상품을 미리 근처 물류센터로 이동시키는 "예상 배송" 시스템을 운영합니다.

![googlenow_lead.1419978966.jpg?quality=90&strip=all&crop=23.039215686275,0,53.921568627451,100](//img1.kakaocdn.net/thumb/R1280x0.fwebp/?fname=http://t1.daumcdn.net/brunch/service/user/5lk/image/tq7pV0Qjr4X2x_5jP5MVh9ONF40)

Predictive UX의 가장 큰 장점은 사용자 만족도와 편의성의 극대화입니다. 사용자가 원하는 것을 찾기 위해 여러 단계를 거칠 필요가 없어 인지 부하가 줄어들고, 개인화된 경험 제공으로 사용자는 서비스가 자신을 이해한다고 느끼게 됩니다. 기업 관점에서는 사용자 이탈률 감소와 전환율 향상, 운영 효율성 증대 등의 이점을 얻을 수 있습니다.

실무에서 Predictive UX를 구현하려면 먼저 사용자 행동 데이터를 체계적으로 수집해야 합니다. 클릭, 스크롤, 체류 시간, 이탈 패턴 등 모든 인터랙션 데이터를 추적하고, 시간, 위치, 디바이스, 날씨 등 컨텍스트 정보도 함께 수집합니다. 다음으로 머신러닝 모델을 활용해 패턴을 분석하고 예측 모델을 구축하며, A/B 테스트를 통해 예측 기반 기능의 효과를 검증합니다.

하지만 가장 중요한 것은 개인정보 보호와 투명성입니다. 사용자 데이터 수집과 활용에 대해 명확히 고지하고 동의를 받아야 하며, 예측이 틀렸을 때의 대안과 사용자가 통제할 수 있는 옵션을 제공해야 합니다. 또한 필터 버블이나 편향된 추천을 방지하기 위해 다양성을 고려해야 하고, 예측에만 의존하지 말고 사용자의 명시적 피드백도 함께 활용해야 합니다.

Predictive UX는 사용자와 서비스 간의 관계를 더욱 스마트하고 개인화된 차원으로 끌어올리는 혁신적인 접근법입니다. 하지만 기술의 힘은 사용자의 신뢰와 동의를 바탕으로 할 때만 진정한 가치를 발휘한다는 점을 잊지 말아야 합니다.

UX의 언어들이 책으로 나왔어요.

<!-- CATEGORY_NAV_START -->
<div class="category-nav-wrap">
  <a href="/brunch_web_assets/markdown/064_%ED%99%94%EC%9E%A5%EC%8B%A4%EC%9D%98%20UX%2C%20%EA%B3%B5%ED%95%AD%EA%B3%BC%20%EA%B8%B0%EC%B0%A8%EC%97%AD%EC%9D%B4%20%EB%A7%90%ED%95%B4%EC%A3%BC%EB%8A%94%20%EA%B3%B5%EA%B0%84%20%EB%94%94%EC%9E%90%EC%9D%B8.html" class="cat-nav-item cat-nav-left"><span class="cat-nav-label">'UX의 언어들'의 이전글</span><span class="nav-title">화장실의 UX, 공항과 기차역이 말해주는 공간 디자인</span></a>
  <a href="/brunch_web_assets/markdown/076_%EC%96%B4%ED%94%84%EB%A1%9C%EC%B9%98%EB%A5%BC%20%EB%B0%94%EA%BE%B8%EB%8B%A4%20AI%20Assisted%20Design.html" class="cat-nav-item cat-nav-right"><span class="nav-title">어프로치를 바꾸다 AI Assisted Design</span><span class="cat-nav-label">'UX의 언어들'의 다음글</span></a>
</div>
<!-- CATEGORY_NAV_END -->
