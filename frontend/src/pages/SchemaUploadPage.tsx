import { useState, useCallback } from 'react'
import { useMutation } from '@tanstack/react-query'

interface SchemaUploadResponse {
  tables_found: number
  columns_found: number
  detected_vendor: string | null
  vendor_confidence: number
  suggestions: {
    vendor_table: string
    vendor_field: string
    canonical_table: string
    canonical_field: string
    confidence: number
    match_reason: string
  }[]
  mapping_coverage_pct: number
  import_coverage_pct: number
}

export default function SchemaUploadPage() {
  const [content, setContent] = useState('')
  const [format, setFormat] = useState('auto')
  const [dragOver, setDragOver] = useState(false)
  const [result, setResult] = useState<SchemaUploadResponse | null>(null)

  const uploadMutation = useMutation({
    mutationFn: async () => {
      const token = localStorage.getItem('taa_token')
      const res = await fetch('/api/bss/schema', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({ content, format }),
      })
      if (!res.ok) throw new Error(`Upload failed: ${res.status}`)
      return res.json() as Promise<SchemaUploadResponse>
    },
    onSuccess: (data) => setResult(data),
  })

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setDragOver(false)
    const file = e.dataTransfer.files[0]
    if (file) {
      const reader = new FileReader()
      reader.onload = (ev) => {
        setContent(ev.target?.result as string)
        const ext = file.name.split('.').pop()?.toLowerCase()
        if (ext === 'csv') setFormat('csv')
        else if (ext === 'json') setFormat('json')
        else if (ext === 'yaml' || ext === 'yml') setFormat('yaml')
      }
      reader.readAsText(file)
    }
  }, [])

  const handleFileSelect = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file) {
      const reader = new FileReader()
      reader.onload = (ev) => {
        setContent(ev.target?.result as string)
        const ext = file.name.split('.').pop()?.toLowerCase()
        if (ext === 'csv') setFormat('csv')
        else if (ext === 'json') setFormat('json')
        else if (ext === 'yaml' || ext === 'yml') setFormat('yaml')
      }
      reader.readAsText(file)
    }
  }, [])

  return (
    <div className="page">
      <h2>BSS Schema Import</h2>
      <p className="page-desc">
        Upload a vendor BSS/OSS schema to auto-detect the vendor, map fields to the canonical telco data model, and preview coverage.
      </p>

      <div className="form-grid">
        <section className="card">
          <h3>Upload Schema</h3>
          <div
            className={`drop-zone ${dragOver ? 'drop-zone-active' : ''}`}
            onDragOver={e => { e.preventDefault(); setDragOver(true) }}
            onDragLeave={() => setDragOver(false)}
            onDrop={handleDrop}
          >
            <div className="drop-zone-content">
              <span className="drop-icon">&#128193;</span>
              <p>Drag & drop a schema file here</p>
              <p className="drop-hint">CSV, JSON, or YAML</p>
              <label className="btn btn-sm drop-browse">
                Browse Files
                <input
                  type="file"
                  accept=".csv,.json,.yaml,.yml"
                  onChange={handleFileSelect}
                  hidden
                />
              </label>
            </div>
          </div>
        </section>

        <section className="card">
          <h3>Format</h3>
          <select className="select" value={format} onChange={e => setFormat(e.target.value)}>
            <option value="auto">Auto-detect</option>
            <option value="csv">CSV</option>
            <option value="json">JSON</option>
            <option value="yaml">YAML</option>
          </select>
          <div style={{ marginTop: '1rem' }}>
            <h3>Or paste schema content</h3>
            <textarea
              className="input schema-textarea"
              value={content}
              onChange={e => setContent(e.target.value)}
              placeholder={"table,column,type,nullable\nsubscriber_profile,subscriber_id,STRING,NO\nsubscriber_profile,msisdn,STRING,NO"}
              rows={8}
            />
          </div>
        </section>
      </div>

      <div className="action-bar">
        <button
          className="btn btn-primary btn-lg"
          disabled={!content.trim() || uploadMutation.isPending}
          onClick={() => uploadMutation.mutate()}
        >
          {uploadMutation.isPending ? 'Analysing...' : 'Import & Analyse Schema'}
        </button>
      </div>

      {uploadMutation.isError && (
        <div className="alert alert-error">
          {(uploadMutation.error as Error).message}
        </div>
      )}

      {result && (
        <>
          <div className="schema-stats">
            <div className="stat-card">
              <div className="stat-value">{result.tables_found}</div>
              <div className="stat-label">Tables Found</div>
            </div>
            <div className="stat-card">
              <div className="stat-value">{result.columns_found}</div>
              <div className="stat-label">Columns Found</div>
            </div>
            <div className="stat-card">
              <div className="stat-value">{result.detected_vendor || 'Unknown'}</div>
              <div className="stat-label">Detected Vendor ({(result.vendor_confidence * 100).toFixed(0)}%)</div>
            </div>
            <div className="stat-card">
              <div className="stat-value">{result.mapping_coverage_pct.toFixed(1)}%</div>
              <div className="stat-label">Mapping Coverage</div>
            </div>
          </div>

          {result.suggestions.length > 0 && (
            <section className="card result-card">
              <h3>Field Mapping Suggestions ({result.suggestions.length})</h3>
              <div className="mapping-grid">
                <div className="mapping-header">
                  <span>Vendor Table</span>
                  <span>Vendor Field</span>
                  <span>Canonical Table</span>
                  <span>Canonical Field</span>
                  <span>Confidence</span>
                </div>
                {result.suggestions.map((s, i) => (
                  <div key={i} className="mapping-row">
                    <span className="col-name">{s.vendor_table}</span>
                    <span className="col-name">{s.vendor_field}</span>
                    <span style={{ color: 'var(--accent)' }}>{s.canonical_table}</span>
                    <span style={{ color: 'var(--accent)' }}>{s.canonical_field}</span>
                    <span>
                      <span className={`confidence-badge ${s.confidence >= 0.8 ? 'conf-high' : s.confidence >= 0.5 ? 'conf-med' : 'conf-low'}`}>
                        {(s.confidence * 100).toFixed(0)}%
                      </span>
                    </span>
                  </div>
                ))}
              </div>
            </section>
          )}
        </>
      )}
    </div>
  )
}
