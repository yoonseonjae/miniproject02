import os

from openai import OpenAI


_HF_PIPELINES = {}
_OPENAI_CLIENT = None
_OPENAI_API_KEY = None


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


def _get_summary_engine() -> str:
    return os.getenv("SUMMARY_ENGINE", "auto").lower()


def _get_summary_hf_model() -> str:
    return os.getenv("SUMMARY_HF_MODEL", "ainize/kobart-news")


def _use_openai() -> bool:
    if not os.getenv("OPENAI_API_KEY"):
        return False
    flag = os.getenv("USE_OPENAI")
    if flag is None:
        return True
    return flag == "1"


def _use_hf_summary(engine: str) -> bool:
    if engine == "hf":
        return True
    if engine != "auto":
        return False
    flag = os.getenv("USE_TRANSFORMERS_SUMMARY")
    if flag is None:
        return True
    return flag == "1"


def _get_hf_pipeline(model_name: str):
    key = ("summarization", model_name)
    if key in _HF_PIPELINES:
        return _HF_PIPELINES[key]
    try:
        from transformers import pipeline
    except Exception:
        return None
    try:
        pipe = pipeline("summarization", model=model_name, tokenizer=model_name)
    except Exception:
        return None
    _HF_PIPELINES[key] = pipe
    return pipe


def _stub_summarize(text: str, max_chars: int = 350) -> str:
    if not text:
        return ""
    return text[:max_chars].strip()


def _openai_summarize(text: str) -> str:
    if not _use_openai():
        return ""

    client = _get_openai_client()
    if not client:
        return ""

    prompt = (
        "다음 뉴스 텍스트를 한국어로 3~4문장으로 요약해 주세요. "
        "핵심 사실만 간결하게 정리하세요."
    )
    try:
        response = client.chat.completions.create(
            model=_get_openai_model(),
            messages=[
                {"role": "system", "content": "너는 뉴스 요약 전문가야."},
                {"role": "user", "content": f"{prompt}\n\n{text[:6000]}"},
            ],
            temperature=0.2,
        )
    except Exception:
        return ""

    choice = response.choices[0].message.content if response.choices else ""
    return (choice or "").strip()


def _hf_summarize(text: str) -> str:
    model_name = _get_summary_hf_model()
    pipe = _get_hf_pipeline(model_name)
    if not pipe:
        return ""
    try:
        result = pipe(text[:3000], max_length=120, min_length=30, do_sample=False)
    except Exception:
        return ""
    if result and isinstance(result, list):
        return result[0].get("summary_text", "").strip()
    return ""


def summarize(text: str) -> str:
    if not text:
        return ""

    engine = _get_summary_engine()

    if engine == "openai":
        summary = _openai_summarize(text)
        return summary or _stub_summarize(text)

    if engine == "hf":
        summary = _hf_summarize(text)
        return summary or _stub_summarize(text)

    if engine == "stub":
        return _stub_summarize(text)

    if _use_openai():
        summary = _openai_summarize(text)
        if summary:
            return summary

    if _use_hf_summary(engine):
        summary = _hf_summarize(text)
        if summary:
            return summary

    return _stub_summarize(text)
