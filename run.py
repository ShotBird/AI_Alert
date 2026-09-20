"""AI Alert — 하루치 보드를 만든다.

    python run.py

기본은 실제 호출을 한다. `--dry` 를 주면 저장된 응답만 쓰고 바깥으로 나가지 않는다.
개발 중 실수로 외부 API를 때려 예산을 태우는 것을 막기 위한 장치다.
"""

import argparse
import os
import sys
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from src import benchmarks                    # noqa: E402
from src import board as board_mod            # noqa: E402
from src import collect as collect_mod        # noqa: E402
from src import community as community_mod    # noqa: E402
from src import github_skills                 # noqa: E402
from src import keywords as keywords_mod      # noqa: E402
from src import relevance                     # noqa: E402
from src import summarize                     # noqa: E402
from src import timeline                      # noqa: E402
from src import vendors                       # noqa: E402
from src.budget import Budget, BudgetUnavailable   # noqa: E402
from src.cluster import build_clusters        # noqa: E402
from src.rank import rank                     # noqa: E402
from src.sources import (MODEL_WORDS, PRODUCT_TERMS,  # noqa: E402
                         RELEASE_HINTS, SOURCES)

BOARDS = os.path.join(HERE, "boards")
COUNTER = os.path.join(HERE, "state", "api-usage.json")
RANK_CACHE = os.path.join(HERE, "state", "domain-ranks.json")
BENCH_CACHE = os.path.join(HERE, "state", "benchmarks.json")


def load_env(path=os.path.join(HERE, ".env")):
    out = {}
    try:
        with open(path, encoding="utf-8-sig") as fh:
            for line in fh:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, _, v = line.partition("=")
                v = v.strip().strip('"').strip("'")
                if v:
                    out[k.strip()] = v
    except FileNotFoundError:
        pass
    return out


