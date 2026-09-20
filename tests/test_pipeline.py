"""파이프라인 검증. `python tests/test_pipeline.py` 로 돌린다.

외부 호출을 하지 않는다. 저장된 응답과 손으로 만든 항목만 쓴다.
개발 중 실수로 실제 API를 때려 예산을 태우는 일을 막기 위한 것이기도 하다.

여기서 지키려는 것은 "코드가 돌아간다"가 아니라 **실제로 났던 사고가 다시 나지 않는다**이다.
그래서 각 테스트는 무엇이 어떻게 잘못됐었는지를 이름과 주석에 남긴다.
"""

import os
import sys
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from src.board import MAX_PER_SOURCE, build          # noqa: E402
from src.budget import Budget, BudgetExceeded, BudgetUnavailable  # noqa: E402
from src.cluster import build_clusters, canonical_url  # noqa: E402
from src.collect import _parse_date                  # noqa: E402
from src.rank import heat                            # noqa: E402

NOW = datetime(2026, 9, 20, 12, 0, tzinfo=timezone.utc)
PASS, FAIL = [], []


def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    mark = "  ok" if cond else "FAIL"
    print(f"[{mark}] {name}" + (f"  — {detail}" if detail and not cond else ""))


def item(title, url, source="TechCrunch", sid="techcrunch_ai",
         section="top_headlines", age_h=1, engagement=0, comments=0):
    return dict(title=title, url=url, source_name=source, source_id=sid,
                section=section, published_at=NOW - timedelta(hours=age_h),
                engagement=engagement, comments=comments)


# ── 날짜 ────────────────────────────────────────────────────────────────────
# 사고: AI타임스가 시간대 없는 pubDate 를 준다. UTC 로 읽으면 기사가 미래가 되고,
# 미래 항목은 최신성 만점을 받아 뉴스 5칸을 통째로 가져갔다.
naive = _parse_date("2026-09-20 17:40:45", tz_hours=9)
check("시간대 없는 날짜를 KST 로 읽는다",
      naive is not None and naive.hour == 8,
      f"got {naive}")

future = _parse_date("2099-01-01T00:00:00Z")
check("미래 날짜는 현재로 눌린다",
      future is not None and future <= datetime.now(timezone.utc),
      f"got {future}")

check("깨진 날짜는 조용히 None", _parse_date("어제쯤") is None)


# ── URL 정규화 ──────────────────────────────────────────────────────────────
check("추적 파라미터를 뗀다",
      canonical_url("https://a.com/x?utm_source=rss&id=3") ==
      canonical_url("https://www.a.com/x/?id=3"))


# ── 묶음 ────────────────────────────────────────────────────────────────────
same = build_clusters([
    item("OpenAI launches GPT-6 for enterprise", "https://a.com/1", "TechCrunch"),
    item("OpenAI launches GPT-6 for enterprise", "https://b.com/2", "Ars Technica"),
])
check("같은 제목은 한 묶음", len(same) == 1 and same[0]["source_count"] == 2,
      f"{len(same)} clusters")

diff = build_clusters([
    item("OpenAI launches GPT-6", "https://a.com/1", "TechCrunch"),
    item("Apple unveils new MacBook Pro", "https://b.com/2", "Ars Technica"),
])
check("다른 사건은 합치지 않는다", len(diff) == 2, f"{len(diff)} clusters")

dup_source = build_clusters([
    item("Same story", "https://a.com/1", "TechCrunch"),
    item("Same story", "https://b.com/2", "TechCrunch"),
])
check("같은 출처는 두 번 세지 않는다", dup_source[0]["source_count"] == 1)


# ── 화제도 ──────────────────────────────────────────────────────────────────
# 사고: 감쇠를 뺄셈으로 해서 오래된 항목이 -18 까지 내려갔다. 음수 화제도는 뜻이 없다.
old = dict(source_count=1, engagement=0, comments=0,
           published_at=NOW - timedelta(days=60))
check("오래된 항목도 화제도가 음수가 아니다", heat(old, NOW) >= 0, f"{heat(old, NOW)}")

