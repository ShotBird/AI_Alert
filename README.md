# AI Alert

매일 아침 아이폰에서 AI 동향 한 판을 보기 위한 개인용 도구.

```
오늘의 키워드 → 모델 업데이트 → GitHub 스킬 → 뉴스 Top5 → AI 커뮤니티 Top5
```

---

## 지금 상태

**파이프라인은 돌아간다.** 실제 피드에서 오늘자 보드가 만들어진다.

```
python run.py
```

하루 1,600여 건을 모아 107개 묶음으로 줄이고, 그중 31장을 보드에 싣는다. 결과는 `boards/latest.json` 하나(12KB).
화면은 `web/index.html` 이고 이 파일 하나만 받아 그린다.

**비어 있는 것은 전부 키 세 개에 걸려 있다.** 아래 "내일 할 일" 참고.

---

## 내일 할 일 — 키 세 개

발급은 전부 사람이 해야 한다. 에이전트가 대신 못 한다.
자세한 절차는 [`docs/roadmap/ai-alert-daily-board/issues/11-cloudflare-setup.md`](docs/roadmap/ai-alert-daily-board/issues/11-cloudflare-setup.md).

| 키 | 어디서 | 켜지는 것 | 비용 |
|---|---|---|---|
| `ANTHROPIC_API_KEY` | console.anthropic.com | 한국어 요약 · 섹션 브리핑 · 제대로 된 키워드 | 월 ₩2,650. **콘솔에서 한도 설정 가능** |
| `GH_READ_TOKEN` | GitHub > Developer settings > Fine-grained tokens | GitHub 스킬의 주간 급상승 (지금은 누적 스타 폴백) | 무료. 공개 저장소 읽기 권한만 |
| Cloudflare 토큰 | dash.cloudflare.com | 매일 자동 배포 | 무료 |

**등록 위치**: GitHub 리포의 Settings → Secrets and variables → Actions.
로컬에서도 시험하려면 `.env` 에 같은 이름으로 넣는다 (`.env.example` 참고).

⚠️ **Cloudflare 가입이 결제수단을 요구하면 멈추고 알려줄 것.** 무료라는 전제가 깨지면
공개 리포 + GitHub Pages 안을 다시 비교해야 한다.

---

## 어떻게 돌아가나

```
수집 → 기간 4일 → AI 관련성 → 묶음 → 화제도 → 섹션 배치 → 요약 → boards/latest.json
```

| 파일 | 하는 일 |
|---|---|
| `src/sources.py` | 수집 대상. **실제로 호출해 확인한 것만** 들어 있다 |
| `src/collect.py` | RSS/Atom/HN/HF 를 항목으로 정규화. 소스 하나가 죽어도 나머지는 간다 |
| `src/relevance.py` | AI 관련성 (한·영). 이미 AI 피드인 소스는 다시 따지지 않는다 |
| `src/cluster.py` | 같은 사건을 하나로. URL 정규화 → 제목 유사도 + 내용어 겹침 |
| `src/rank.py` | 화제도. **출처 개수 > 반응 수치 > 최신성** |
| `src/vendors.py` | 모델 업데이트 = 벤더별 현황판 |
| `src/github_skills.py` | 스타 히스토리로 주간 증가분 |
| `src/community.py` | 커뮤니티 Top5 (Tranco + 화제 유입량) |
| `src/keywords.py` | 오늘의 키워드 (키 없을 때의 임시 추출) |
| `src/summarize.py` | Sonnet 5 요약. 키 없으면 조용히 건너뛴다 |
| `src/board.py` | 보드 조립 |
| `src/budget.py` | 일일 호출 상한 |
| `web/index.html` | 홈화면 웹앱 |
| `.github/workflows/daily.yml` | 매일 03:00 KST |

용어는 [`CONTEXT.md`](CONTEXT.md), 화면 규칙은 [`DESIGN.md`](DESIGN.md)에 있다. **둘 다 손으로 고치지 않는다.**

---

## 돈이 새지 않게 하는 장치

NCP 에 결제수단이 등록돼 있고 종량제다. **콘솔 알림은 하드 차단이 아니므로 우리 코드가 막는다.**

- 모든 외부 호출이 일일 카운터(`state/api-usage.json`)를 통과한다
- 상한은 무료 구간의 **2% 이하** (네이버 검색 일 300회 등)
- **카운터를 못 읽으면 호출하지 않는다.** 안전장치가 고장났을 때 뚫리는 게 아니라 멈추는 쪽이다
- `--dry` 는 외부 호출도 저장도 하지 않는다

---

## 뭔가 이상할 때

```bash
python run.py --dry        # 외부 호출 없이 배선만 확인
python tests/test_pipeline.py
```

테스트 17개는 전부 **실제로 났던 사고**를 막는 것이다. 이름만 읽어도 무엇이 잘못됐었는지 알 수 있다.

보드 자체가 상태를 밝힌다. `boards/latest.json` 안에:

- `status` — `ok` / `partial`(일부 소스 실패) / `degraded`(거의 못 모음)
- `sources_status` — 소스별 성공·실패와 이유
- `generator.notes` — 그날 무슨 일이 있었는지 한국어로
- `generator.api_budget` — 호출을 얼마나 썼는지

**섹션이 비면 사라지지 않고 이유를 남긴다.** 사라진 섹션은 버그처럼 보이고, 이유가 적힌 빈 섹션은 알려진 구멍처럼 보인다.

---

## 하지 않기로 한 것

약관을 회피하는 수집은 만들지 않는다. 막힌 소스는 우회하지 말고 기능을 재정의한다.

- **Threads 트렌딩** — 공식 API 에 타인 공개글을 읽는 기능 자체가 없다
- **디시인사이드 수집** — 이용약관이 비영리·개인 포함 자동 수집을 전면 금지
- **텔레그램을 수집원으로** — 봇 약관이 공개 채널 집계를 명시 금지 (알림 발신은 무관)
- **네이티브 iOS 앱** — Mac 없음이 전제. 원하면 별도 지도를 그린다

판단 근거는 전부 `docs/roadmap/ai-alert-daily-board/issues/` 에 남아 있다.

---

## 알림

알림 시각은 **앱이 아니라 아이폰 단축어**에 있다. 시간 자동화가 정해진 시각에 보드를 가져와 알림을 띄운다.
서버는 새벽에 한 번 돌 뿐 사용자 시각을 모른다.

단축어가 조용히 멈추면 아무도 안 알려주므로, 같은 내용을 **메일로도 보낸다**.
알림이 안 뜨는 건 눈치채기 어렵지만 매일 오던 메일이 끊기는 건 눈치챈다.