def looks_like_release(title):
    """모델 업데이트 섹션에 넣을 만한가.

    티켓 09의 발견: 회사명으로 걸면 소송·인사·정치가 딸려오고,
    제품명으로 걸어야 실제 출시가 잡힌다.

    다만 제품명 목록만으로는 목록에 없는 벤더를 영원히 놓친다. 실제로
    "StepFun, 차세대 플래그십 AI 모델 Step 5 Preview 공개"가 그래서 빠졌다.
    그래서 **출시를 알리는 말 + (아는 제품명 또는 모델을 가리키는 말)**로 본다.
    """
    low = title.lower()
    if not any(hint in low for hint in RELEASE_HINTS):
        return False
    return (any(term in low for term in PRODUCT_TERMS)
            or any(word in low for word in MODEL_WORDS))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true",
                    help="외부 호출도 저장도 하지 않는다. 배선만 확인한다")
    ap.add_argument("--no-github", action="store_true",
                    help="GitHub 섹션을 건너뛴다 (core 예산 아끼기)")
    ap.add_argument("--days", type=int, default=4,
                    help="며칠치까지 볼 것인가 (기본 4일)")
    args = ap.parse_args()

    env = load_env()
    now = datetime.now(timezone.utc)
    notes = []

    try:
        budget = Budget(COUNTER)
    except BudgetUnavailable as exc:
        # fail-closed: 안전장치를 못 읽으면 호출하지 않는다.
        print(f"[중단] {exc}", file=sys.stderr)
        return 2

    if args.dry:
        print("[dry] 외부 호출을 하지 않습니다.")
        items, status = [], []
    else:
        print(f"[수집] 소스 {len(SOURCES)}개")
        items, status = collect_mod.collect(SOURCES)
        ok = sum(1 for s in status if s["ok"])
        print(f"[수집] 성공 {ok}/{len(status)} · 항목 {len(items)}개")
        for s in status:
            if not s["ok"]:
                print(f"        실패: {s['id']} ({s['error']})")

    # 현황판은 날짜 창 이전까지 본다. "이 회사의 최신 모델"은
    # 최근 4일 안에 나온 것이 아니라 **마지막으로 나온 것**이기 때문이다.
    # 창을 적용하면 조용한 회사가 전부 "소식 없음"이 되어 현황판의 뜻이 사라진다.
    all_items = list(items)

    # 날짜 창. 피드가 과거 아카이브를 통째로 주는 경우가 있어서
    # (OpenAI 는 1,200건을 준다) 이게 없으면 몇 달 전 글이 오늘 것과 경쟁한다.
    cutoff = now - timedelta(days=args.days)
    fresh = [i for i in items
             if i.get("published_at") is None or i["published_at"] >= cutoff]
    stale_n = len(items) - len(fresh)
    if stale_n:
        print(f"[기간] {args.days}일 밖 {stale_n}건 제외 · 남은 항목 {len(fresh)}개")
    items = fresh

    # AI 관련성. GeekNews·Techmeme 는 일반 테크 피드라 "뇌 건강" 같은 기사가 섞인다.
    # 이미 AI 카테고리로 거른 피드(TechCrunch AI 등)는 다시 따지지 않는다.
    before = len(items)
    items = [i for i in items
             if i["section"] != "top_headlines"
             or (relevance.is_relevant(i["title"], i["source_id"])
                 and not relevance.is_promo(i["title"]))]
    off_topic = before - len(items)
    if off_topic:
        print(f"[관련성] AI와 무관한 뉴스 {off_topic}건 제외")

    # 출시로 보이는 항목에 표시를 단다. 거르지는 않는다 —
    # 실제 출시는 하루 한두 건이라 걸러버리면 섹션이 빈다.
    # 대신 화제도에서 가점을 받아 위로 올라간다.
    releases = 0
    for item in items:
        if item["source_id"].startswith("hf_") or looks_like_release(item["title"]):
            item["is_release"] = True
            releases += 1

    # 출시 소식은 어느 소스로 들어오든 모델 업데이트다.
    # 섹션을 소스로만 정하면 GeekNews 로 들어온 "Step 5 Preview 공개"가
    # 뉴스에 갇힌다. 티켓 09 에서 "뉴스 커버리지가 벤더 발표를 대신한다"고
    # 정했으므로, 내용이 출시면 섹션을 옮긴다.
    moved = 0
    for item in items:
        if item.get("is_release") and item["section"] != "model_updates":
            item["section"] = "model_updates"
            moved += 1
    if moved:
        print(f"[재배치] 뉴스에서 들어온 출시 소식 {moved}건을 모델 업데이트로")

    # 모델 업데이트 섹션은 출시로 보이는 것만 남긴다.
    # 가점만으로는 출시가 없는 날 벤더 홍보글("교육 학점", "컨설팅사와 제휴")이
    # 다섯 칸을 채운다. 그건 모델 업데이트가 아니라 그 회사 블로그 목차다.
    # 실제 출시는 하루 한두 건이라 섹션이 짧아지지만, 짧은 게 정직하다.
    before = len(items)
    items = [i for i in items
             if i["section"] != "model_updates" or i.get("is_release")]
    print(f"[선별] 출시 {releases}건 · 벤더 홍보글 {before - len(items)}건 제외")

    clusters = rank(build_clusters(items), now)
    by_section = {}
    for c in clusters:
        by_section.setdefault(c["section"], []).append(c)
    print(f"[묶음] {len(items)}개 항목 → {len(clusters)}개 묶음")

    github_rows = []
    if not args.dry and not args.no_github:
        token = env.get("GH_READ_TOKEN") or env.get("GITHUB_TOKEN") or os.environ.get("GITHUB_TOKEN")
        if not token:
            notes.append("GitHub 토큰이 없어 후보 수를 줄였습니다 (무인증 core 시간당 60회).")
        try:
            github_rows, gh_notes = github_skills.top_rising(
                token, budget, candidates=300 if token else 45)
            notes.extend(gh_notes)
            print(f"[GitHub] 급상승 {len(github_rows)}개")
        except Exception as exc:
            notes.append(f"GitHub 섹션 실패: {type(exc).__name__}")
            print(f"[GitHub] 실패: {type(exc).__name__}")

    community_rows = []
    if not args.dry:
        try:
            community_rows, com_notes = community_mod.top_communities(
                items, budget, RANK_CACHE)
            notes.extend(com_notes)
            print(f"[커뮤니티] {len(community_rows)}곳")
        except Exception as exc:
            notes.append(f"커뮤니티 섹션 실패: {type(exc).__name__}")
            print(f"[커뮤니티] 실패: {type(exc).__name__}")

    vendor_rows = None
    if not args.dry:
        try:
            for it in all_items:
                if (it["source_id"].startswith("hf_")
                        or looks_like_release(it["title"])):
                    it["is_release"] = True
            vendor_rows, v_notes = vendors.vendor_status(all_items, now)
            notes.extend(v_notes)
            filled = sum(1 for r in vendor_rows if r["model"])
            print(f"[벤더] {filled}/{len(vendor_rows)}곳 현황 확인")
        except Exception as exc:
            notes.append(f"벤더 현황 실패: {type(exc).__name__}")
            print(f"[벤더] 실패: {type(exc).__name__}")

    milestone = None
    if not args.dry:
        try:
            milestone, m_notes = timeline.build(all_items, now)
            notes.extend(m_notes)
            print(f"[마일스톤] 올해 출시 {len(milestone['points'])}건")
        except Exception as exc:
            notes.append(f"마일스톤 실패: {type(exc).__name__}")
            print(f"[마일스톤] 실패: {type(exc).__name__}")

    # 벤치마크 점수. 별도 섹션이 아니라 벤더 행에 붙는 주석이다 —
    # 커버리지가 낮아(오늘 3/14) 섹션으로 만들면 대부분 빈칸이 된다.
    if vendor_rows and not args.dry:
        try:
            index, b_notes = benchmarks.load_scores(budget, BENCH_CACHE)
            notes.extend(b_notes)
            notes.extend(benchmarks.annotate(vendor_rows, index))
            hit = sum(1 for r in vendor_rows if r.get("benchmarks"))
            print(f"[벤치마크] {hit}/{len(vendor_rows)}개 모델에 점수")
        except Exception as exc:
            notes.append(f"벤치마크 실패: {type(exc).__name__}")
            print(f"[벤치마크] 실패: {type(exc).__name__}")

    keyword_rows, k_notes = keywords_mod.extract(items)
    notes.extend(k_notes)
    print(f"[키워드] {len(keyword_rows)}개")

    result = board_mod.build(by_section, github_rows, status,
                             budget.report(), BOARDS, now, notes,
                             community_rows=community_rows,
                             vendor_rows=vendor_rows,
                             keyword_rows=keyword_rows,
                             milestone=milestone)
    # 요약. 키가 없으면 조용히 건너뛰고 카드는 제목만으로 완성돼 보인다.
    if not args.dry:
        try:
            notes.extend(summarize.summarize_board(result, env, budget))
            if result["generator"].get("model"):
                print(f"[요약] {result['generator']['model']}")
            else:
                print("[요약] 건너뜀 (ANTHROPIC_API_KEY 없음)")
        except Exception as exc:
            notes.append(f"요약 실패: {type(exc).__name__}")
            print(f"[요약] 실패: {type(exc).__name__}")
        result["generator"]["notes"] = notes

    if args.dry:
        # 저장하지 않는다. 한 번 이걸 빠뜨려서 멀쩡한 보드를 빈 것으로 덮어썼다.
        # 외부 호출을 안 하는 모드가 결과물을 파괴하면 안전장치가 아니라 사고다.
        print()
        print("[dry] 저장하지 않았습니다. 기존 보드는 그대로입니다.")
        for s_ in result["sections"]:
            print(f"        {s_['title']}: {len(s_['cards'])}개")
        return 0

    path = board_mod.write(result, BOARDS)
    budget.save()

    counts = result["generator"]["counts"]
    print(f"\n[완료] {path}")
    print(f"        상태 {result['status']} · 수집 {counts['collected']} "
          f"→ 묶음 {counts['clustered']} → 게시 {counts['published']}")
    for s in result["sections"]:
        mark = f"{len(s['cards'])}개" if s["cards"] else f"비어 있음 — {s['empty_reason']}"
        print(f"        {s['title']}: {mark}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
