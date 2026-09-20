"""수집 대상 목록.

티켓 01에서 **실제로 호출해 확인한 것만** 들어 있다. 보고만 된 것은 넣지 않는다.
VentureBeat(봇 차단)와 ZDNet Korea(2020년 기사를 캐시로 반환)는 그래서 빠져 있다.
"""

# region: "global" | "kr" — 해외/국내 구분. 보드에서 지역별로 갈라 보여준다.
#         국내 소스가 적다고 해외에 묻히면 "한국에서 뭐가 뜨나"를 못 본다.
# kind:
#   rss   — RSS 2.0 (<item>/<pubDate>)
#   atom  — Atom (<entry>/<updated>)
#   hn    — Hacker News Algolia 검색 API (점수·댓글수가 응답에 들어 있다)
#   hf    — Hugging Face 모델 API (신규 모델 출시 신호)
#   hfpaper — Hugging Face Daily Papers (추천수가 달린 실제 커뮤니티 활동)
SOURCES = [
    # ── 모델 업데이트 ────────────────────────────────────────────────────────
    dict(id="openai", region="global", name="OpenAI", section="model_updates", kind="rss",
         url="https://openai.com/news/rss.xml"),
    dict(id="google_blog", region="global", name="Google", section="model_updates", kind="rss",
         url="https://blog.google/rss/"),
    dict(id="mistral", region="global", name="Mistral", section="model_updates", kind="rss",
         # 공식 문서에 없지만 실제로 동작한다 (티켓 01에서 확인)
         url="https://mistral.ai/news/rss"),
    dict(id="anthropic_mirror", region="global", name="Anthropic", section="model_updates", kind="rss",
         # 커뮤니티 미러. 오늘도 갱신되고 있음을 확인했으나 남의 개인 프로젝트라
         # 단일 장애점이다. 죽으면 anthropic.com 직접 파싱으로 넘어간다 (티켓 09).
         url="https://raw.githubusercontent.com/taobojlen/anthropic-rss-feed/main/anthropic_news_rss.xml"),
    dict(id="hf_deepseek", region="global", name="Hugging Face", section="model_updates", kind="hf",
         url="https://huggingface.co/api/models?author=deepseek-ai&sort=createdAt&direction=-1&limit=8"),
    dict(id="hf_qwen", region="global", name="Hugging Face", section="model_updates", kind="hf",
         url="https://huggingface.co/api/models?author=Qwen&sort=createdAt&direction=-1&limit=8"),
    dict(id="hf_meta", region="global", name="Hugging Face", section="model_updates", kind="hf",
         url="https://huggingface.co/api/models?author=meta-llama&sort=createdAt&direction=-1&limit=8"),

    # ── 뉴스 ────────────────────────────────────────────────────────────────
    dict(id="techcrunch_ai", region="global", name="TechCrunch", section="top_headlines", kind="rss",
         url="https://techcrunch.com/category/artificial-intelligence/feed/"),
    dict(id="verge_ai", region="global", name="The Verge", section="top_headlines", kind="atom",
         url="https://www.theverge.com/rss/ai-artificial-intelligence/index.xml"),
    dict(id="ars_ai", region="global", name="Ars Technica", section="top_headlines", kind="rss",
         url="https://arstechnica.com/ai/feed/"),
    dict(id="techmeme", region="global", name="Techmeme", section="top_headlines", kind="rss",
         url="https://www.techmeme.com/feed.xml"),
    dict(id="hn", region="global", name="Hacker News", section="top_headlines", kind="hn",
         url="https://hn.algolia.com/api/v1/search?tags=story&hitsPerPage=60&query=AI"),
    dict(id="geeknews", region="kr", name="GeekNews", section="top_headlines", kind="atom",
         url="https://news.hada.io/rss/news"),
    dict(id="etnews_ai", region="kr", name="전자신문", section="top_headlines", kind="rss", tz=9,
         # 티켓 01에서 주소를 정정했다. rss.etnews.co.kr 은 인증서가 맞지 않는다.
         url="http://rss.etnews.com/04046.xml"),
    # pubDate 에 시간대가 없다 (2026-09-20 17:40:45). KST 로 읽지 않으면
    # 기사들이 몇 시간 "미래"가 되어 화제도를 독식한다.
    dict(id="aitimes", region="kr", name="AI타임스", section="top_headlines", kind="rss", tz=9,
         url="https://www.aitimes.com/rss/allArticle.xml"),

    # ── 커뮤니티 활동 ────────────────────────────────────────────────────────
    # HF Daily Papers 는 추천수가 달린 실제 커뮤니티 신호다. 모델 API 와 달리
    # "사람들이 오늘 뭘 읽고 있나"를 보여준다.
    dict(id="hf_papers", region="global", name="Hugging Face", section="top_headlines",
         kind="hfpaper", url="https://huggingface.co/api/daily_papers?limit=30"),
]

# 모델 업데이트 섹션의 벤더 필터.
# 티켓 09의 발견: 회사명으로 걸면 소송·인사·정치 기사가 딸려오고,
# 제품명으로 걸어야 실제 출시가 잡힌다.
PRODUCT_TERMS = [
    "claude", "gpt", "gemini", "grok", "llama", "deepseek",
    "qwen", "mistral", "sonnet", "opus", "haiku", "o3", "o4",
]

# "이건 모델 얘기다"를 알려주는 말. 고정된 제품명 목록만으로는
# StepFun·Kimi·GLM 처럼 목록에 없는 벤더의 출시를 영원히 못 잡는다.
MODEL_WORDS = [
    "모델", "model", "llm", "preview", "weights", "가중치",
    "checkpoint", "파라미터", "parameter", "-b ", "b 모델",
]

# 출시를 알리는 말. 제품명이나 모델 단어와 함께 나와야 인정한다.
RELEASE_HINTS = [
    "introduc", "launch", "releas", "announc", "unveil", "ship",
    "now available", "available now", "출시", "공개", "발표",
    "-v", "1.0", "2.0", "3.0", "4.0", "5.0",
]
