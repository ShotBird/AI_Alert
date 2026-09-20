"""올해 모델 출시 마일스톤.

현황판([vendors.py])과 **다른 질문에 답한다.** 현황판은 "지금 각 계열의 최신이 무엇인가"고,
여기는 "올해 이 판이 어떻게 흘러왔나"다. 그래서 현황판은 계열당 한 줄이지만
마일스톤은 같은 계열의 과거 출시까지 연중으로 편다.

추가 수집이 없다. vendors.py 가 이미 긁어온 후보를 그대로 쓴다 —
Hugging Face 회사별 목록, 벤더 자기 페이지, 수집한 피드의 출시 항목.

**모델명만 싣는다.** 발표 제목을 그대로 실으면 1년 축이 글자로 덮인다.
"""

from datetime import datetime, timezone

from . import vendors


def _month_day(dt):
    return f"{dt.month}/{dt.day}"


def build(items, now=None, max_points=40):
    """(마일스톤 점 목록, notes). 올해 1/1 부터 오늘까지."""
    now = now or datetime.now(timezone.utc)
    year_start = datetime(now.year, 1, 1, tzinfo=timezone.utc)

    seen, points = set(), []
    for vendor in vendors.VENDORS:
        cands = vendors._all_candidates(vendor, items)
        for fam in (vendor.get("families") or []):
            for cand in cands:
                name = cand.get("name") or ""
                at = cand.get("at")
                if at is None or at < year_start or at > now:
                    continue
                # 현황판과 같은 판정을 쓴다. 기능 소식·홍보글이 축에 오르지 않는다.
                if not vendors._is_family_release(name, fam):
                    continue
                model = vendors._model_name(name, fam)
                # 같은 날 같은 모델이 여러 경로로 들어온다 (HF + 발표문 + 뉴스).
                # HF 는 `Qwen/Qwen-Image-2.1` 로, 발표문은 `Qwen-Image-2.1` 로 오므로
                # 소유자 접두사를 떼고 비교해야 한 점으로 합쳐진다.
                bare = model.split("/")[-1].lower()
                key = (vendor["name"], bare, at.date())
                if key in seen:
                    continue
                seen.add(key)
                points.append(dict(
                    vendor=vendor["name"],
                    family=fam,
                    model=model.split("/")[-1],
                    date=at.date().isoformat(),
                    label=_month_day(at),
                    url=cand.get("url"),
                    day_of_year=at.timetuple().tm_yday,
                ))

    points.sort(key=lambda p: p["date"])

    # 축이 빽빽해지면 읽을 수 없다. 최근 것을 남긴다 — 올해 흐름은
    # 연초보다 최근 몇 달이 더 궁금하다.
    trimmed = points[-max_points:] if len(points) > max_points else points

    notes = []
    if len(points) > len(trimmed):
        notes.append(f"올해 출시 {len(points)}건 중 최근 {len(trimmed)}건만 축에 올렸습니다.")
    if not trimmed:
        notes.append("올해 축에 올릴 모델 출시를 찾지 못했습니다.")

    return dict(
        year=now.year,
        today_day_of_year=now.timetuple().tm_yday,
        total_days=366 if (now.year % 4 == 0 and now.year % 100 != 0)
                   or now.year % 400 == 0 else 365,
        points=trimmed,
    ), notes
