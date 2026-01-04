import json
import os
from datetime import datetime
from pathlib import Path

import streamlit as st

from backend.app.pipeline import run_pipeline


LANGUAGE_OPTIONS = [
    ("en", "영어"),
    ("ko", "한국어"),
    ("ja", "일본어"),
    ("fr", "프랑스어"),
    ("de", "독일어"),
    ("es", "스페인어"),
]

SENTIMENT_LABELS = {
    "positive": "긍정",
    "neutral": "중립",
    "negative": "부정",
}

ENV_PATH = Path(".env")
SECRET_FIELDS = {
    "NEWS_API_KEY": "NewsAPI Key",
    "OPENAI_API_KEY": "OpenAI API Key",
}
PLAIN_FIELDS = {
    "OPENAI_MODEL": "OpenAI Model",
}
BOOL_FIELDS = {
    "USE_OPENAI": "OpenAI 사용 허용 (자동 모드)",
    "USE_TRANSFORMERS_SUMMARY": "HF 요약 사용 허용 (자동 모드)",
    "USE_VADER": "VADER 감정 분석 사용 허용 (자동 모드)",
}
BOOL_FIELD_DESC = {
    "USE_OPENAI": "자동 모드에서 OpenAI 요약/감정 분석을 허용합니다.",
    "USE_TRANSFORMERS_SUMMARY": "자동 모드에서 HF 요약 모델 사용을 허용합니다.",
    "USE_VADER": "자동 모드에서 VADER 감정 분석 사용을 허용합니다.",
}

SUMMARY_ENGINE_OPTIONS = {
    "auto": "자동 (OpenAI → HF → 스텁)",
    "openai": "OpenAI 요약",
    "hf": "Hugging Face 요약",
    "stub": "스텁 요약",
}

SENTIMENT_ENGINE_OPTIONS = {
    "auto": "자동 (OpenAI → HF → VADER → 룰)",
    "openai": "OpenAI 감정 분석",
    "hf": "Hugging Face 감정 분석",
    "vader": "VADER 감정 분석",
    "rule": "룰 기반 스텁",
}

SUMMARY_HF_MODELS = {
    "ainize/kobart-news": "KoBART 뉴스 요약 (ainize/kobart-news)",
}

SENTIMENT_HF_MODELS = {
    "snunlp/KR-FinBert-SC": "KR-FinBERT 감정 (snunlp/KR-FinBert-SC)",
}


def _init_state():
    if "dataset" not in st.session_state:
        st.session_state.dataset = None
    if "selected_index" not in st.session_state:
        st.session_state.selected_index = 0


