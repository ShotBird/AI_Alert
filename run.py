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

from src import board as board_mod            # noqa: E402
from src import collect as collect_mod        # noqa: E402
from src import github_skills                 # noqa: E402
from src.budget import Budget, BudgetUnavailable   # noqa: E402
from src.cluster import build_clusters        # noqa: E402
from src.rank import rank                     # noqa: E402
from src.sources import PRODUCT_TERMS, RELEASE_HINTS, SOURCES  # noqa: E402

BOARDS = os.path.join(HERE, "boards")
COUNTER = os.path.join(HERE, "state", "api-usage.json")


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
    제품명으로 걸어야 실제 출시가 잡힌다. 그래서 제품명을 먼저 본다.
    """
    low = title.lower()
    if not any(term in low for term in PRODUCT_TERMS):
        return False
    return any(hint in low for hint in RELEASE_HINTS)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true",
                    help="외부 호출 없이 직전 보드만 다시 조립한다")
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

    # 날짜 창. 피드가 과거 아카이브를 통째로 주는 경우가 있어서
    # (OpenAI 는 1,200건을 준다) 이게 없으면 몇 달 전 글이 오늘 것과 경쟁한다.
    cutoff = now - timedelta(days=args.days)
    fresh = [i for i in items
             if i.get("published_at") is None or i["published_at"] >= cutoff]
    stale_n = len(items) - len(fresh)
    if stale_n:
        print(f"[기간] {args.days}일 밖 {stale_n}건 제외 · 남은 항목 {len(fresh)}개")
    items = fresh

    # 출시로 보이는 항목에 표시를 단다. 거르지는 않는다 —
    # 실제 출시는 하루 한두 건이라 걸러버리면 섹션이 빈다.
    # 대신 화제도에서 가점을 받아 위로 올라간다.
    releases = 0
    for item in items:
        if item["source_id"].startswith("hf_") or looks_like_release(item["title"]):
            item["is_release"] = True
            releases += 1
    print(f"[선별] 출시로 보이는 항목 {releases}건에 가점")

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
                token, budget, candidates=40 if token else 20)
            notes.extend(gh_notes)
            print(f"[GitHub] 급상승 {len(github_rows)}개")
        except Exception as exc:
            notes.append(f"GitHub 섹션 실패: {type(exc).__name__}")
            print(f"[GitHub] 실패: {type(exc).__name__}")

    result = board_mod.build(by_section, github_rows, status,
                             budget.report(), BOARDS, now, notes)
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
