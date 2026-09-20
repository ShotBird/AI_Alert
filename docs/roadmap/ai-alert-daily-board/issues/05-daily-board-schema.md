# 05. 일일 보드 스키마와 다섯 섹션의 내용 확정

Type: grilling
Status: resolved
Blocked by: 01

## Question

파이프라인과 화면이 주고받는 **유일한 계약**을 확정한다. 이게 정해지면 수집·요약 쪽과 화면 쪽이
서로를 기다리지 않고 따로 만들어질 수 있다.

정해야 할 것:

- 다섯 섹션 각각에 **몇 개**가, **어떤 필드**로 들어가는가
  (제목 / 한 줄 요약 / 출처 이름 / 링크 / 핫도 / 출처 개수 / 최초 게시 시각)
- 섹션별 3줄 브리핑을 어디에 담는가
- "오늘의 키워드"는 키워드마다 어떤 항목들을 묶어 보여주는가
- 어제 대비 **변화**를 어떻게 표현하는가 (신규 / 계속 뜨는 중 / 사라짐)
- 일부 소스가 죽은 날의 표현 — 섹션을 비우고 이유를 적는가, 숨기는가
- 보관 정책 — 며칠치를 남기는가 (조사 권고: 전체 14일 + 가벼운 색인 90일)
- 모바일 데이터로 받기에 충분히 작은가

`grilling` + `domain-modeling` 스킬을 호출할 것. 여기서 정해지는 용어(항목·클러스터·핫도·보드)는
`CONTEXT.md`에 바로 기록한다.

조사 단계에서 나온 JSON 초안이 출발점으로 있으니 백지에서 시작하지 말 것.

## Answer

### 정해진 것

| 항목 | 결정 |
|---|---|
| 섹션 | **4개** — 모델 업데이트 / GitHub 스킬 / 뉴스 Top5 / 오늘의 키워드 |
| 분량 | 섹션당 **5개**, 전체 20개 내외 (아침 3분) |
| 제목 | **원문 그대로**, 아래에 한국어 한 줄 요약 |
| 변화 표시 | **넣는다** — 카드·키워드마다 `신규` / `지속` |
| 보관 | 전체 보드 14일 + 가벼운 색인 90일 |

**커뮤니티 섹션은 없어졌다.** 네이버·카카오는 검색어를 줘야 답하고 그 검색어는 키워드에서 나오므로,
"커뮤니티"는 독립 섹션이 아니라 **키워드에 붙는 한국 반응**이다. GeekNews는 RSS라 검색어가 필요 없어
뉴스 섹션의 수집원으로 들어간다.

용어는 `CONTEXT.md`에 기록했다. "핫도"는 폐기하고 **화제도**를 쓴다.

### 스키마

```jsonc
{
  "schema_version": "1.0",
  "board_date": "2026-09-21",
  "generated_at": "2026-09-21T03:58:12+09:00",
  "status": "ok",                    // ok | partial | degraded
  "previous_board_date": "2026-09-20",

  "generator": {
    "pipeline_version": "0.1.0",
    "model": "claude-sonnet-5",
    "counts": { "collected": 214, "clustered": 131, "published": 20 },
    "api_budget": { "naver_search": "12/300", "naver_trend": "4/20" }
  },

  "sources_status": [
    { "id": "openai_rss",  "ok": true,  "items": 6 },
    { "id": "venturebeat", "ok": false, "items": 0, "error": "blocked" }
  ],

  "sections": [
    {
      "id": "model_updates",          // model_updates | github_skills | top_headlines | keywords
      "title": "모델 업데이트",
      "briefing_ko": ["...", "...", "..."],
      "empty_reason": null,           // cards 가 비면 왜 비었는지
      "cards": [ /* 아래 카드 모양 */ ]
    }
  ]
}
```

**카드 (모델 업데이트 · 뉴스 Top5 공통)**

```jsonc
{
  "id": "c_2026-09-21_007",          // 날짜+순번. 내용 해시가 아니라 재실행해도 안정적
  "title": "Anthropic ships Claude Opus 5",   // 원문 그대로, 번역하지 않음
  "summary_ko": "코딩 벤치마크에서 전작 대비 …",
  "url": "https://...",              // 대표 링크 하나
  "heat": 8.42,
  "source_count": 5,
  "sources": [                        // 최대 3개까지만. 크기 제한용
    { "name": "Hacker News", "url": "...", "engagement": 512 },
    { "name": "TechCrunch",  "url": "..." }          // engagement 없으면 생략
  ],
  "change": "new",                    // new | continuing
  "first_seen": "2026-09-21",
  "published_at": "2026-09-21T05:02:00Z",
  "vendor": "anthropic"               // 모델 업데이트 섹션만
}
```

**카드 (GitHub 스킬)** — 위 공통 필드에 더해:

```jsonc
{
  "repo": "anthropics/skills",
  "stars": 8661,
  "stars_delta": 120,                 // 티켓 10이 스냅샷 방식을 정하기 전까지 null
  "category": "planning"              // 값 목록은 티켓 06이 정한다
}
```

**카드 (오늘의 키워드)** — 모양이 다르다:

```jsonc
{
  "id": "k_2026-09-21_01",
  "keyword": "agentic coding",
  "keyword_ko": "에이전트형 코딩",
  "mentions": 9,                      // 오늘 항목 중 몇 개에 등장했나
  "card_ids": ["c_2026-09-21_007"],   // 어느 카드들과 연결되나
  "change": "new",
  "korea": {
    "naver": { "blog": 56386, "cafe": 296181, "news": 225434 },
    "kakao": { "web": 122189, "blog": 376734, "cafe": 5400 },
    "trend": { "direction": "up", "index": 73 },   // 데이터랩. 없으면 null
    "picks": [                        // 대표 글 2개
      { "title": "...", "url": "...", "source": "네이버 카페" }
    ]
  }
}
```

### 실패했을 때

- **일부 소스 실패** → `status: "partial"`, 나머지로 보드를 만든다. 이게 정상 상태에 가깝다
- **섹션이 비었다** → 섹션을 지우지 않고 `cards: []` + `empty_reason`을 남긴다.
  사라진 섹션은 버그처럼 보이고, 이유가 적힌 빈 섹션은 알려진 구멍처럼 보인다
- **수집량이 평소의 10% 미만** → `status: "degraded"`
- **파이프라인이 아예 안 돌았다** → 가짜 보드를 만들지 않는다. 오늘 파일이 그냥 없다.
  화면이 어제 것을 **스테일 배지와 함께** 보여주는 것으로 처리한다 (클라이언트 책임)

### 파일 배치

```
boards/2026-09-21.json     # 하루치. 14일 보관
boards/latest.json         # 오늘 것 사본. 화면은 이것만 받으면 된다
boards/index.json          # 90일치 { date, status, counts } 만. 파이프라인 건강 확인용
```

화면이 매번 받는 건 `latest.json` 하나다. 카드 20개 기준 수 KB 수준이라 모바일 데이터로 부담 없다.
**본문·발췌문은 넣지 않는다** — 제목 + 한 줄 요약 + 링크까지만. 크기가 작은 이유가 이것이다.

### 이 스키마가 넘긴 숙제

- `heat`의 정확한 가중치 — 근거 세 가지는 `CONTEXT.md`에 고정했고, 계수는 실제 데이터로 튜닝
- `category` 값 목록 → 티켓 06
- `stars_delta` 생산 방법 → 티켓 10
- 섹션 순서와 접힘 여부 → 티켓 07 (화면 문제지 계약 문제가 아니다)
