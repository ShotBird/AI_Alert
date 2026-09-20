# 09. RSS 없는 벤더(Anthropic·xAI·Meta·DeepSeek)를 어떻게 잡을 것인가

Type: grilling
Status: open
Blocked by: (없음)

## Question

[01](01-verify-source-feeds.md)에서 확인된 것: **Anthropic, xAI, Meta, DeepSeek는 RSS가 아예 없다.**
추측이 아니라 원문 HTML에 자동발견 링크 태그가 없음을 확인했다.
그런데 이 넷이 빠지면 "주요 회사별 모델 업데이트"라는 기능의 절반이 사라진다.

선택지:

1. **Hugging Face API로 갈음** — Meta·DeepSeek는 가중치를 HF에 올리므로 잡힌다.
   Anthropic·xAI는 클로즈드라 **안 잡힌다**
2. **커뮤니티 미러 피드에 의존** — 누군가 GitHub Actions로 스크래핑해 만든 비공식 RSS가 존재한다.
   공짜지만 남의 취미 프로젝트가 멈추면 같이 멈춘다
3. **뉴스 섹션이 대신하게 둔다** — Anthropic이 뭘 내놓으면 TechCrunch·HN이 반드시 다룬다.
   즉 별도 벤더 추적을 포기하고, 뉴스에서 벤더명으로 필터링해 모델 업데이트 섹션을 만든다
4. **해당 벤더 뉴스 페이지를 직접 파싱** — robots.txt와 약관을 먼저 확인해야 한다

핵심 질문: **"모델 업데이트"는 공식 발표를 봐야 하는가, 아니면 "새 모델이 나왔다는 사실"만 알면 되는가?**
후자라면 3번이 가장 튼튼하고 공짜다.

`grilling` + `domain-modeling` 스킬을 호출할 것.

## Answer

(미해결)