def _unwrap_env_value(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def _read_env_file(path: Path) -> dict:
    if not path.exists():
        return {}
    data = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        data[key.strip()] = _unwrap_env_value(value)
    return data


def _load_env_once():
    if st.session_state.get("env_loaded"):
        return
    data = _read_env_file(ENV_PATH)
    for key, value in data.items():
        os.environ.setdefault(key, value)
    st.session_state.env_loaded = True


def _apply_env_values(values: dict) -> None:
    for key, value in values.items():
        if value:
            os.environ[key] = value
        else:
            os.environ.pop(key, None)


def _persist_env_values(values: dict) -> None:
    existing = _read_env_file(ENV_PATH)
    for key, value in values.items():
        if value:
            existing[key] = value
        else:
            existing.pop(key, None)
    lines = []
    for key in sorted(existing.keys()):
        val = existing[key].replace('"', '\\"')
        lines.append(f'{key}="{val}"')
    ENV_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _init_settings_state():
    _load_env_once()
    for key in {**SECRET_FIELDS, **PLAIN_FIELDS}:
        if key not in st.session_state or not st.session_state.get(key):
            st.session_state[key] = os.getenv(key, "")
    for key in BOOL_FIELDS:
        if key not in st.session_state:
            current = os.getenv(key)
            if current is None:
                if key == "USE_OPENAI":
                    st.session_state[key] = bool(os.getenv("OPENAI_API_KEY"))
                else:
                    st.session_state[key] = False
            else:
                st.session_state[key] = current == "1"
    if "SUMMARY_ENGINE" not in st.session_state:
        summary_engine = os.getenv("SUMMARY_ENGINE", "auto").lower()
        if summary_engine not in SUMMARY_ENGINE_OPTIONS:
            summary_engine = "auto"
        st.session_state["SUMMARY_ENGINE"] = summary_engine
    if "SENTIMENT_ENGINE" not in st.session_state:
        sentiment_engine = os.getenv("SENTIMENT_ENGINE", "auto").lower()
        if sentiment_engine not in SENTIMENT_ENGINE_OPTIONS:
            sentiment_engine = "auto"
        st.session_state["SENTIMENT_ENGINE"] = sentiment_engine
    if "SUMMARY_HF_MODEL" not in st.session_state:
        default_summary_model = next(iter(SUMMARY_HF_MODELS.keys()))
        summary_model = os.getenv("SUMMARY_HF_MODEL", default_summary_model)
        if summary_model not in SUMMARY_HF_MODELS:
            summary_model = default_summary_model
        st.session_state["SUMMARY_HF_MODEL"] = summary_model
    if "SENTIMENT_HF_MODEL" not in st.session_state:
        default_sentiment_model = next(iter(SENTIMENT_HF_MODELS.keys()))
        sentiment_model = os.getenv("SENTIMENT_HF_MODEL", default_sentiment_model)
        if sentiment_model not in SENTIMENT_HF_MODELS:
            sentiment_model = default_sentiment_model
        st.session_state["SENTIMENT_HF_MODEL"] = sentiment_model


def _reset_home_state():
    st.session_state.dataset = None
    st.session_state.selected_index = 0
    st.session_state.query_input = ""
    st.session_state.page_size_input = 5
    st.session_state.language_input = LANGUAGE_OPTIONS[0][0]


def _secret_input(label: str, value_key: str) -> None:
    st.text_input(label, key=value_key, type="password")


@st.dialog("API 설정")
def _render_settings_dialog():
    st.caption("설정은 `.env`에 저장되며, 즉시 적용됩니다.")
    st.subheader("API 키")
    for key, label in SECRET_FIELDS.items():
        _secret_input(label, key)
    for key, label in PLAIN_FIELDS.items():
        st.text_input(label, key=key)
    st.subheader("모델 선택")
    st.selectbox(
        "뉴스 요약 엔진",
        options=list(SUMMARY_ENGINE_OPTIONS.keys()),
        format_func=lambda value: SUMMARY_ENGINE_OPTIONS.get(value, value),
        key="SUMMARY_ENGINE",
    )
    st.selectbox(
        "요약 HF 모델",
        options=list(SUMMARY_HF_MODELS.keys()),
        format_func=lambda value: SUMMARY_HF_MODELS.get(value, value),
        key="SUMMARY_HF_MODEL",
    )
    st.selectbox(
        "감정 분석 엔진",
        options=list(SENTIMENT_ENGINE_OPTIONS.keys()),
        format_func=lambda value: SENTIMENT_ENGINE_OPTIONS.get(value, value),
        key="SENTIMENT_ENGINE",
    )
    st.selectbox(
        "감정 HF 모델",
        options=list(SENTIMENT_HF_MODELS.keys()),
        format_func=lambda value: SENTIMENT_HF_MODELS.get(value, value),
        key="SENTIMENT_HF_MODEL",
    )
    st.subheader("옵션")
    for key, label in BOOL_FIELDS.items():
        col_label, col_desc = st.columns([0.62, 0.38])
        with col_label:
            st.checkbox(label, key=key)
        with col_desc:
            st.caption(BOOL_FIELD_DESC.get(key, ""))

    col_save, col_close = st.columns(2)
    with col_save:
        if st.button("저장 및 적용", type="primary"):
            updates = {}
            for key in {**SECRET_FIELDS, **PLAIN_FIELDS}:
                updates[key] = st.session_state.get(key, "").strip()
            updates["SUMMARY_ENGINE"] = st.session_state.get("SUMMARY_ENGINE", "auto")
            updates["SENTIMENT_ENGINE"] = st.session_state.get(
                "SENTIMENT_ENGINE", "auto"
            )
            updates["SUMMARY_HF_MODEL"] = st.session_state.get("SUMMARY_HF_MODEL", "")
            updates["SENTIMENT_HF_MODEL"] = st.session_state.get(
                "SENTIMENT_HF_MODEL", ""
            )
            for key in BOOL_FIELDS:
                updates[key] = "1" if st.session_state.get(key) else "0"
            _apply_env_values(updates)
            _persist_env_values(updates)
            st.session_state.settings_saved = True
            st.rerun()


def _format_time(value: str) -> str:
    if not value:
        return "-"
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).strftime(
            "%Y-%m-%d %H:%M"
        )
    except ValueError:
        return value


def _load_json_file(uploaded_file):
    if uploaded_file is None:
        return None
    try:
        content = uploaded_file.read().decode("utf-8")
        data = json.loads(content)
    except Exception:
        st.error("파일을 읽을 수 없습니다.")
        return None
    if not isinstance(data, dict) or "articles" not in data:
        st.error("JSON 스키마가 올바르지 않습니다.")
        return None
    return data


