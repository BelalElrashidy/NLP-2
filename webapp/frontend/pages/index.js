import { useState } from 'react'

function Spinner() {
  return (
    <svg width="20" height="20" viewBox="0 0 50 50" className="spinner">
      <circle cx="25" cy="25" r="20" stroke="rgba(255,255,255,0.14)" strokeWidth="5" fill="none" />
      <path d="M45 25a20 20 0 0 0-6.1-14.1" stroke="#fff" strokeWidth="5" strokeLinecap="round" fill="none" />
    </svg>
  )
}

export default function Home() {
  const [prompt, setPrompt] = useState('')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)

  async function submit(e) {
    e && e.preventDefault()
    setLoading(true)
    setResult(null)
    try {
      const res = await fetch('http://localhost:8000/api/ask', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ prompt })
      })
      const data = await res.json()
      setResult(data)
    } catch (err) {
      setResult({ error: String(err) })
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="chat-container">
      <div className="panel">
        <header className="flex items-center gap-4 mb-4">
          <div className="w-12 h-12 rounded-lg bg-gradient-to-br from-violet-600 to-cyan-500 flex items-center justify-center font-bold text-white">R</div>
          <div>
            <h1 className="text-xl font-semibold">RAG Web QA</h1>
            <p className="text-sm text-slate-400">Ask from your offline corpus — fast, private.</p>
          </div>
        </header>

        <form onSubmit={submit} className="space-y-4">
          <textarea
            className="prompt-input"
            placeholder="Type your question here..."
            value={prompt}
            onChange={e => setPrompt(e.target.value)}
          />

          <div className="flex gap-3">
            <button className="btn-primary" disabled={loading || !prompt}>
              {loading ? 'Thinking…' : 'Ask'}
            </button>
            <button type="button" className="btn-muted" onClick={() => setPrompt('')}>Clear</button>
          </div>
        </form>

        {result && (
          <div className="mt-6">
            {result.error ? (
              <div className="answer-bubble">Error: {result.error}</div>
            ) : (
              <>
                <div className="answer-bubble">{result.answer}</div>
                <div className="mt-3 text-sm text-slate-400">Confidence: <strong className="text-white">{result.confidence ?? '—'}</strong></div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mt-4">
                  {result.sources && result.sources.length ? result.sources.map((s,i)=>(
                    <div key={i} className="source-card">
                      <div className="font-semibold text-sm text-white">{s.title || 'Source'}</div>
                      <a className="text-slate-400 text-xs break-words" href={s.url} target="_blank" rel="noreferrer">{s.url}</a>
                      <div className="mt-2 text-xs"><span className="inline-block bg-slate-700 text-white px-2 py-1 rounded-full">{(s.score||0).toFixed(3)}</span></div>
                    </div>
                  )) : <div className="text-slate-400">No sources returned.</div>}
                </div>
              </>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

