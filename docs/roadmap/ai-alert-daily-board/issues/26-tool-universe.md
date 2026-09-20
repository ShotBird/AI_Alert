# 26. GitHub 섹션을 스킬 너머로 — MCP·프레임워크·CLI

Type: task
Status: claimed
Blocked by: (없음)

## Question

사용자 요청: "GitHub 스킬 말고 MCP 등 다른 유명한 툴들도 소팅/차팅하는 구역을 만들고 싶다.
추천안으로 진행해."

### 추천안: 새 섹션이 아니라 **축을 하나 더 얹는다**

이미 있는 기계를 그대로 쓴다 — 토픽 검색, 스타 히스토리 증가분, 부문 분류, Top 20.
**바뀌는 건 토픽 목록뿐이다.** 새 섹션을 만들면 수집·랭킹·화면을 통째로 다시 짜야 하고,
아침에 볼 섹션만 하나 더 늘어난다.

섹션 이름을 **"GitHub 급상승"** 으로 바꾸고 상단에 **종류** 축을 둔다:

| 종류 | 토픽 |
|---|---|
| 스킬 | `agent-skills`, `claude-skills`, `claude-code-skills` |
| MCP 서버 | `mcp`, `mcp-server`, `model-context-protocol` |
| 에이전트 프레임워크 | `ai-agent`, `agent-framework`, `llm-agent`, `autonomous-agents` |
| CLI·개발도구 | `ai-cli`, `llm-tools`, `ai-coding` |

부문(디자인·코드리뷰 …)은 그 아래 두 번째 축으로 남는다.
즉 **종류 → 부문 → Top 20** 이다.

### 비용

토픽이 3개에서 13개로 늘어난다. 검색은 토픽당 1~3회라 싸지만,
**증가분 조회가 후보 수만큼 든다.** 무인증 시간당 60회로는 한 종류도 못 채운다.
`GH_READ_TOKEN` 이 사실상 전제 조건이 된다 ([11](11-cloudflare-setup.md)).

## Answer

(진행 중)
