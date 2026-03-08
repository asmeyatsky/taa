import { useState, useMemo } from 'react'
import { useQuery, useMutation } from '@tanstack/react-query'
import { useAuth } from '../auth/AuthContext'
import { api } from '../api/client'
import type { ExportResponse, JurisdictionInfo } from '../api/types'

const REGIONS: { label: string; match: (j: JurisdictionInfo) => boolean }[] = [
  { label: 'All Regions', match: () => true },
  { label: 'Middle East', match: j => j.gcp_region.startsWith('me-') },
  { label: 'Europe', match: j => j.gcp_region.startsWith('europe-') },
  { label: 'Asia Pacific', match: j => j.gcp_region.startsWith('asia-') },
  { label: 'Africa', match: j => j.gcp_region.startsWith('africa-') },
]

export default function GeneratePage() {
  const { hasPermission } = useAuth()
  const [selectedDomains, setSelectedDomains] = useState<string[]>([])
  const [selectedRegion, setSelectedRegion] = useState('All Regions')
  const [jurisdiction, setJurisdiction] = useState('SA')
  const [vendor, setVendor] = useState<string>('')
  const [includeTerraform, setIncludeTerraform] = useState(true)
  const [includePipelines, setIncludePipelines] = useState(true)
  const [includeDags, setIncludeDags] = useState(true)
  const [includeCompliance, setIncludeCompliance] = useState(true)
  const [result, setResult] = useState<ExportResponse | null>(null)

  const domains = useQuery({ queryKey: ['domains'], queryFn: api.getDomains })
  const vendors = useQuery({ queryKey: ['vendors'], queryFn: api.getVendors })
  const jurisdictions = useQuery({ queryKey: ['jurisdictions'], queryFn: api.getJurisdictions })

  const regionFilter = REGIONS.find(r => r.label === selectedRegion) ?? REGIONS[0]
  const filteredJurisdictions = useMemo(
    () => jurisdictions.data?.filter(regionFilter.match) ?? [],
    [jurisdictions.data, selectedRegion],
  )

  // Auto-select first jurisdiction when region changes and current selection is out of scope
  const activeJurisdiction = filteredJurisdictions.find(j => j.code === jurisdiction)
    ? jurisdiction
    : filteredJurisdictions[0]?.code ?? ''

  if (activeJurisdiction !== jurisdiction && activeJurisdiction) {
    setJurisdiction(activeJurisdiction)
  }

  const exportMutation = useMutation({
    mutationFn: () =>
      api.exportPack({
        domains: selectedDomains,
        jurisdiction,
        vendor: vendor || undefined,
        include_terraform: includeTerraform,
        include_pipelines: includePipelines,
        include_dags: includeDags,
        include_compliance: includeCompliance,
      }),
    onSuccess: (data) => setResult(data),
  })

  const toggleDomain = (name: string) => {
    setSelectedDomains(prev =>
      prev.includes(name) ? prev.filter(d => d !== name) : [...prev, name]
    )
  }

  const selectAllDomains = () => {
    if (domains.data) {
      setSelectedDomains(
        selectedDomains.length === domains.data.length
          ? []
          : domains.data.map(d => d.name)
      )
    }
  }

  return (
    <div className="page">
      <h2>Generate Artefacts</h2>
      <p className="page-desc">
        Select domains, jurisdiction, and artefact types to generate a complete BigQuery analytics pack.
      </p>

      <div className="form-grid">
        <section className="card">
          <h3>1. Select Domains</h3>
          {domains.isLoading && <p className="loading">Loading domains...</p>}
          {domains.data && (
            <>
              <button className="btn btn-sm" onClick={selectAllDomains}>
                {selectedDomains.length === domains.data.length ? 'Deselect All' : 'Select All'}
              </button>
              <div className="chip-group">
                {domains.data.map(d => (
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
            </>
          )}
        </section>

        <section className="card">
          <h3>2. Region & Jurisdiction</h3>
          <div className="chip-group" style={{ marginBottom: '0.75rem' }}>
            {REGIONS.map(r => (
              <button
                key={r.label}
                className={`chip ${selectedRegion === r.label ? 'chip-active' : ''}`}
                onClick={() => setSelectedRegion(r.label)}
              >
                {r.label}
              </button>
            ))}
          </div>
          {jurisdictions.isLoading && <p className="loading">Loading...</p>}
          {filteredJurisdictions.length > 0 && (
            <select
              className="select"
              value={jurisdiction}
              onChange={e => setJurisdiction(e.target.value)}
            >
              {filteredJurisdictions.map(j => (
                <option key={j.code} value={j.code}>
                  {j.name} ({j.framework}) — {j.gcp_region}
                </option>
              ))}
            </select>
          )}
        </section>

        <section className="card">
          <h3>3. BSS Vendor (optional)</h3>
          {vendors.isLoading && <p className="loading">Loading...</p>}
          {vendors.data && (
            <select
              className="select"
              value={vendor}
              onChange={e => setVendor(e.target.value)}
            >
              <option value="">None (canonical only)</option>
              {vendors.data.map(v => (
                <option key={v.name} value={v.name}>
                  {v.name} ({v.mapping_count} mappings)
                </option>
              ))}
            </select>
          )}
        </section>

        <section className="card">
          <h3>4. Artefacts</h3>
          <div className="checkbox-group">
            <label><input type="checkbox" checked={true} disabled /> BigQuery DDL</label>
            <label><input type="checkbox" checked={includeTerraform} onChange={e => setIncludeTerraform(e.target.checked)} /> Terraform IaC</label>
            <label><input type="checkbox" checked={includePipelines} onChange={e => setIncludePipelines(e.target.checked)} /> Dataflow Pipelines</label>
            <label><input type="checkbox" checked={includeDags} onChange={e => setIncludeDags(e.target.checked)} /> Airflow DAGs</label>
            <label><input type="checkbox" checked={includeCompliance} onChange={e => setIncludeCompliance(e.target.checked)} /> Compliance Reports</label>
          </div>
        </section>
      </div>

      <div className="action-bar">
        <button
          className="btn btn-primary btn-lg"
          disabled={selectedDomains.length === 0 || exportMutation.isPending}
          onClick={() => exportMutation.mutate()}
        >
          {exportMutation.isPending ? 'Generating...' : `Generate Pack (${selectedDomains.length} domain${selectedDomains.length !== 1 ? 's' : ''})`}
        </button>
      </div>

      {exportMutation.isError && (
        <div className="alert alert-error">
          Error: {(exportMutation.error as Error).message}
        </div>
      )}

      {result && (
        <section className="card result-card">
          <h3>{result.success ? 'Generation Complete' : 'Generation Failed'}</h3>
          <p>{result.file_count} files generated</p>
          {result.files.length > 0 && (
            <>
              <div className="file-list">
                {result.files.map(f => (
                  <div key={f.name} className="file-item">
                    <span className="file-name">{f.name}</span>
                    <span className="file-size">{(f.size / 1024).toFixed(1)} KB</span>
                    <span className="file-type">{f.type}</span>
                  </div>
                ))}
              </div>
              {hasPermission('generate:download') && (
                <a
                  className="btn btn-primary"
                  href={api.getDownloadUrl(result.download_id)}
                  download
                >
                  Download ZIP
                </a>
              )}
            </>
          )}
        </section>
      )}
    </div>
  )
}
