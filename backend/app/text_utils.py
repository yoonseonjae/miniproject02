import re
from typing import Dict


def normalize_text(article_raw: Dict) -> str:
    parts = []
    for key in ("title", "description", "content"):
        value = article_raw.get(key)
        if value:
            parts.append(str(value))

    merged = " ".join(parts)
    merged = re.sub(r"\s+", " ", merged).strip()
    return merged
