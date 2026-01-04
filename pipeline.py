import hashlib
from datetime import datetime, timezone
from typing import Dict, List

from news_client import fetch_news
from summarizer import summarize
from sentiment import sentiment
from text_utils import normalize_text


def _hash_id(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def build_dataset(query: str, language: str, articles_raw: List[Dict]) -> Dict:
    items = []
    for article in articles_raw:
        text = normalize_text(article)
        summary = summarize(text)
        senti = sentiment(text)

        url = article.get("url") or ""
        title = article.get("title") or ""
        id_source = url or title

        items.append(
            {
                "id": _hash_id(id_source),
                "title": title,
                "url": url,
                "source": article.get("source") or "",
                "publishedAt": article.get("publishedAt") or "",
                "text": text,
                "summary": summary,
                "sentiment": senti,
            }
        )

    return {
        "query": query,
        "language": language,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "articles": items,
    }


def run_pipeline(query: str, page_size: int, language: str, sort_by: str = "publishedAt") -> Dict:
    raw = fetch_news(query, page_size=page_size, language=language, sort_by=sort_by)
    return build_dataset(query, language, raw)
