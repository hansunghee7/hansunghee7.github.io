---
layout: default
title: "Perplexity #2 검색 시스템의 구조 설계"
category: '스타트업 인사이트'
cover_image: 'https://img1.kakaocdn.net/thumb/R1280x0.fjpg/?fname=http://t1.daumcdn.net/brunch/service/user/5lk/image/ea0JK6P4BIQJxzW_h5fais4yano.jpg'
date_string: 'Apr 20. 2025'
---

안녕하세요, 스타트업 성공코치 한성희입니다. 지난 시간에는 Perplexity AI의 핵심 기술 아키텍처를 살펴보았습니다. 오늘은 그 중에서도 검색 시스템의 구조, 특히 BM25와 벡터 검색을 결합한 하이브리드 설계에 대해 실제 구현 방법을 중심으로 자세히 알아보겠습니다.

### **하이브리드 검색의 필요성**


Perplexity가 기존 검색 엔진과 차별화되는 가장 큰 특징 중 하나는 키워드 기반 검색과 의미 기반 검색을 동시에 활용하는 하이브리드 접근법입니다. 이런 접근이 필요한 이유는 두 방식이 각각 고유한 장단점을 가지고 있기 때문입니다.

키워드 기반 검색(BM25, TF-IDF 등)은 정확한 단어 매칭에 강하고 계산 효율성이 높지만, 동의어나 맥락을 이해하지 못합니다. 반면 의미 기반 검색(벡터 검색)은 유사 개념을 인식하고 맥락을 이해하지만, 계산 비용이 높고 정확한 키워드 매칭에는 상대적으로 약합니다.

예를 들어, "2024년 서울 인구는?"이라는 질문은 키워드 매칭이 효과적이지만, "도시 생활의 스트레스를 줄이는 방법은?"과 같은 개념적 질문은 의미 기반 검색이 더 적합합니다. Perplexity는 이런 상황을 인식하고 쿼리 특성에 따라 적절한 검색 방식을 적용하거나, 두 방식을 결합하여 최적의 결과를 제공합니다.

