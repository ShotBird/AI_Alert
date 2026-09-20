# 01. 소스 피드 실동작 검증

Type: research
Status: claimed
Blocked by: (없음)

## Question

차팅 단계의 조사는 "존재한다고 보고됨"과 "직접 호출해 확인함"이 섞여 있다.
실제로 코드를 짜기 전에, 후보 소스 전체를 한 번씩 호출해서 **살아있는 것만 남긴 확정 목록**을 만들어야 한다.

확인 대상:

- **모델 업데이트**: `openai.com/news/rss.xml`(검증됨), `developers.googleblog.com/rss/`(검증됨),
  Hugging Face `api/models?sort=createdAt`(무인증 호출 한도 확인 필요),
  Anthropic·Meta·Mistral·xAI·DeepSeek — 공식 RSS 없음이 확정이면 대안(커뮤니티 미러 피드)의 신뢰도까지 판단
- **뉴스**: TechCrunch / The Verge(AI 카테고리) / Ars Technica(AI) / VentureBeat AI /
  Hacker News(Firebase + Algolia) / Techmeme / 전자신문 섹션 RSS / ZDNet Korea / AI타임스
- **커뮤니티**: GeekNews `news.hada.io/rss/news`(검증됨), velog 작성자별 RSS(정확한 URL 미확정 — `v2.velog.io` 인지 `api.velog.io` 인지),
  클리앙 RSS 생존 여부
- **GitHub**: Search API `topic:claude-skills` 실제 결과 수와 응답 형태, 인증 시 분당 30회 한도 확인

각 항목을 GREEN(바로 사용) / YELLOW(되지만 불안정) / RED(사용 불가)로 판정하고,
**GREEN만으로 다섯 섹션이 다 채워지는지**를 답할 것. 채워지지 않는 섹션이 있으면 그게 다음 티켓이 된다.

## Answer

(미해결)
