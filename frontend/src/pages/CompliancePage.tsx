import { useState, useMemo } from 'react'
import { useQuery, useMutation } from '@tanstack/react-query'
import { useAuth } from '../auth/AuthContext'
import { api } from '../api/client'
import type { ComplianceCheckResponse, JurisdictionInfo } from '../api/types'

const REGIONS: { label: string; match: (j: JurisdictionInfo) => boolean }[] = [
  { label: 'All Regions', match: () => true },
  { label: 'Middle East', match: j => j.gcp_region.startsWith('me-') },
  { label: 'Europe', match: j => j.gcp_region.startsWith('europe-') },
  { label: 'Asia Pacific', match: j => j.gcp_region.startsWith('asia-') },
  { label: 'Africa', match: j => j.gcp_region.startsWith('africa-') },
]

export default function CompliancePage() {
  const { hasPermission } = useAuth()
  const [selectedDomains, setSelectedDomains] = useState<string[]>([])
  const [selectedRegion, setSelectedRegion] = useState('All Regions')
  const [jurisdiction, setJurisdiction] = useState('')
  const [result, setResult] = useState<ComplianceCheckResponse | null>(null)

  const domains = useQuery({ queryKey: ['domains'], queryFn: api.getDomains })
  const jurisdictions = useQuery({ queryKey: ['jurisdictions'], queryFn: api.getJurisdictions })

  const regionFilter = REGIONS.find(r => r.label === selectedRegion) ?? REGIONS[0]
  const filteredJurisdictions = useMemo(
    () => jurisdictions.data?.filter(regionFilter.match) ?? [],
    [jurisdictions.data, selectedRegion],
  )

  // Auto-select first jurisdiction when region changes
  const activeJurisdiction = filteredJurisdictions.find(j => j.code === jurisdiction)
    ? jurisdiction
    : filteredJurisdictions[0]?.code ?? ''

  if (activeJurisdiction !== jurisdiction && activeJurisdiction) {
    setJurisdiction(activeJurisdiction)
  }

  const checkMutation = useMutation({
    mutationFn: () => api.checkCompliance(selectedDomains, jurisdiction),
    onSuccess: (data) => setResult(data),
  })

  const toggleDomain = (name: string) => {
    setSelectedDomains(prev =>
      prev.includes(name) ? prev.filter(d => d !== name) : [...prev, name]
    )
  }

  const canRun = hasPermission('compliance:run')
  const canExport = hasPermission('compliance:export')

  return (
    <div className="page">
      <h2>Compliance Assessment</h2>
      <p className="page-desc">
        Run data protection compliance checks against telco privacy regulations. Select a region to filter applicable jurisdictions.
      </p>

      <div className="form-grid">
        <section className="card">
          <h3>Domains</h3>
          <div className="chip-group">
            {domains.data?.map(d => (
              <button
                key={d.name}
                className={`chip ${selectedDomains.includes(d.name) ? 'chip-active' : ''}`}
                onClick={() => toggleDomain(d.name)}
              >
                {d.name}
              </button>
            ))}
          </div>
        </section>

        <section className="card">
          <h3>Region</h3>
          <div className="chip-group">
            {REGIONS.map(r => {
              const count = jurisdictions.data?.filter(r.match).length ?? 0
              return (
                <button
                  key={r.label}
                  className={`chip ${selectedRegion === r.label ? 'chip-active' : ''}`}
                  onClick={() => {
                    setSelectedRegion(r.label)
                    setResult(null)
                  }}
                >
                  {r.label}
                  {r.label !== 'All Regions' && <span className="chip-badge">{count}</span>}
                </button>
              )
            })}
          </div>
        </section>
      </div>

      <section className="card">
        <h3>Jurisdiction</h3>
        {filteredJurisdictions.length === 0 ? (
          <p className="text-dim">No jurisdictions in this region.</p>
        ) : (
          <div className="jurisdiction-cards">
            {filteredJurisdictions.map(j => (
              <button
                key={j.code}
                className={`jurisdiction-card ${jurisdiction === j.code ? 'jurisdiction-active' : ''}`}
                onClick={() => {
                  setJurisdiction(j.code)
                  setResult(null)
                }}
              >
                <div className="jurisdiction-header">
                  <span className="jurisdiction-code">{j.code}</span>
                  <span className="jurisdiction-name">{j.name}</span>
                </div>
                <div className="jurisdiction-meta">
                  <span className="jurisdiction-framework">{j.framework}</span>
                  <span className="jurisdiction-region">{j.gcp_region}</span>
                  {j.data_residency_required && (
                    <span className="jurisdiction-residency">Data Residency</span>
                  )}
                </div>
                <div className="jurisdiction-rules">{j.rule_count} rules</div>
              </button>
            ))}
          </div>
        )}
      </section>

      <div className="action-bar" style={{ display: 'flex', gap: '0.75rem' }}>
        {canRun ? (
          <button
            className="btn btn-primary btn-lg"
            disabled={selectedDomains.length === 0 || !jurisdiction || checkMutation.isPending}
            onClick={() => checkMutation.mutate()}
          >
            {checkMutation.isPending ? 'Checking...' : `Run ${filteredJurisdictions.find(j => j.code === jurisdiction)?.framework ?? ''} Compliance Check`}
          </button>
        ) : (
          <div className="permission-notice">
            Compliance checks require Admin or Management access. You can view jurisdictions and frameworks above.
          </div>
        )}
      </div>

      {result && (
        <section className="card result-card">
          <div className="result-header">
            <h3>
              {result.framework} Compliance — {result.jurisdiction}
            </h3>
            {canExport && (
              <button className="btn btn-sm" onClick={() => {
                const text = result.findings.map(f =>
                  `${f.rule_id}\t${f.framework}\t${f.data_residency_required ? 'Yes' : 'No'}\t${f.encryption_required ? 'Yes' : 'No'}`
                ).join('\n')
                navigator.clipboard.writeText(`Rule ID\tFramework\tData Residency\tEncryption\n${text}`)
              }}>
                Export to Clipboard
              </button>
            )}
          </div>
          <p>{result.finding_count} rules assessed</p>
          <div className="findings-grid">
            <div className="findings-header">
              <span>Rule ID</span>
              <span>Framework</span>
              <span>Data Residency</span>
              <span>Encryption</span>
            </div>
            {result.findings.map(f => (
              <div key={f.rule_id} className="finding-row">
                <span className="rule-id">{f.rule_id}</span>
                <span>{f.framework}</span>
                <span className={f.data_residency_required ? 'required' : ''}>
                  {f.data_residency_required ? 'Required' : 'No'}
                </span>
                <span className={f.encryption_required ? 'required' : ''}>
                  {f.encryption_required ? 'Required' : 'No'}
                </span>
              </div>
            ))}
          </div>
        </section>
      )}
    </div>
  )
}
