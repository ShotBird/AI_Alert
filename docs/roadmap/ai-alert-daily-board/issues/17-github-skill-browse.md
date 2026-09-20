# 17. GitHub 스킬 — 부문 블록 + Top 20 + 한 줄 분석

Type: task
Status: → GitHub Issue #17 (상태·라벨은 거기가 정본이다)
Blocked by: (없음)

## Question

사용자 요청:

1. **더보기**를 누르면 Top 20 까지
2. **부문을 상위 블록**으로 빼고, 부문을 누르면 그 부문의 Top 20
3. `DESIGN.md` 무시해도 됨
4. **"어떤 스킬인지 LLM 으로 한 줄 분석"이 안 되어 있다**

### 4번에 대한 사실 관계

요약 모듈(`summarize.py`)은 붙어 있고 카드마다 `summary_ko` 자리도 있다.
**`ANTHROPIC_API_KEY` 가 없어서 잠들어 있을 뿐이다.** 지금 화면에 보이는 한 줄은
GitHub 이 준 영어 `description` 이다.

키를 기다리는 동안 비워두면 기능이 없는 것과 같으므로 **씨앗 캐시**를 둔다:

- `state/skill-notes.json` 에 `레포 → 한국어 한 줄` 을 저장
- 파이프라인은 `summary_ko` 가 없을 때 이 캐시를 쓴다
- 키가 생기면 `summarize.py` 가 덮어쓴다 — 캐시는 자동으로 뒷전이 된다

즉 **오늘 당장 한국어로 보이고, 키가 생기면 자동으로 더 나아진다.**

## Answer

(진행 중 — UI / 파이프라인 / 씨앗 캐시 3갈래 병렬)