![1_ld0zOBtRHnsDaycUQh2PLg.png](//img1.kakaocdn.net/thumb/R1280x0.fpng/?fname=http://t1.daumcdn.net/brunch/service/user/5lk/image/xaAB7bjFtrwTEDbZ2KJtY2MDXXo.png)

### **쿼리 분석과 라우팅 시스템**


하이브리드 검색의 첫 단계는 사용자의 질문을 분석하여 어떤 검색 방식이 적합한지 판단하는 것입니다. Perplexity는 자연어 처리 기술을 활용해 쿼리의 특성을 파악합니다. 짧은 키워드 중심 쿼리, 따옴표나 불리언 연산자가 포함된 쿼리는 키워드 검색으로 라우팅되고, 긴 문장 형태의 질문이나 개념적 질문은 의미 기반 검색으로 처리됩니다. 복잡한 질문은 두 방식을 모두 사용하는 하이브리드 접근으로 처리하여 결과의 다양성과 정확성을 높입니다.

실제 구현에서는 쿼리 길이, 명사 비율, 질문 형태(5W1H), 특수 연산자 포함 여부 등을 분석하는 간단한 분류 로직부터 시작할 수 있습니다. 더 정교한 시스템을 원한다면 과거 쿼리 데이터로 학습된 머신러닝 모델을 활용하는 것도 가능합니다. 이 단계는 전체 검색 성능에 큰 영향을 미치므로, 사용자 피드백을 기반으로 지속적으로 개선해 나가는 것이 중요합니다.

### **BM25 기반 키워드 검색 구현**


BM25는 1994년에 개발된 검색 알고리즘으로, 문서 내 단어 빈도와 역문서 빈도를 고려하여 관련성을 계산합니다. TF-IDF를 개선한 이 알고리즘은 단어 빈도에 상한을 두어 특정 단어가 과도하게 반복되는 경우의 편향을 줄이고, 문서 길이를 정규화하여 짧은 문서와 긴 문서를 공정하게 평가합니다.

Perplexity와 같은 시스템에서 BM25 검색을 구현할 때는 Elasticsearch가 가장 보편적인 선택입니다. Elasticsearch에서 효과적인 검색을 위해서는 문서 인덱스 설계가 중요합니다. 한국어 문서를 다룬다면 형태소 분석기(nori\_tokenizer)를 활용하고, 제목에는 더 높은 가중치를 부여하는 등의 최적화가 필요합니다. 또한 URL, 출처, 날짜, 카테고리 등의 메타데이터는 필터링에 활용할 수 있도록 keyword 타입으로 지정해야 합니다.

실제 검색 쿼리를 구성할 때는 must, filter, should 등의 boolean 조합을 활용하여 정확도와 관련성을 균형 있게 조정할 수 있습니다. 예를 들어, 핵심 키워드는 must로 반드시 포함되도록 하고, 날짜 범위는 filter로 제한하며, 특정 카테고리는 should로 가중치를 부여하는 방식입니다. 이런 세부적인 조정을 통해 사용자 질문의 의도에 가장 적합한 결과를 찾아낼 수 있습니다.

대규모 문서 컬렉션에서 검색 성능을 최적화하기 위해서는 필터 캐싱, 적절한 샤딩 전략, 스코어 계산 최적화 등의 기술을 활용할 수 있습니다. 이러한 최적화는 사용자에게 빠른 응답 시간을 제공하는 데 중요합니다.

![F9yayQGXAAA__wA.jpg](//img1.kakaocdn.net/thumb/R1280x0.fjpg/?fname=http://t1.daumcdn.net/brunch/service/user/5lk/image/pdjnKDPzOhDZWv4U6Vx1AJTkFaM.jpg)

### **벡터 검색 시스템 구축**


벡터 검색은 텍스트를 고차원 벡터 공간에 표현하고, 이 공간에서의 유사도를 기반으로 검색하는 방식입니다. 이 과정은 크게 임베딩 생성과 벡터 인덱싱, 그리고 유사도 검색으로 나눌 수 있습니다.

텍스트 임베딩을 위해서는 적절한 모델을 선택해야 합니다. SentenceTransformer는 문장 수준 임베딩에 최적화되어 있고, BERT는 더 상세한 의미 표현이 가능하며, MiniLM은 경량화된 모델로 추론 속도가 빠릅니다. 한국어 문서를 다룬다면 다국어 모델이나 한국어에 특화된 모델(예: Ko-SBERT)을 선택하는 것이 좋습니다.

임베딩을 생성한 후에는 이를 효율적으로 저장하고 검색할 수 있는 벡터 데이터베이스가 필요합니다. Faiss는 매우 빠른 검색 속도와 메모리 효율성을 제공하지만 메타데이터 관리가 제한적입니다. Weaviate는 스키마 기반 구조화와 GraphQL을 지원하며 풍부한 필터링이 가능합니다. Milvus는 분산 아키텍처와 뛰어난 확장성을 제공하지만 설정과 운영이 복잡합니다. Qdrant는 사용 편의성이 높고 REST API를 제공하여 빠른 프로토타이핑에 적합합니다.

벡터 데이터베이스에서 효율적인 검색을 위해 ANN(Approximate Nearest Neighbor) 알고리즘을 활용합니다. 이 알고리즘은 정확한 최근접 이웃 대신 근사치를 빠르게 찾음으로써 대규모 벡터 데이터에서도 실시간 검색이 가능하게 합니다. 인덱스 타입(HNSW, IVF, 등)과 파라미터는 데이터 크기와 검색 성능 요구사항에 따라 조정해야 합니다.

벡터 검색 구현 시, 임베딩 생성과 저장은 배치 처리로 최적화하고, 검색은 비동기 처리로 응답 시간을 최소화하는 것이 중요합니다. 또한 임베딩 캐싱을 통해 동일 쿼리에 대한 중복 계산을 피하고, 정기적인 인덱스 업데이트로 최신 정보를 반영해야 합니다.

![1.png](//img1.kakaocdn.net/thumb/R1280x0.fpng/?fname=http://t1.daumcdn.net/brunch/service/user/5lk/image/LQKiZE_RomYrJVvB5WM3pbzg4hk.png)

### **Reranker를 통한 결과 최적화**


초기 검색 결과를 재평가하여 더 정확한 순위를 매기는 Reranker는 하이브리드 검색 시스템의 핵심 구성 요소입니다. 특히 키워드 검색과 벡터 검색 결과를 통합할 때 중요한 역할을 합니다.

CrossEncoder는 Reranking에 널리 사용되는 모델입니다. 이 모델은 쿼리와 문서를 쌍으로 입력받아 관련성 점수를 직접 계산하는 방식으로 작동합니다. 임베딩 모델이 쿼리와 문서를 각각 독립적으로 벡터화하는 것과 달리, CrossEncoder는 둘 사이의 상호작용을 고려하여 더 정확한 관련성 평가가 가능합니다.

실제 구현에서는 초기 검색으로 상위 50-100개 결과를 가져온 후, 이를 CrossEncoder로 재평가하여 최종 순위를 결정하는 방식이 효과적입니다. 이때 문서 길이가 긴 경우 적절히 잘라서 사용하고, 배치 처리를 통해 성능을 최적화할 수 있습니다.

BM25와 벡터 검색 결과를 통합하는 방법으로는 가중 평균이나 RRF(Reciprocal Rank Fusion) 같은 방식이 있습니다. 가중 평균은 두 검색의 정규화된 점수를 가중치(α)를 통해 결합하는 방식입니다. 이 가중치는 검색 도메인과 사용자 피드백을 통해 최적화할 수 있으며, 쿼리 유형에 따라 동적으로 조정하는 것도 가능합니다.

Reranking 과정은 계산 비용이 높기 때문에, 실제 서비스에서는 결과 캐싱, 병렬 처리, 계산량 감소 기법(early stopping 등) 등을 통해 성능을 최적화하는 것이 중요합니다.

![906c3c0f8fe637840f134dbf966839ef89ac7242-3443x1641.png](//img1.kakaocdn.net/thumb/R1280x0.fpng/?fname=http://t1.daumcdn.net/brunch/service/user/5lk/image/66tiaKTwCphBeZD4r6EwJZI2F18.png)

### **쿼리 라우터 설계와 통합 시스템**


이제 키워드 검색, 벡터 검색, Reranker를 하나의 통합된 시스템으로 구성해야 합니다. 이를 위해 쿼리 라우터를 구현하여 사용자 질문의 특성에 따라 적절한 검색 파이프라인으로 안내해야 합니다.

FastAPI와 같은 현대적인 웹 프레임워크를 활용하면 비동기 처리가 가능한 API 엔드포인트를 쉽게 구현할 수 있습니다. 쿼리 라우터는 사용자 질문을 분석하여 키워드 검색, 벡터 검색, 또는 둘 다 사용하는 하이브리드 검색으로 라우팅합니다. 하이브리드 검색의 경우, 두 검색을 병렬로 실행하여 응답 시간을 최소화하고, 결과를 통합한 후 Reranker를 적용합니다.

실제 서비스 환경에서는 오류 처리, 타임아웃 관리, 재시도 로직 등을 추가하여 안정성을 확보해야 합니다. 또한 검색 결과의 다양성을 유지하기 위해 클러스터링이나 다양성 메트릭을 활용할 수 있습니다.

검색 성능을 지속적으로 모니터링하고 개선하기 위해서는 관련성 평가, 사용자 피드백 수집, A/B 테스트 등의 프로세스를 구축해야 합니다. 이를 통해 가중치, 임계값, 검색 파라미터 등을 최적화하고, 검색 품질을 끊임없이 향상시킬 수 있습니다.

![AD_4nXctUk0KyYu4ZEz_WltqubL1XPoYllm2U_lvPGjO76N1JGpml3kyTKCZiYB2D6m8M7XhyWYpnGtTFVAKIxMp3y63CQ9xrteqrdZo19rCzP0EjhCRt3RRpOHY4NZklMb-XS27_MdqePdeyQBNqTb0ZHW6vngK?key=eMVU7KbNgmcKhH2yZMZFvQ](//img1.kakaocdn.net/thumb/R1280x0.fwebp/?fname=http://t1.daumcdn.net/brunch/service/user/5lk/image/fnLx4OyzWe9SDk20MxGzxtNvqOI)

### **성능 최적화와 운영 전략**


실제 서비스에서 하이브리드 검색 시스템을 운영할 때는 성능 최적화와 효율적인 리소스 관리가 중요합니다. 자주 검색되는 쿼리 결과와 임베딩 계산 결과를 캐싱하고, 임베딩 생성이나 문서 인덱싱을 배치로 처리하여 GPU 활용도를 높일 수 있습니다.

시스템 모니터링 또한 중요한 요소입니다. 검색 지연 시간, 정확도, 사용자 만족도 등의 핵심 지표를 추적하고, 오류율과 재시도 패턴을 분석하여 시스템의 안정성을 확보해야 합니다.

비용 관리 측면에서는 임베딩 모델 선택과 인프라 규모를 최적화하고, 필요에 따라 동적 스케일링을 적용하여 효율적으로 리소스를 활용해야 합니다. 특히 벡터 검색과 Reranking은 계산 비용이 높기 때문에, 쿼리 복잡성에 따라 처리 깊이를 조정하는 전략이 효과적입니다.

### **마치며**


Perplexity AI의 검색 시스템은 전통적인 키워드 기반 검색과 최신 벡터 검색을 효과적으로 결합한 하이브리드 아키텍처를 통해 정확하고 관련성 높은 결과를 제공합니다. 이러한 접근 방식은 다양한 형태의 사용자 질문에 유연하게 대응하면서도, 실시간 성능을 유지할 수 있게 해줍니다.

이 기술을 자체 서비스에 적용하려는 팀은 쿼리 특성에 따른 라우팅 전략, 효과적인 인덱싱 구조, 결과 통합 및 재평가 방식, 그리고 시스템 확장성과 운영 효율성 등을 종합적으로 고려해야 합니다. 하지만 모든 구성 요소를 처음부터 구현할 필요는 없으며, 검색 엔진(Elasticsearch), 벡터 데이터베이스(Qdrant, FAISS), 임베딩 모델(SentenceTransformer) 등의 오픈소스 도구를 활용하여 단계적으로 시스템을 구축해 나갈 수 있습니다.

다음 편에서는 이러한 검색 결과를 바탕으로 자연스럽고 정확한 답변을 생성하는 RAG(Retrieval-Augmented Generation) 시스템의 구조를 자세히 살펴보겠습니다. :-)

<!-- CATEGORY_NAV_START -->
<style>
.category-nav-wrap { margin-top: 60px; padding-top: 25px; border-top: 1px solid #eee; display: flex; justify-content: space-between; align-items: center; font-family: 'Noto Sans KR', sans-serif; font-size: 14px; color: #888; gap: 20px; }
.cat-nav-item { display: flex; align-items: center; gap: 8px; text-decoration: none !important; color: #666; transition: color 0.2s; max-width: 48%; }
.cat-nav-item:hover { color: #111; }
.cat-nav-item:hover .nav-title { color: #111; text-decoration: underline; }
.cat-nav-label { font-size: 12px; color: #999; white-space: nowrap; font-weight: 300; }
.nav-title { font-weight: 400; color: #333; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.cat-nav-right { margin-left: auto; justify-content: flex-end; text-align: right; }
</style>
<div class="category-nav-wrap">
  <a href="/brunch_web_assets/markdown/164_%EB%84%B7%ED%94%8C%EB%A6%AD%EC%8A%A4%20%EC%82%AC%EB%A1%80%EB%A1%9C%20%EB%B0%B0%EC%9A%B0%EB%8A%94%20%EC%8A%A4%ED%83%80%ED%8A%B8%EC%97%85%20%ED%95%B5%EC%8B%AC%20%EC%A7%80%ED%91%9C%20%EC%84%A4%EC%A0%95%EB%B2%95.html" class="cat-nav-item cat-nav-left"><span class="cat-nav-label">카테고리의 이전글</span><span class="nav-title">넷플릭스 사례로 배우는 스타트업 핵심 지표 설정법</span></a>
  <a href="/brunch_web_assets/markdown/167_Perplexity%20%231%20%EA%B2%80%EC%83%89%EC%9D%98%20%ED%95%9C%EA%B3%84%EB%A5%BC%20%EB%84%98%EC%96%B4%EC%84%9C.html" class="cat-nav-item cat-nav-right"><span class="nav-title">Perplexity #1 검색의 한계를 넘어서</span><span class="cat-nav-label">카테고리의 다음글</span></a>
</div>
<!-- CATEGORY_NAV_END -->