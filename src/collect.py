"""수집: 소스를 돌며 항목(Item)으로 정규화한다.

용어는 CONTEXT.md를 따른다. 여기서 만드는 것은 **항목**이고, 보드에 실리는 **묶음**이 아니다.

소스 하나가 죽어도 나머지는 계속 간다. 죽은 소스는 조용히 사라지지 않고
`sources_status`에 이유와 함께 남는다 — 사라진 소스는 버그처럼 보이고,
이유가 적힌 실패는 알려진 구멍처럼 보인다.
"""

import json
import html
import re
import socket
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/140.0 Safari/537.36")
TIMEOUT = 25

TAG_RE = re.compile(r"<[^>]+>")
WS_RE = re.compile(r"\s+")


def _clean(text):
    if not text:
        return ""
    text = TAG_RE.sub(" ", text)
    # 손으로 고른 엔티티 목록은 늘 모자란다 — 실제로 `&#x27;`(16진 작은따옴표)가
    # 요약에 그대로 남아 화면에 나왔다. 표준 디코더에 맡긴다.
    text = html.unescape(text)
    return WS_RE.sub(" ", text).strip()


# 제목만 들고 오던 시절, "다음 예정"을 찾을 텍스트가 아예 없었다. 루머 기사의
# 제목은 "Meta to give Muse its own mailbox" 처럼 미래형만 있고 **날짜는 본문에
# 있다.** 그래서 요약을 함께 싣는다. 다만 본문 전체를 들고 다니면 수집물이
# 수십 MB 가 되므로 앞부분만 자른다 — 날짜는 보통 리드 문단에 나온다.
SUMMARY_CHARS = 400


def _summary(text):
    return _clean(text)[:SUMMARY_CHARS]


def fetch(url):
    req = urllib.request.Request(url, headers={
        "User-Agent": UA,
        "Accept": "application/rss+xml, application/atom+xml, application/json, text/xml, */*",
    })
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        return resp.read()


def _parse_date(raw, tz_hours=0):
    if not raw:
        return None
    raw = raw.strip()
    try:
        dt = parsedate_to_datetime(raw)          # RFC 822 (RSS)
    except Exception:
        try:
            dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))  # ISO (Atom/JSON)
        except Exception:
            return None
    if dt.tzinfo is None:
        # 시간대가 없는 피드가 있다. 소스가 알려준 기본 시간대로 읽는다.
        dt = dt.replace(tzinfo=timezone(timedelta(hours=tz_hours)))
    dt = dt.astimezone(timezone.utc)
    # 그래도 미래면 표기가 틀린 것이다. 미래 항목이 최신성 만점을 받아
    # 섹션을 독식하는 일을 막는다.
    now = datetime.now(timezone.utc)
    return min(dt, now)


def _strip_ns(tag):
    return tag.rsplit("}", 1)[-1]


def _items_rss(raw, tz=0):
    root = ET.fromstring(raw)
    out = []
    for node in root.iter():
        if _strip_ns(node.tag) != "item":
            continue
        d = {}
        for child in node:
            d.setdefault(_strip_ns(child.tag), child.text)
        out.append(dict(
            title=_clean(d.get("title")),
            url=(d.get("link") or "").strip(),
            published_at=_parse_date(d.get("pubDate") or d.get("date"), tz),
            summary=_summary(d.get("description") or d.get("summary")
                             or d.get("encoded")),
        ))
    return out


def _items_atom(raw, tz=0):
    root = ET.fromstring(raw)
    out = []
    for node in root.iter():
        if _strip_ns(node.tag) != "entry":
            continue
        title, url, when, summary = "", "", None, ""
        for child in node:
            tag = _strip_ns(child.tag)
            if tag == "title":
                title = _clean(child.text)
            elif tag == "link" and not url:
                url = (child.get("href") or child.text or "").strip()
            elif tag in ("updated", "published") and when is None:
                when = _parse_date(child.text, tz)
            elif tag in ("summary", "content") and not summary:
                summary = _summary(child.text)
        out.append(dict(title=title, url=url, published_at=when, summary=summary))
    return out


def _items_hn(raw, tz=0):
    data = json.loads(raw)
    out = []
    for hit in data.get("hits", []):
        title = _clean(hit.get("title") or hit.get("story_title"))
        if not title:
            continue
        url = hit.get("url") or f"https://news.ycombinator.com/item?id={hit.get('objectID')}"
        out.append(dict(
            title=title,
            url=url,
            published_at=_parse_date(hit.get("created_at"), tz),
            engagement=hit.get("points") or 0,
            comments=hit.get("num_comments") or 0,
        ))
    return out


def _items_hf(raw, tz=0):
    data = json.loads(raw)
    out = []
    for m in data:
        rid = m.get("id") or ""
        if not rid:
            continue
        out.append(dict(
            title=rid,
            url=f"https://huggingface.co/{rid}",
            published_at=_parse_date(m.get("createdAt"), tz),
            engagement=m.get("likes") or 0,
        ))
    return out


def _items_hfpaper(raw, tz=0):
    """Hugging Face Daily Papers. 추천수가 달려 있어 반응 수치로 쓸 수 있다."""
    data = json.loads(raw)
    out = []
    for row in data or []:
        paper = row.get("paper") or {}
        title = _clean(paper.get("title"))
        pid = paper.get("id") or ""
        if not title or not pid:
            continue
        out.append(dict(
            title=title,
            url=f"https://huggingface.co/papers/{pid}",
            published_at=_parse_date(row.get("publishedAt"), tz),
            engagement=paper.get("upvotes") or 0,
        ))
    return out


PARSERS = {"rss": _items_rss, "atom": _items_atom, "hn": _items_hn,
           "hf": _items_hf, "hfpaper": _items_hfpaper}


def collect(sources):
    """모든 소스를 돌며 (항목 목록, 소스별 상태)를 돌려준다."""
    items, status = [], []
    for src in sources:
        try:
            raw = fetch(src["url"])
            parsed = PARSERS[src["kind"]](raw, src.get("tz", 0))
        except (urllib.error.HTTPError, urllib.error.URLError,
                socket.timeout, ET.ParseError, ValueError, json.JSONDecodeError) as exc:
            status.append(dict(id=src["id"], ok=False, items=0,
                               error=type(exc).__name__))
            continue
        except Exception as exc:           # 예상 못 한 것도 소스 하나로 끝낸다
            status.append(dict(id=src["id"], ok=False, items=0,
                               error=f"unexpected: {type(exc).__name__}"))
            continue

        good = 0
        for p in parsed:
            if not p.get("title") or not p.get("url"):
                continue
            items.append(dict(
                title=p["title"],
                url=p["url"],
                source_id=src["id"],
                source_name=src["name"],
                section=src["section"],
                region=src.get("region", "global"),
                published_at=p.get("published_at"),
                engagement=p.get("engagement") or 0,
                comments=p.get("comments") or 0,
                # 제목에는 미래형만 있고 날짜는 본문에 있다. 여기서 떨어뜨리면
                # '다음 예정'이 볼 수 있는 글자가 제목뿐이 된다 — 실제로 그랬다.
                summary=p.get("summary") or "",
                # 미출시 전문 매체인가. "prepares/tests/is working on" 같은
                # 현재형을 '아직 안 나왔다'로 읽어도 되는 곳인지 가른다.
                rumor=bool(src.get("rumor")),
            ))
            good += 1
        status.append(dict(id=src["id"], ok=True, items=good))
    return items, status
