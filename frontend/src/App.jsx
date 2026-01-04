import { useMemo, useRef, useState } from 'react'
import './App.css'

const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000'

const LANGUAGE_OPTIONS = [
  { value: 'en', label: '영어' },
  { value: 'ko', label: '한국어' },
  { value: 'ja', label: '일본어' },
  { value: 'fr', label: '프랑스어' },
  { value: 'de', label: '독일어' },
  { value: 'es', label: '스페인어' },
]

const sentimentLabelMap = {
  positive: '긍정',
  neutral: '중립',
  negative: '부정',
}

function App() {
  const [query, setQuery] = useState('')
  const [pageSize, setPageSize] = useState(5)
  const [language, setLanguage] = useState('en')
  const [dataset, setDataset] = useState(null)
  const [selectedIndex, setSelectedIndex] = useState(0)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const fileInputRef = useRef(null)

  const articles = dataset?.articles ?? []
  const selectedArticle = articles[selectedIndex] ?? null

  const fetchedAt = useMemo(() => {
    if (!dataset?.fetched_at) {
      return ''
    }
    try {
      return new Date(dataset.fetched_at).toLocaleString()
    } catch {
      return dataset.fetched_at
    }
  }, [dataset])

  const handleFetch = async () => {
    if (!query.trim()) {
      setError('검색어를 입력하세요.')
      return
    }

    setLoading(true)
    setError('')

    try {
      const response = await fetch(`${API_BASE}/api/fetch`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          query: query.trim(),
          page_size: Number(pageSize),
          language,
        }),
      })

      const data = await response.json()
      if (!response.ok) {
        throw new Error(data?.detail || '요청에 실패했습니다.')
      }

      setDataset(data)
      setSelectedIndex(0)
    } catch (err) {
      setError(err.message || '알 수 없는 오류가 발생했습니다.')
    } finally {
      setLoading(false)
    }
  }

  const handleSave = () => {
    if (!dataset) {
      setError('저장할 데이터가 없습니다.')
      return
    }

    const blob = new Blob([JSON.stringify(dataset, null, 2)], {
      type: 'application/json',
    })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `news_${dataset.query || 'dataset'}.json`
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    URL.revokeObjectURL(url)
  }

  const handleLoadClick = () => {
    fileInputRef.current?.click()
  }

  const handleLoadFile = (event) => {
    const file = event.target.files?.[0]
    if (!file) {
      return
    }

    const reader = new FileReader()
    reader.onload = () => {
      try {
        const data = JSON.parse(reader.result)
        if (!data?.articles) {
          throw new Error('JSON 스키마가 올바르지 않습니다.')
        }
        setDataset(data)
        setSelectedIndex(0)
        setError('')
      } catch (err) {
        setError(err.message || '파일을 읽을 수 없습니다.')
      }
    }
    reader.readAsText(file)
    event.target.value = ''
  }

  return (
    <div className="app">
      <header className="hero">
        <div>
          <p className="eyebrow">News Intelligence Desk</p>
          <h1>뉴스 요약 · 감정 분석</h1>
          <p className="subtitle">
            최신 뉴스 흐름을 빠르게 파악하고, 요약과 감정 스코어를 한 번에 확인하세요.
          </p>
        </div>
        <div className="meta-card">
          <p className="meta-title">데이터 상태</p>
          <p className="meta-value">{dataset ? `${articles.length}건` : '대기 중'}</p>
          <p className="meta-caption">{dataset ? `업데이트 ${fetchedAt}` : '검색을 시작해 주세요'}</p>
        </div>
      </header>

      <section className="panel">
        <div className="controls">
          <label className="field">
            <span>검색어</span>
            <input
              type="text"
              value={query}
              placeholder="예: AI, 금융, 스타트업"
              onChange={(event) => setQuery(event.target.value)}
            />
          </label>

          <label className="field">
            <span>개수</span>
            <input
              type="number"
              min="1"
              max="100"
              value={pageSize}
              onChange={(event) => setPageSize(event.target.value)}
            />
          </label>

          <label className="field">
            <span>언어</span>
            <select value={language} onChange={(event) => setLanguage(event.target.value)}>
              {LANGUAGE_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>

          <div className="actions">
            <button className="primary" onClick={handleFetch} disabled={loading}>
              {loading ? '가져오는 중...' : '가져오기'}
            </button>
            <button onClick={handleSave} disabled={!dataset}>
              JSON 저장
            </button>
            <button onClick={handleLoadClick}>JSON 불러오기</button>
            <input ref={fileInputRef} type="file" accept="application/json" hidden onChange={handleLoadFile} />
          </div>
        </div>

        {error && <div className="error">{error}</div>}
      </section>

      <main className="grid">
        <section className="list-panel">
          <div className="panel-header">
            <h2>기사 목록</h2>
            <p>감정 · 출처 · 제목 순서로 표시됩니다.</p>
          </div>
          <div className="list">
            {articles.length === 0 && (
              <div className="empty">아직 가져온 기사가 없습니다.</div>
            )}
            {articles.map((article, index) => {
              const sentiment = article.sentiment || {}
              const label = sentimentLabelMap[sentiment.label] || '미정'
              return (
                <button
                  key={article.id || `${article.url}-${index}`}
                  className={`list-item ${index === selectedIndex ? 'active' : ''}`}
                  onClick={() => setSelectedIndex(index)}
                >
                  <span className={`badge badge-${sentiment.label || 'neutral'}`}>{label}</span>
                  <div className="list-content">
                    <p className="source">{article.source || '알 수 없음'}</p>
                    <p className="title">{article.title || '제목 없음'}</p>
                  </div>
                </button>
              )
            })}
          </div>
        </section>

        <section className="detail-panel">
          <div className="panel-header">
            <h2>기사 상세</h2>
            <p>요약과 감정 스코어를 함께 확인하세요.</p>
          </div>
          {!selectedArticle && <div className="empty">좌측에서 기사를 선택하세요.</div>}
          {selectedArticle && (
            <div className="detail-card">
              <div className="detail-header">
                <div>
                  <p className="detail-source">{selectedArticle.source || '알 수 없음'}</p>
                  <h3>{selectedArticle.title || '제목 없음'}</h3>
                </div>
                <div className="score-box">
                  <span>감정</span>
                  <strong>{sentimentLabelMap[selectedArticle.sentiment?.label] || '미정'}</strong>
                  <em>{(selectedArticle.sentiment?.score ?? 0).toFixed(2)}</em>
                </div>
              </div>

              <div className="detail-meta">
                <p>발행일: {selectedArticle.publishedAt || '-'}</p>
                <p>
                  원문:
                  <a href={selectedArticle.url} target="_blank" rel="noreferrer">
                    링크 열기
                  </a>
                </p>
              </div>

              <div className="detail-section">
                <h4>요약</h4>
                <p>{selectedArticle.summary || '요약이 없습니다.'}</p>
              </div>

              <div className="detail-section">
                <h4>전체 텍스트</h4>
                <p>{selectedArticle.text || '본문이 없습니다.'}</p>
              </div>
            </div>
          )}
        </section>
      </main>
    </div>
  )
}

export default App
