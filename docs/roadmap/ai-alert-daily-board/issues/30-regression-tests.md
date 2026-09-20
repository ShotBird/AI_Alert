# 30. 회귀 방어 테스트 확대

Type: task
Status: → GitHub Issue #30 (상태·라벨은 거기가 정본이다)
Blocked by: (없음)

## Question

`tests/test_pipeline.py` 17개는 **실제로 났던 사고**를 하나씩 막는 규칙으로 쓰였다.
그 사이 모듈이 늘었는데(`vendors`, `timeline`, `keywords`, `relevance`,
`github_skills`, `board`) 그쪽은 테스트가 없다. 고친 결함이 조용히 되살아날 자리다.

같은 규칙을 유지한다: **"함수가 뭔가 돌려준다"가 아니라 "이 사고가 다시 나면
여기서 잡힌다"가 기준**이다. 외부 호출은 하지 않는다.

## Answer

`tests/test_coverage.py` 신설, **34개 추가** (기존 17개는 그대로 통과).

| 모듈 | 개수 | 막는 사고 |
|---|---|---|
| `vendors` | 7 | 계열 분리, 버전이 계열명 뒤에 와야 출시, 2개 벤더 헤드라인 거부, 클로즈드 벤더는 HF 보다 자기 채널 우선 |
| `timeline` | 2 | 소유자 접두사 중복 제거, 작년 항목 축에서 제외 |
| `keywords` | 3 | 일반어(에이전트/오픈/companies) 차단, 문장 조각 차단, 단일 출처 배제 |
| `relevance` | 6 | `"ai"` 부분일치 함정(said/chair/Thailand), 한국어 조사(AI가/AI는) |
| `github_skills` | 2 | 레이트리밋을 '데이터 없음'과 구분 |
| `board` | 5 | 섹션별 빈 사유 문구, 벤더 `[]` 와 `None` 의 서로 다른 경로 |

### 순수 함수가 아닌 것 하나

`run.py --dry` 가 멀쩡한 보드를 빈 보드로 덮어쓴 사고는 고친 자리가 `main()` 안이라
순수 함수로 부를 수 없다. `inspect.getsource` 로 **"dry 분기의 return 이
`board_mod.write()` 호출보다 소스 순서상 앞에 있는지"** 를 정적으로 확인한다.
의도적인 예외이고 테스트 파일 주석에 적어 뒀다.

## Comments

- 2026-09-21: `tests/test_coverage.py` 만 추가. `state/` 는 건드리지 않았다.
- 이 티켓의 후속이 [31](31-render-guard.md) 이다 — 파이썬 51개가 전부 통과하는
  동안 **화면은 죽어 있었다.** 이쪽을 아무도 안 보고 있었다.
