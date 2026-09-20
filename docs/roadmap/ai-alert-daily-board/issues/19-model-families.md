# 19. 모델 업데이트 — 메인스트림 계열 분리

Type: task
Status: claimed
Blocked by: (없음)

## Question

사용자 요청: "한 회사에 LLM 모델이 여러 개일 거잖아. 메인스트림은 분리해서 보여줘."

맞는 지적이다. 지금은 **회사당 한 줄**이고 "그 회사가 마지막으로 낸 아무거나"를 싣는다.
그래서 Meta 가 `Llama-Prompt-Guard-2-86M`(가드레일 모델)로 대표되고,
Anthropic 은 Opus·Sonnet·Haiku 중 무엇이 최신인지 알 수 없다.

### 할 것

회사가 아니라 **계열(family)** 단위로 행을 만든다.

| 회사 | 메인스트림 계열 |
|---|---|
| Anthropic | Opus · Sonnet · Haiku |
| OpenAI | GPT · o-시리즈 |
| Google | Gemini · Gemma |
| Meta | Llama |
| xAI | Grok |
| DeepSeek | DeepSeek-V · DeepSeek-R |
| Alibaba | Qwen |
| 그 외 | 대표 계열 하나씩 |

계열이 하나도 안 잡히는 회사는 지금처럼 회사 한 줄로 남긴다.
**계열을 지어내지 않는다** — 모르면 회사 줄이 정직하다.

## Answer

(진행 중)
