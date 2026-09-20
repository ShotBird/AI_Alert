# 14. 모델별 벤치마크 점수

Type: research
Status: → GitHub Issue #14 (상태·라벨은 거기가 정본이다)
Blocked by: (없음)

## Question

사용자 요청: artificialanalysis.ai 처럼 모델별 벤치마크 점수를 가져올 수 있나.
"페이지 구조 그대로 가져와도 된다", 이어서 **"기능적으로 가능하면 그냥 긁어와. 어차피 나 혼자 쓸거야."**

→ 사용자가 판단하고 재확인했다. **기능적으로 가능하면 가져온다.**
다만 어느 경로가 더 안정적인지는 별개 문제라 조사한다.

조사 중인 것:

1. artificialanalysis.ai 의 robots.txt · 페이지가 서버 렌더링인지 · 임베디드 데이터 페이로드 · 공식 API 유무
2. **원천 소스가 더 깨끗한가** — LMArena, HF Open LLM Leaderboard, SWE-bench, EpochAI, OpenRouter 모델 API.
   집계물을 재게시하는 것보다 원천이 안정적이면 그쪽이 낫다 (약관이 아니라 **내구성** 문제)
3. **일간 콘텐츠가 맞는가** — 점수는 모델이 나올 때만 바뀐다. 매일 같은 표면 3일 뒤 안 본다.
   대안: 새 모델이 뜰 때 [모델 업데이트](05-daily-board-schema.md) 행에 점수를 붙이는 방식

## Answer

(조사 중)
