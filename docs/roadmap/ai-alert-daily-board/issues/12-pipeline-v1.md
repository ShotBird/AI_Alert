# 12. 수집 → 보드 JSON 파이프라인 v1

Type: task
Status: claimed
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

(진행 중)
