# 12. 수집 → 보드 JSON 파이프라인 v1

Type: task
Status: → GitHub Issue #12 (상태·라벨은 거기가 정본이다)
Blocked by: 01, 05, 06, 09, 10

## Question

결정이 전부 끝났으니 실제로 돌아가는 것을 만든다.
**목표: 공개 피드만으로 오늘자 `boards/latest.json`을 실제로 생성한다.**

범위에 넣는 것:

- 소스 레지스트리 — [01](01-verify-source-feeds.md)에서 GREEN 판정된 것만
- 수집기 — RSS/Atom/JSON 을 항목으로 정규화
- 묶음 — URL 정규화 → 제목 유사도
- 화제도 — 출처 개수 중심, `CONTEXT.md` 정의대로
- 보드 조립 — [05](05-daily-board-schema.md) 스키마 그대로
- 호출 예산 — [08](08-runtime-infrastructure.md)의 fail-closed 카운터

범위에서 빼는 것 (열쇠가 없어서):

- **LLM 요약** — `ANTHROPIC_API_KEY`가 아직 없다. 요약 자리는 비워두고 파이프라인은 완주한다
- **Cloudflare 배포** — [11](11-cloudflare-setup.md) 대기
- **네이버·카카오 한국 반응** — 키는 있으나 키워드 추출이 LLM에 걸려 있어 v2로 미룬다

제약: 표준 라이브러리만 쓴다. 비개발자가 `pip install` 없이 돌릴 수 있어야 한다.

## Answer

**돌아간다.** 실제 피드에서 오늘자 `boards/latest.json` 을 만든다. 표준 라이브러리만 쓴다.

```
수집 1,629건 → 기간 4일 창 → AI 관련성 → 묶음 107 → 게시 15
```

| 파일 | 하는 일 |
|---|---|
| `src/sources.py` | 01 에서 실호출로 확인한 소스만. 소스별 시간대 포함 |
| `src/collect.py` | RSS/Atom/HN/HF 를 항목으로 정규화. 소스 하나가 죽어도 계속 간다 |
| `src/relevance.py` | AI 관련성 점수 (한·영). 이미 AI 피드인 소스는 다시 따지지 않는다 |
| `src/cluster.py` | URL 정규화 → 제목 유사도 + 내용어 겹침 |
| `src/rank.py` | 화제도. 출처 개수 > 반응 > 최신성 |
| `src/github_skills.py` | 스타 히스토리로 7일 증가분 + 부문 배지 |
| `src/community.py` | 커뮤니티 Top5 (13번) |
| `src/summarize.py` | Sonnet 5 요약. 키 없으면 무해하게 건너뛴다 |
| `src/board.py` | 05 스키마대로 조립. 빈 섹션은 이유와 함께 남긴다 |
| `src/budget.py` | 일일 호출 상한. 카운터 못 읽으면 호출 안 함 |
| `web/index.html` | 홈화면 웹앱. `latest.json` 하나만 받는다 |
| `.github/workflows/daily.yml` | 매일 03:00 KST |
| `tests/test_pipeline.py` | 17개. 전부 **실제로 났던 사고**를 막는 것 |

실제 화면: https://claude.ai/artifact/S59NApcP8eBaDhdMCYLT8a

### 첫 출력을 보고 고친 것들 — 코드를 봐서는 안 보였던 것

1. **OpenAI 피드가 아카이브 1,210건을 준다.** 날짜 창이 없으면 몇 달 전 글이 오늘 것과 경쟁한다
2. **화제도가 음수(-18)였다.** 감쇠를 뺄셈으로 해서. 곱셈 배율로 바꿨다
3. **AI타임스 `pubDate` 에 시간대가 없다.** UTC 로 읽으면 기사가 미래가 되고, 미래는 최신성 만점이라 뉴스 5칸을 통째로 가져갔다
4. **부문 분류가 부분 문자열이었다.** `"ui"` 가 build·guide 에 걸려 코드리뷰 도구가 디자인으로 갔다
5. **한 매체가 섹션을 독식했다.** 한 피드에서 5칸이면 보드가 아니라 그 매체의 목차다
6. **GeekNews 의 "뇌 건강" 기사가 AI 뉴스로 실렸다.** 일반 테크 피드라서. 관련성 필터로 하루 100건이 걸러진다
7. **출시가 없는 날 벤더 홍보글이 모델 섹션을 채웠다.** "교육 학점", "컨설팅사와 제휴". 이제 짧아지더라도 출시만 싣는다
8. **섹션을 소스로만 정해서** GeekNews 로 들어온 StepFun 출시가 뉴스에 갇혔다. 09 가 이미 "뉴스가 벤더 발표를 대신한다"고 정했는데 코드가 반영을 안 했다
9. **제품명 고정 목록으로는** StepFun·Kimi·GLM 처럼 목록에 없는 벤더를 영원히 못 잡는다. 출시 동사 + (제품명 또는 모델 단어)로 바꿨다

### 남은 것

- `ANTHROPIC_API_KEY` → 요약·브리핑·오늘의 키워드
- `GH_READ_TOKEN` → GitHub 섹션 (무인증은 시간당 60회라 금방 막힌다)
- Cloudflare 토큰 → 배포 (11번)
