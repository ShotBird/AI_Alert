# 01. 소스 피드 실동작 검증

Type: research
Status: resolved
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

모든 URL을 실제로 호출했고, 애매한 것은 브라우저 UA로 다시 확인했다. **GREEN만으로는 다섯 섹션이 다 안 채워진다.**

### 모델 업데이트 — 절반만 됨

| 소스 | 판정 | 비고 |
|---|---|---|
| `openai.com/news/rss.xml` | 🟢 | 200+건, 최신 9/18 |
| `blog.google/rss/` | 🟢 | 20건, pubDate 있음 |
| `developers.googleblog.com/rss/` | 🟡 | **item별 pubDate가 하나도 없음** — 항목 단위 최신성 판단 불가 |
| `mistral.ai/news/rss` | 🟢 | 문서에 없지만 실제로 동작. 96건, 최신 9/16 |
| Hugging Face `api/models?sort=createdAt` | 🟢 | 무인증 동작. **500req/5분** 헤더로 확인 |
| Anthropic / xAI / Meta / DeepSeek | 🔴 | **RSS 자동발견 태그가 아예 없음**(원문 HTML 직접 grep 확인). 4개 주요 벤더가 피드로는 안 잡힌다 |

### 뉴스 — 넉넉함

TechCrunch(+AI 카테고리 별도 확인) · The Verge(+AI, **Atom 포맷**) · Ars Technica(+AI) · Hacker News · Techmeme 전부 🟢.
**Hacker News는 Algolia API가 최선** — `points`와 `num_comments`가 응답에 바로 들어 있어 N+1 호출이 없다.

- 🔴 **VentureBeat**: Vercel 봇 차단 페이지를 반환. 1차 조사에서 WebFetch가 **차단 페이지를 보고 그럴듯한 RSS 요약을 지어냈고**, curl 재확인으로 잡아냈다. 이 티켓이 존재한 이유가 바로 이것
- 🔴 **전자신문 `rss.etnews.co.kr/...`**: TLS 인증서 불일치(인증서는 `*.etnews.com`용). → 🟢 `http://rss.etnews.com/04046.xml`로 정정하면 동작(50건, AI/로봇)
- 🔴 **ZDNet Korea**: 작동하는 피드를 못 찾음. FeedBurner 주소는 200을 주지만 **2020년 기사를 캐시로 뱉는다**
- 🟢 **AI타임스**: `aitimes.com/rss/allArticle.xml` (50건, 최신 당일)

### 커뮤니티

- 🟢 GeekNews `news.hada.io/rss/news` — Atom, 50건, 당일. 단 **추천수·댓글수 필드 없음**
- 🟢 velog — 올바른 주소는 `https://v2.velog.io/rss/@<id>` (또는 `api.velog.io`). 문서에 흔히 도는 `velog.io/rss/@<id>`는 **404**
- 🔴 클리앙 — 게시판 RSS 전부 404이고 페이지에 피드 링크 태그 자체가 없다. 2026년 기준 피드 경로 없음

### GitHub

| 토픽 | 레포 수 |
|---|---|
| `topic:agent-skills` | 24,382 |
| `topic:claude-skills` | 8,661 |
| `topic:claude-code-skills` | 1,861 |

무인증 Search API는 **분당 10회**(헤더 확인). 그리고 결정적으로 —
**"최근 스타 증가분" 필드가 API에 없다.** `stargazers_count`(누적)와 `pushed_at`뿐이다.
→ 급상승 랭킹을 하려면 **우리가 매일 스타 수를 스냅샷해서 직접 차분**해야 한다. → 티켓 10으로 분리.

### 다섯 섹션 채움 여부

1. **모델 업데이트** — ⚠️ Anthropic·xAI·Meta·DeepSeek가 조용히 빠진다 → 티켓 09
2. **커뮤니티** — ⚠️ 클리앙 불가. GeekNews + velog(활동 중인 작성자 선별 필요)로 축소
3. **GitHub 스킬** — ⚠️ 목록은 되지만 "급상승"은 불가 → 티켓 10
4. **뉴스 Top5** — ✅ 충분. VentureBeat·ZDNet Korea는 버려도 무방
5. **오늘의 키워드** — ✅ 애초에 피드가 아니라 1~4번의 제목에서 파생. 별도 소스 불필요