many = dict(source_count=5, engagement=0, comments=0, published_at=NOW)
few = dict(source_count=1, engagement=500, comments=100, published_at=NOW)
check("여러 출처가 단일 출처의 높은 추천수를 이긴다",
      heat(many, NOW) > heat(few, NOW),
      f"{heat(many, NOW)} vs {heat(few, NOW)}")

fresh = dict(source_count=2, engagement=0, comments=0, published_at=NOW)
stale = dict(source_count=2, engagement=0, comments=0,
             published_at=NOW - timedelta(hours=40))
check("같은 조건이면 최신이 이긴다", heat(fresh, NOW) > heat(stale, NOW))

released = dict(source_count=1, engagement=0, comments=0,
                published_at=NOW, is_release=True)
plain = dict(source_count=1, engagement=0, comments=0, published_at=NOW)
check("출시 표시는 가점을 받는다", heat(released, NOW) > heat(plain, NOW))


# ── 보드 조립 ───────────────────────────────────────────────────────────────
# 사고: AI타임스 하나가 뉴스 5칸을 다 먹었다. 그건 보드가 아니라 그 매체의 목차다.
flood = build_clusters([item(f"AI타임스 기사 {i}", f"https://ait.com/{i}",
                             "AI타임스", "aitimes") for i in range(8)])
for c in flood:
    c["heat"] = heat(c, NOW)
board = build({"top_headlines": flood}, [], [dict(id="aitimes", ok=True, items=8)],
              {}, os.path.join(HERE, "_tmp_boards"), NOW)
news = [s for s in board["sections"] if s["id"] == "top_headlines"][0]
check("한 매체가 섹션을 독식하지 못한다",
      len(news["cards"]) <= MAX_PER_SOURCE,
      f"{len(news['cards'])} cards from one source")

empty = build({}, [], [], {}, os.path.join(HERE, "_tmp_boards"), NOW)
check("빈 섹션은 사라지지 않고 이유를 남긴다",
      all(s["cards"] or s["empty_reason"] for s in empty["sections"]))
check("섹션 수는 계약대로 유지된다", len(empty["sections"]) >= 4)

# 본문을 싣지 않는다는 약속. 이게 깨지면 모바일 데이터로 받기 어려워진다.
card_keys = set()
for s in board["sections"]:
    for c in s["cards"]:
        card_keys |= set(c)
check("카드에 본문·발췌문이 없다",
      not (card_keys & {"body", "content", "excerpt", "description"}),
      f"extra keys: {card_keys}")


# ── 예산 ────────────────────────────────────────────────────────────────────
tmp = os.path.join(HERE, "_tmp_budget.json")
if os.path.exists(tmp):
    os.remove(tmp)
b = Budget(tmp)
b.check("tranco")
b.spend("tranco", 40)
try:
    b.check("tranco")
    check("상한에 닿으면 막는다", False, "예외가 안 났다")
except BudgetExceeded:
    check("상한에 닿으면 막는다", True)

# 가장 중요한 성질: 카운터를 못 읽으면 호출하지 않는다.
try:
    Budget(os.path.join(HERE, "_nope", "\0bad", "x.json"))
    check("카운터를 못 읽으면 멈춘다 (fail-closed)", False, "예외가 안 났다")
except BudgetUnavailable:
    check("카운터를 못 읽으면 멈춘다 (fail-closed)", True)
except Exception as exc:
    check("카운터를 못 읽으면 멈춘다 (fail-closed)", False, type(exc).__name__)

for path in (tmp, os.path.join(HERE, "_tmp_boards")):
    try:
        if os.path.isdir(path):
            for f in os.listdir(path):
                os.remove(os.path.join(path, f))
            os.rmdir(path)
        elif os.path.exists(path):
            os.remove(path)
    except OSError:
        pass

print(f"\n{len(PASS)} 통과 / {len(FAIL)} 실패")
if FAIL:
    print("실패:", ", ".join(FAIL))
raise SystemExit(1 if FAIL else 0)
