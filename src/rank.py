"""화제도: 묶음이 지금 얼마나 회자되고 있는지를 하나의 수로.

CONTEXT.md 가 정한 근거 세 가지를 중요도 순으로 그대로 옮긴 것이다.

  ① 서로 다른 출처의 개수   ② 반응 수치   ③ 시간 감쇠

①이 가장 무거운 이유는 품질 판단이 아니라 데이터 제약이다. 수집원 대부분(RSS)은
개별 항목의 추천수를 주지 않는다. 티켓 01에서 실측했듯 반응 수치가 있는 곳은
Hacker News, Hugging Face, GitHub 뿐이다. 여러 곳이 동시에 말한다는 사실이
우리가 가진 유일하게 보편적인 신호다.

계수는 잠정값이다. 실제 데이터를 며칠 모아 조정한다 (지도의 안개 항목).
"""

import math
from datetime import datetime, timezone

W_SOURCES = 3.0     # 출처 개수 — 가장 무겁다
W_ENGAGE = 1.0      # 반응 수치 — 있는 항목만
RELEASE_BONUS = 2.5 # 출시로 보이는 항목 가점
HALF_LIFE_H = 20.0  # 반감기. 하루 한 번 보는 물건이라 HN 만큼 급하게 꺾을 이유가 없다


def heat(cluster, now=None):
    now = now or datetime.now(timezone.utc)

    corroboration = math.log2(1 + cluster["source_count"])

    engagement = cluster.get("engagement") or 0
    comments = cluster.get("comments") or 0
    # 로그로 눌러 첫 10개 추천이 그다음 100개만큼 값어치를 갖게 한다 (Reddit 방식)
    reaction = math.log10(1 + engagement + 2 * comments)

    published = cluster.get("published_at")
    if published:
        age_h = max(0.0, (now - published).total_seconds() / 3600.0)
    else:
        # 날짜가 없는 피드가 실제로 있다. 모르면 중간값으로 둔다.
        # 최신으로 쳐주면 날짜 없는 소스가 상위를 독식한다.
        age_h = HALF_LIFE_H

    # 감쇠는 뺄셈이 아니라 배율이다. 뺄셈으로 하면 오래된 항목이 음수가 되는데,
    # 음수 화제도는 뜻이 없고 정렬만 망가뜨린다.
    freshness = 0.5 ** (age_h / HALF_LIFE_H)

    base = W_SOURCES * corroboration + W_ENGAGE * reaction
    # 출시는 드물다. 버리지 않고 가점을 줘서 위로 올린다 —
    # 버리면 섹션이 매일 한두 칸이 되고, 그건 고장난 화면처럼 보인다.
    if cluster.get("is_release"):
        base += RELEASE_BONUS
    return round(base * freshness, 2)


def rank(clusters, now=None):
    for c in clusters:
        c["heat"] = heat(c, now)
    clusters.sort(key=lambda c: c["heat"], reverse=True)
    return clusters
