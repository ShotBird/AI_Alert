"""올해 모델 출시 마일스톤.

현황판([vendors.py])과 **다른 질문에 답한다.** 현황판은 "지금 각 계열의 최신이 무엇인가"고,
여기는 "올해 이 판이 어떻게 흘러왔나"다. 그래서 현황판은 계열당 한 줄이지만
마일스톤은 같은 계열의 과거 출시까지 연중으로 편다.

추가 수집이 없다. vendors.py 가 이미 긁어온 후보를 그대로 쓴다 —
Hugging Face 회사별 목록, 벤더 자기 페이지, 수집한 피드의 출시 항목.

**모델명만 싣는다.** 발표 제목을 그대로 실으면 1년 축이 글자로 덮인다.
"""

from datetime import date, datetime, timezone

from . import vendors


def _month_day(dt):
    return f"{dt.month}/{dt.day}"


def _family_in(text, vendor):
    """헤드라인에 이름이 보이는 계열. 계열이 없으면 제품명이라도 찾는다.

    Anthropic 의 계열은 Opus·Sonnet·Haiku… 인데 기사는 "신형 Claude 모델" 이라고
    쓴다. 계열만 찾다 못 찾으면 `Anthropic (미정)` 이 되는데, 회사 이름을 모델
    자리에 적는 건 답이 아니다. 벤더가 들고 있는 제품 용어까지 본다.
    """
    low = (text or "").lower()
    for fam in (vendor.get("families") or []):
        if fam.lower() in low:
            return fam
    for term in (vendor.get("terms") or []):
        # 한글 표기(앤트로픽)는 모델명 자리에 어울리지 않는다. 영문만 쓴다.
        if term.isascii() and len(term) > 2 and term in low:
            return term.title()
    return None


def _future_points(items, now, year_end):
    """찌라시·예고에서 읽은 **앞으로 나올 것**. 과거 점과 같은 축에 올린다.

    현황판의 '다음 예정' 칸과 같은 판정(`vendors._next_expected`)을 쓴다.
    두 곳이 서로 다른 기준을 쓰면 표에는 있는 일정이 축에는 없는 일이 생긴다.

    날짜를 콕 집은 것은 그 날에, "4분기"처럼 기간만 말한 것은 **기간의 끝**에
    찍는다. 기간 한가운데에 찍으면 있지도 않은 정밀도를 주장하게 된다.
    """
    out = []
    today = now.date()
    for vendor in vendors.VENDORS:
        nxt = vendors._next_expected(vendor, items, now)
        if not nxt:
            continue
        headline = nxt.get("headline") or ""
        when = vendors._pick_when(headline, now)
        if not when:
            continue
        day = None
        if when.get("date"):
            try:
                day = date.fromisoformat(when["date"])
            except ValueError:
                day = None
        if day is None:
            day = when.get("until")
        # 올해 축에 못 올리는 것(내년 얘기, 기간을 못 집는 말)은 싣지 않는다.
        if not isinstance(day, date) or not (today <= day <= year_end):
            continue

        fam = _family_in(headline, vendor)
        model = vendors._model_name(headline, fam) if fam else headline
        # 모델명을 못 집었으면 헤드라인을 통째로 싣지 않는다 — 축이 글자로 덮인다.
        if not fam or model == headline or len(model) > 34:
            model = f"{fam or vendor['name']} (미정)"

        out.append(dict(
            vendor=vendor["name"],
            family=fam,
            model=model.split("/")[-1],
            date=day.isoformat(),
            label=_month_day(day),
            url=nxt.get("url"),
            day_of_year=day.timetuple().tm_yday,
            future=True,
            confidence=nxt.get("confidence") or "예정",
        ))
    return out


def build(items, now=None, max_points=40):
    """(마일스톤 점 목록, notes). 올해 1/1 부터 오늘까지."""
    now = now or datetime.now(timezone.utc)
    year_start = datetime(now.year, 1, 1, tzinfo=timezone.utc)

    seen, points = {}, []
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
                # 같은 모델이 여러 경로로, 그리고 **여러 날에 걸쳐** 들어온다
                # (HF 등록일 + 발표문 + 며칠 뒤 후속 기사). 날짜까지 키에 넣었더니
                # `Grok 4.5` 가 7/16·7/22·7/28 세 줄로 축에 박혔다 — 축이 아니라
                # 기사 목록이 된다. 모델 하나는 점 하나이고, 그 점의 날짜는
                # **가장 이른 날**이다. 그게 출시일에 가장 가깝다.
                #
                # HF 는 `Qwen/Qwen-Image-2.1` 로, 발표문은 `Qwen-Image-2.1` 로 오므로
                # 소유자 접두사를 떼고 비교해야 한 점으로 합쳐진다.
                bare = model.split("/")[-1].lower()
                key = (vendor["name"], bare)
                if key in seen:
                    prev = seen[key]
                    if at < prev["_at"]:
                        prev.update(date=at.date().isoformat(),
                                    label=_month_day(at),
                                    url=cand.get("url"),
                                    day_of_year=at.timetuple().tm_yday,
                                    _at=at)
                    continue
                point = dict(
                    vendor=vendor["name"],
                    family=fam,
                    model=model.split("/")[-1],
                    date=at.date().isoformat(),
                    label=_month_day(at),
                    url=cand.get("url"),
                    day_of_year=at.timetuple().tm_yday,
                    _at=at,
                )
                seen[key] = point
                points.append(point)

    for p in points:
        p.pop("_at", None)
    points.sort(key=lambda p: p["date"])

    # 앞날은 따로 모은다. 과거는 '최근 N건'으로 잘리지만 **예정은 자르지 않는다** —
    # 몇 건 없을 뿐더러, 축에서 가장 궁금한 쪽이 오른쪽이다.
    year_end = date(now.year, 12, 31)
    future = _future_points(items, now, year_end)

    # 축이 빽빽해지면 읽을 수 없다. 최근 것을 남긴다 — 올해 흐름은
    # 연초보다 최근 몇 달이 더 궁금하다.
    trimmed = points[-max_points:] if len(points) > max_points else points

    notes = []
    if len(points) > len(trimmed):
        notes.append(f"올해 출시 {len(points)}건 중 최근 {len(trimmed)}건만 축에 올렸습니다.")
    if not trimmed and not future:
        notes.append("올해 축에 올릴 모델 출시를 찾지 못했습니다.")
    if not future:
        notes.append("앞으로의 출시 예정은 아직 찾지 못했습니다 — "
                     "수집한 글에 날짜를 적은 예고가 없었습니다.")

    trimmed = trimmed + future

    return dict(
        year=now.year,
        note=" · ".join(notes) if notes else None,
        future_count=len(future),
        today_day_of_year=now.timetuple().tm_yday,
        total_days=366 if (now.year % 4 == 0 and now.year % 100 != 0)
                   or now.year % 400 == 0 else 365,
        points=trimmed,
    ), notes
