import os
from typing import Dict, List

import requests


def fetch_news(query: str, page_size: int = 5, language: str = "en", sort_by: str = "publishedAt") -> List[Dict]:
    api_key = os.getenv("NEWS_API_KEY")
    if not api_key:
        raise ValueError("NEWS_API_KEY 환경 변수가 필요합니다.")

    url = "https://newsapi.org/v2/everything"
    params = {
        "q": query,
        "pageSize": page_size,
        "language": language,
        "sortBy": sort_by,
        "apiKey": api_key,
    }

    try:
        response = requests.get(url, params=params, timeout=15)
        response.raise_for_status()
    except requests.RequestException as exc:
        raise RuntimeError(f"뉴스 API 요청 실패: {exc}") from exc

    data = response.json()
    if data.get("status") != "ok":
        raise RuntimeError(data.get("message", "알 수 없는 API 오류"))

    articles = []
    for item in data.get("articles", []):
        source_name = ""
        source = item.get("source")
        if isinstance(source, dict):
            source_name = source.get("name") or ""

        articles.append(
            {
                "title": item.get("title"),
                "description": item.get("description"),
                "content": item.get("content"),
                "url": item.get("url"),
                "source": source_name,
                "publishedAt": item.get("publishedAt"),
            }
        )

    return articles
