import json
import os

from openai import OpenAI


_ANALYZER = None
_HF_PIPELINES = {}
_OPENAI_CLIENT = None
_OPENAI_API_KEY = None


def _load_vader():
    global _ANALYZER
    if _ANALYZER is None:
        from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

        _ANALYZER = SentimentIntensityAnalyzer()
    return _ANALYZER


def _get_openai_client():
    global _OPENAI_CLIENT, _OPENAI_API_KEY
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        _OPENAI_CLIENT = None
        _OPENAI_API_KEY = None
        return None
    if _OPENAI_CLIENT is None or _OPENAI_API_KEY != api_key:
        _OPENAI_CLIENT = OpenAI(api_key=api_key)
        _OPENAI_API_KEY = api_key
    return _OPENAI_CLIENT


def _get_openai_model() -> str:
    return os.getenv("OPENAI_MODEL", "gpt-3.5-turbo")


def _get_sentiment_engine() -> str:
    return os.getenv("SENTIMENT_ENGINE", "auto").lower()


def _get_sentiment_hf_model() -> str:
    return os.getenv("SENTIMENT_HF_MODEL", "snunlp/KR-FinBert-SC")


def _use_openai() -> bool:
    if not os.getenv("OPENAI_API_KEY"):
        return False
    flag = os.getenv("USE_OPENAI")
    if flag is None:
        return True
    return flag == "1"


def _use_vader(engine: str) -> bool:
    if engine == "vader":
        return True
    if engine != "auto":
        return False
    flag = os.getenv("USE_VADER")
    if flag is None:
        return False
    return flag == "1"


def _get_hf_pipeline(model_name: str):
    key = ("text-classification", model_name)
    if key in _HF_PIPELINES:
        return _HF_PIPELINES[key]
    try:
        from transformers import pipeline
    except Exception:
        return None
    try:
        pipe = pipeline("text-classification", model=model_name, tokenizer=model_name)
    except Exception:
        return None
    _HF_PIPELINES[key] = pipe
    return pipe


def _rule_based_sentiment(text: str):
    positives = {"good", "great", "excellent", "happy", "love", "positive", "win", "success"}
    negatives = {"bad", "terrible", "sad", "hate", "negative", "loss", "fail", "crisis"}

    tokens = [t.strip(".,!?;:").lower() for t in text.split()]
    pos_count = sum(1 for t in tokens if t in positives)
    neg_count = sum(1 for t in tokens if t in negatives)
    total = pos_count + neg_count

    score = 0.0
    if total > 0:
        score = (pos_count - neg_count) / total

    if score > 0.2:
        label = "positive"
    elif score < -0.2:
        label = "negative"
    else:
        label = "neutral"

    return {"label": label, "score": float(score), "model": "stub-rule"}


def _extract_json(text: str):
    text = (text or "").strip()
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            return None
        try:
            return json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            return None


def _openai_sentiment(text: str):
    if not _use_openai():
        return None

    client = _get_openai_client()
    if not client:
        return None

    prompt = (
        "다음 텍스트의 감정을 분석해 주세요. "
        "반드시 JSON 한 줄만 반환하세요. "
        '형식: {"label":"positive|neutral|negative","score":-1.0~1.0}'
    )
    try:
        response = client.chat.completions.create(
            model=_get_openai_model(),
            messages=[
                {"role": "system", "content": "너는 감정 분석 모델이야."},
                {"role": "user", "content": f"{prompt}\n\n{text[:6000]}"},
            ],
            temperature=0.0,
        )
    except Exception:
        return None

    content = response.choices[0].message.content if response.choices else ""
    payload = _extract_json(content)
    if not payload:
        return None

    label = payload.get("label")
    score = payload.get("score")
    if label not in {"positive", "neutral", "negative"}:
        return None
    try:
        score = float(score)
    except (TypeError, ValueError):
        return None
    score = max(-1.0, min(1.0, score))
    return {"label": label, "score": score, "model": _get_openai_model()}


def _normalize_hf_label(label: str):
    value = (label or "").strip().lower()
    if "positive" in value or value == "pos":
        return "positive"
    if "negative" in value or value == "neg":
        return "negative"
    if "neutral" in value or value == "neu":
        return "neutral"
    if value in {"label_0", "label_1", "label_2"}:
        mapping = {"label_0": "negative", "label_1": "neutral", "label_2": "positive"}
        return mapping.get(value)
    return None


def _hf_sentiment(text: str):
    model_name = _get_sentiment_hf_model()
    pipe = _get_hf_pipeline(model_name)
    if not pipe:
        return None
    try:
        result = pipe(text[:2000], truncation=True)
    except Exception:
        return None
    if not result or not isinstance(result, list):
        return None
    item = result[0] or {}
    label = _normalize_hf_label(item.get("label"))
    if not label:
        return None
    try:
        score = float(item.get("score", 0.0))
    except (TypeError, ValueError):
        score = 0.0
    if label == "positive":
        scaled = score
    elif label == "negative":
        scaled = -score
    else:
        scaled = 0.0
    return {"label": label, "score": float(scaled), "model": model_name}


def _vader_sentiment(text: str):
    try:
        analyzer = _load_vader()
        scores = analyzer.polarity_scores(text or "")
        compound = float(scores.get("compound", 0.0))
        if compound > 0.2:
            label = "positive"
        elif compound < -0.2:
            label = "negative"
        else:
            label = "neutral"
        return {"label": label, "score": compound, "model": "vader"}
    except Exception:
        return None


def sentiment(text: str):
    engine = _get_sentiment_engine()

    if engine == "openai":
        result = _openai_sentiment(text or "")
        return result or _rule_based_sentiment(text or "")

    if engine == "hf":
        result = _hf_sentiment(text or "")
        return result or _rule_based_sentiment(text or "")

    if engine == "vader":
        result = _vader_sentiment(text or "")
        return result or _rule_based_sentiment(text or "")

    if engine == "rule":
        return _rule_based_sentiment(text or "")

    if _use_openai():
        result = _openai_sentiment(text or "")
        if result:
            return result

    result = _hf_sentiment(text or "")
    if result:
        return result

    if _use_vader(engine):
        result = _vader_sentiment(text or "")
        if result:
            return result

    return _rule_based_sentiment(text or "")
