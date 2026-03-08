import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api } from '../api/client'
import type { DomainDetail, TableDetail } from '../api/types'

export default function DomainsPage() {
  const [selectedDomains, setSelectedDomains] = useState<string[]>([])
  const [expandedTable, setExpandedTable] = useState<string | null>(null)

  const domains = useQuery({ queryKey: ['domains'], queryFn: api.getDomains })

  const ldm = useQuery({
    queryKey: ['ldm', selectedDomains],
    queryFn: () => api.getLDM(selectedDomains),
    enabled: selectedDomains.length > 0,
  })

  const toggleDomain = (name: string) => {
    setSelectedDomains(prev =>
      prev.includes(name) ? prev.filter(d => d !== name) : [...prev, name]
    )
    setExpandedTable(null)
  }

  return (
    <div className="page">
      <h2>Domain Explorer</h2>
      <p className="page-desc">Browse the Logical Data Model — tables, columns, types, and PII classifications.</p>

      <div className="chip-group" style={{ marginBottom: '1.5rem' }}>
        {domains.data?.map(d => (
          <button
            key={d.name}
            className={`chip ${selectedDomains.includes(d.name) ? 'chip-active' : ''}`}
            onClick={() => toggleDomain(d.name)}
          >
            {d.name}
            <span className="chip-badge">{d.table_count}</span>
          </button>
        ))}
      </div>

      {ldm.isLoading && <p className="loading">Loading data model...</p>}

      {ldm.data?.domains.map((domain: DomainDetail) => (
        <section key={domain.name} className="card">
          <h3>{domain.name} <span className="badge">{domain.table_count} tables</span></h3>
          <div className="table-list">
            {domain.tables.map((table: TableDetail) => (
              <div key={table.name} className="table-item">
                <button
                  className="table-header"
                  onClick={() => setExpandedTable(expandedTable === table.name ? null : table.name)}
                >
                  <span className="table-name">{table.name}</span>
                  <span className="badge">{table.column_count} cols</span>
                  <span className="expand-icon">{expandedTable === table.name ? '▾' : '▸'}</span>
                </button>
                {expandedTable === table.name && (
                  <div className="column-grid">
                    <div className="column-grid-header">
                      <span>Column</span>
                      <span>Type</span>
                      <span>Nullable</span>
                      <span>PII</span>
                    </div>
                    {table.columns.map(col => (
                      <div key={col.name} className={`column-row ${col.pii_category ? 'pii-row' : ''}`}>
                        <span className="col-name">{col.name}</span>
                        <span className="col-type">{col.bigquery_type}</span>
                        <span>{col.nullable ? 'yes' : 'no'}</span>
                        <span className="col-pii">
                          {col.pii_category && <span className="pii-badge">{col.pii_category}</span>}
                        </span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
        </section>
      ))}
    </div>
  )
}
