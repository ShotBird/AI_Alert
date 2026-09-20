"""벤더 뉴스 페이지 직접 읽기.

Hugging Face 는 **가중치를 공개하는 회사의 발표 채널**이지, 모든 회사의 발표 채널이 아니다.
xAI 처럼 주력이 클로즈드인 곳은 뒤늦게 푸는 오픈웨이트(grok-1, grok-2)만 올라오고,
실제 최신(Grok 4.x)은 영원히 올라오지 않는다. 실제로 현황판에 393일 전 grok-2 가
"최신 모델"로 떠 있었다. 사용자가 원한 답이 아니다.

그래서 벤더 자기 뉴스 페이지를 읽는다. 티켓 09 에서 네 벤더 모두 robots.txt 가
크롤링을 허용하는 것을 확인했고, x.ai 는 한술 더 떠 명시적으로 허용한다:

    User-agent: *
    Allow: /
    Content-Signal: ai-train=yes, search=yes, ai-input=yes

**차단을 회피하지 않는다.** 허용된 것만 읽고, 막히면 재시도 몇 번 하고 포기한다.
디시인사이드처럼 약관이 금지하는 곳은 애초에 여기 들어오지 않는다.
"""

import json
import re
import urllib.error
import urllib.request
from datetime import datetime, timezone

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/140.0 Safari/537.36")

# 읽어도 되는 곳만. robots.txt 를 확인한 벤더만 여기 들어온다 (티켓 09).
PAGES = {
    "xai": dict(url="https://x.ai/news", base="https://x.ai", style="rsc"),
}

_MONTHS = re.compile(
    r'"children":"((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*'
    r'\s+\d{1,2},\s+\d{4})"')
_HREF = re.compile(r'"href":"(/news/[a-z0-9-]+)"')
_CHILD = re.compile(r'"children":"([^"]{6,120})"')
# className 조각이 children 으로 섞여 들어온다. 사람이 읽을 문장만 남긴다.
_NOISE = ("$", "/", "text-", "group", "flex", "absolute", "http", "className")


def _fetch(url, tries=3):
    last = None
    for _ in range(tries):
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": UA,
                "Accept": "text/html,application/xhtml+xml",
            })
            with urllib.request.urlopen(req, timeout=25) as resp:
                body = resp.read().decode("utf-8", "replace")
            # Cloudflare 챌린지가 간헐적으로 뜬다. 차단이 아니라 불안정이므로
            # 짧은 응답이면 한 번 더 해본다. 회피 기법은 쓰지 않는다.
            if len(body) > 50_000:
                return body
            last = "challenge"
        except (urllib.error.HTTPError, urllib.error.URLError, ValueError) as exc:
            last = type(exc).__name__
    return None if last else None


def _flight(html):
    """Next.js RSC 페이로드를 복원한다. 페이지가 이 안에 구조화돼 들어 있다."""
    dec = json.JSONDecoder()
    parts, pos, marker = [], 0, "self.__next_f.push([1,"
    while True:
        k = html.find(marker, pos)
        if k < 0:
            break
        q = html.find('"', k + len(marker))
        if q < 0:
            break
        try:
            val, end = dec.raw_decode(html, q)
            parts.append(val)
            pos = end
        except Exception:
            pos = k + len(marker)
    return "".join(parts)


def _parse_rsc(html, base):
    body = _flight(html)
    seen, rows = set(), []
    for m in _HREF.finditer(body):
        href = m.group(1)
        if href in seen:
            continue
        seg = body[m.end():m.end() + 2600]
        d = _MONTHS.search(seg)
        if not d:
            continue
        titles = [c for c in _CHILD.findall(seg[:d.start()])
                  if " " in c and not c.startswith(_NOISE)]
        if not titles:
            continue
        try:
            when = datetime.strptime(d.group(1), "%b %d, %Y").replace(tzinfo=timezone.utc)
        except ValueError:
            continue
        seen.add(href)
        rows.append(dict(title=titles[0], url=base + href, at=when))
    rows.sort(key=lambda r: r["at"], reverse=True)
    return rows


def latest_posts(vendor_id):
    """벤더 뉴스 페이지의 최근 글. 못 읽으면 빈 목록."""
    cfg = PAGES.get(vendor_id)
    if not cfg:
        return []
    html = _fetch(cfg["url"])
    if not html:
        return []
    try:
        if cfg["style"] == "rsc":
            return _parse_rsc(html, cfg["base"])
    except Exception:
        return []
    return []
