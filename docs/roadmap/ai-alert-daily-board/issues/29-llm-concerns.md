# 29. 키 하나로 LLM 관심사 네 개가 한꺼번에 켜지게

Type: task
Status: → GitHub Issue #29 (상태·라벨은 거기가 정본이다)
Blocked by: [11](11-cloudflare-setup.md)

## Question

`summarize.py` 는 카드 요약과 섹션 브리핑만 맡고 있었다. 그런데 그 사이
LLM 이 있어야 제대로 되는 자리가 세 군데 더 늘었다:

- 해외 뉴스 **한국어 제목·해설** ([25](25-translate-foreign-news.md))
- GitHub 스킬 **한 줄 분석**과 **부문 분류** ([17](17-github-skill-browse.md), [21](21-skills-per-category.md))
- **오늘의 키워드** 병합·명명 ([24](24-keyword-specificity.md))

지금은 전부 규칙 기반 씨앗 캐시로 버티고 있다. `ANTHROPIC_API_KEY` 하나를 넣었을 때
이 네 곳이 **동시에** 채워져야지, 관심사마다 따로 붙이면 켜는 방법이 네 가지가 된다.

## Answer

`summarize.py` 를 확장했다. `available(env)` 와 `summarize_board(board, env, budget)` 의
서명과 "키 없으면 아무것도 하지 않는다"는 성질은 그대로 둔 채, 관심사 네 개를
각각 **요청 한 건**으로 덧붙였다.

| 관심사 | 채우는 것 | 캐시 |
|---|---|---|
| 해외 뉴스 번역 | `title_ko`, `note_ko` | `state/news-notes.json` |
| 스킬 한 줄 분석 | `note_ko` | `state/skill-notes.json` |
| 부문 분류 | `category` | (없음) |
| 오늘의 키워드 | `keywords` 섹션 전체 | (없음) |

설계에서 정한 것:

- **부문 분류는 26개 라벨 enum 밖이면 버린다.** 모델이 새 부문을 지어내면
  규칙 기반 추측을 그대로 둔다 — 없는 분류를 만드는 것보다 낫다.
- **키워드는 근거가 2개 이상일 때만 채택한다.** 보드에 실린 항목의 URL 과
  대조해서 2개 미만이면 버린다. `change` 는 같은 `dedup_key` 가 있으면 물려받고,
  없으면 `new` 다 — `continuing` 을 지어내지 않는다.
- **실패 전파를 갈랐다.** 예산 초과/미확인은 즉시 전체 중단(fail-closed)이고,
  HTTP·파싱 실패는 **그 관심사만** 건너뛴다.

### 비용

하루 호출이 ~5건에서 ~9-10건으로 는다 (예산 상한 60건/일 안쪽).
카드 수가 늘어도 **새 네 건은 하루 4건으로 고정**이다.
월 추정 ₩2,650 → **약 ₩5,000**. [11](11-cloudflare-setup.md) 의 숫자도 정정했다.

## Comments

- 2026-09-21: `src/summarize.py` 만 수정. 키 없을 때 보드가 바이트 단위로
  불변인지 실제 `boards/latest.json` 으로 확인.