def _build_list_label(article: dict) -> str:
    sentiment = article.get("sentiment", {})
    label = SENTIMENT_LABELS.get(sentiment.get("label"), "미정")
    source = article.get("source") or "알 수 없음"
    title = article.get("title") or "제목 없음"
    return f"[{label}] {source} - {title}"


def main():
    st.set_page_config(page_title="뉴스 요약 · 감정 분석", layout="wide")
    _init_state()
    _init_settings_state()

    title_left, title_right = st.columns([0.78, 0.22])
    with title_left:
        st.title("뉴스 요약 · 감정 분석")
        st.caption("NewsAPI 기반 수집 → 요약 → 감정 분석 → JSON 저장/불러오기")
    with title_right:
        if st.button("API 설정", use_container_width=True):
            _render_settings_dialog()

    if st.session_state.get("settings_saved"):
        st.success("API 설정이 저장되었습니다.")
        st.session_state.settings_saved = False

    if not os.getenv("NEWS_API_KEY"):
        st.warning("NEWS_API_KEY 환경 변수가 없습니다. 뉴스 수집이 실패합니다.")

    with st.sidebar:
        st.subheader("검색 설정")
        query = st.text_input(
            "검색어", placeholder="예: AI, 금융, 스타트업", key="query_input"
        )
        page_size = st.number_input(
            "개수",
            min_value=1,
            max_value=100,
            value=5,
            step=1,
            key="page_size_input",
        )
        language = st.selectbox(
            "언어",
            options=[opt[0] for opt in LANGUAGE_OPTIONS],
            format_func=lambda value: dict(LANGUAGE_OPTIONS).get(value, value),
            key="language_input",
        )
        fetch_clicked = st.button("가져오기", use_container_width=True)

        st.divider()
        st.subheader("JSON 저장/불러오기")
        st.download_button(
            "JSON 저장",
            data=(
                json.dumps(st.session_state.dataset, ensure_ascii=False, indent=2)
                if st.session_state.dataset
                else ""
            ),
            file_name="news_dataset.json",
            mime="application/json",
            disabled=st.session_state.dataset is None,
            use_container_width=True,
        )
        uploaded = st.file_uploader("JSON 불러오기", type=["json"])
        if uploaded:
            data = _load_json_file(uploaded)
            if data:
                st.session_state.dataset = data
                st.session_state.selected_index = 0

    if fetch_clicked:
        if not query.strip():
            st.error("검색어를 입력하세요.")
        else:
            with st.spinner("뉴스를 가져오는 중입니다..."):
                try:
                    dataset = run_pipeline(query.strip(), int(page_size), language)
                except Exception as exc:
                    st.error(str(exc))
                else:
                    if not dataset.get("articles"):
                        st.warning("검색 결과가 없습니다.")
                    st.session_state.dataset = dataset
                    st.session_state.selected_index = 0

    dataset = st.session_state.dataset
    articles = dataset.get("articles", []) if dataset else []

    left, right = st.columns([1, 1.4], gap="large")

    with left:
        st.subheader("기사 목록")
        if not articles:
            st.info("아직 가져온 기사가 없습니다.")
        else:
            labels = [_build_list_label(article) for article in articles]
            selected = st.radio(
                "기사 선택",
                options=list(range(len(labels))),
                format_func=lambda idx: labels[idx],
                index=min(st.session_state.selected_index, len(labels) - 1),
            )
            st.session_state.selected_index = selected

    with right:
        st.subheader("기사 상세")
        if not articles:
            st.info("좌측에서 기사를 선택하세요.")
        else:
            article = articles[st.session_state.selected_index]
            sentiment = article.get("sentiment", {})
            label = SENTIMENT_LABELS.get(sentiment.get("label"), "미정")
            score = sentiment.get("score", 0.0)

            st.markdown(f"**제목**: {article.get('title', '-')}")
            st.markdown(f"**출처**: {article.get('source', '-')}")
            st.markdown(f"**발행일**: {_format_time(article.get('publishedAt', ''))}")
            st.markdown(f"**감정**: {label} ({score:.2f})")
            url = article.get("url")
            if url:
                st.markdown(f"[원문 링크]({url})")

            st.divider()
            st.markdown("### 요약")
            st.write(article.get("summary") or "요약이 없습니다.")
            st.markdown("### 본문")
            st.write(article.get("text") or "본문이 없습니다.")


if __name__ == "__main__":
    main()
