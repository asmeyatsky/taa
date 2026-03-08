import { useState } from 'react'
import { useQuery, useMutation } from '@tanstack/react-query'
import { api } from '../api/client'

export default function AnalyticsPage() {
  const [selectedTemplate, setSelectedTemplate] = useState<string | null>(null)
  const [selectedType, setSelectedType] = useState<string>('sql')
  const [generatedContent, setGeneratedContent] = useState<string | null>(null)

  const templates = useQuery({
    queryKey: ['templates'],
    queryFn: api.getTemplates,
  })

  const generateMutation = useMutation({
    mutationFn: () => api.generateTemplate(selectedTemplate!, selectedType),
    onSuccess: (data) => setGeneratedContent(data.content),
  })

  const grouped = templates.data?.reduce((acc, t) => {
    acc[t.type] = acc[t.type] || []
    acc[t.type].push(t)
    return acc
  }, {} as Record<string, typeof templates.data>) ?? {}

  const typeLabels: Record<string, string> = {
    sql: 'SQL Analytics',
    notebook: 'Vertex AI Notebooks',
    dashboard: 'Looker Dashboards',
  }

  return (
    <div className="page">
      <h2>Analytics Templates</h2>
      <p className="page-desc">
        Pre-built SQL queries, Jupyter notebooks, and Looker dashboards for telco analytics.
      </p>

      {templates.isLoading && <p className="loading">Loading templates...</p>}

      {Object.entries(grouped).map(([type, items]) => (
        <section key={type} className="card">
          <h3>{typeLabels[type] || type}</h3>
          <div className="template-list">
            {items!.map(t => (
              <button
                key={`${t.type}-${t.name}`}
                className={`template-item ${selectedTemplate === t.name && selectedType === t.type ? 'template-active' : ''}`}
                onClick={() => {
                  setSelectedTemplate(t.name)
                  setSelectedType(t.type)
                  setGeneratedContent(null)
                }}
              >
                <span className="template-name">{t.name.replace(/_/g, ' ')}</span>
                <span className="template-type-badge">{t.type}</span>
              </button>
            ))}
          </div>
        </section>
      ))}

      {selectedTemplate && (
        <div className="action-bar">
          <button
            className="btn btn-primary"
            disabled={generateMutation.isPending}
            onClick={() => generateMutation.mutate()}
          >
            {generateMutation.isPending ? 'Generating...' : `Generate: ${selectedTemplate.replace(/_/g, ' ')}`}
          </button>
        </div>
      )}

      {generatedContent && (
        <section className="card result-card">
          <div className="result-header">
            <h3>{selectedTemplate?.replace(/_/g, ' ')}</h3>
            <button
              className="btn btn-sm"
              onClick={() => {
                navigator.clipboard.writeText(generatedContent)
              }}
            >
              Copy
            </button>
          </div>
          <pre className="code-block">{generatedContent}</pre>
        </section>
      )}
    </div>
  )
}
