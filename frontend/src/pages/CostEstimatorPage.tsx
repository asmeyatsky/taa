import { useState, useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api } from '../api/client'

const CLOUD_PRICING = {
  gcp: {
    label: 'Google Cloud',
    color: '#4285f4',
    storage_per_gb: 0.02,
    query_per_tb: 6.25,
    streaming_per_gb: 0.05,
    dataflow_per_vcpu_hr: 0.056,
    terraform_modules: 'Included',
    ml_per_node_hr: 0.45,
  },
  aws: {
    label: 'AWS',
    color: '#ff9900',
    storage_per_gb: 0.023,
    query_per_tb: 5.00,
    streaming_per_gb: 0.04,
    dataflow_per_vcpu_hr: 0.048,
    terraform_modules: 'Included',
    ml_per_node_hr: 0.532,
  },
  azure: {
    label: 'Azure',
    color: '#0078d4',
    storage_per_gb: 0.021,
    query_per_tb: 6.00,
    streaming_per_gb: 0.045,
    dataflow_per_vcpu_hr: 0.052,
    terraform_modules: 'Included',
    ml_per_node_hr: 0.48,
  },
}

export default function CostEstimatorPage() {
  const [subscribers, setSubscribers] = useState(1_000_000)
  const [cdrPerDay, setCdrPerDay] = useState(5_000)
  const [selectedDomains, setSelectedDomains] = useState<string[]>([])
  const [retentionMonths, setRetentionMonths] = useState(12)

  const domains = useQuery({ queryKey: ['domains'], queryFn: api.getDomains })

  const toggleDomain = (name: string) => {
    setSelectedDomains(prev =>
      prev.includes(name) ? prev.filter(d => d !== name) : [...prev, name]
    )
  }

  const estimates = useMemo(() => {
    const domainCount = selectedDomains.length || 1
    const tableCount = domains.data
      ?.filter(d => selectedDomains.includes(d.name))
      .reduce((sum, d) => sum + d.table_count, 0) ?? 10

    // Estimate storage: ~200 bytes per subscriber row, ~500 bytes per CDR
    const subscriberStorageGB = (subscribers * 200 * tableCount * 0.3) / (1024 ** 3)
    const cdrStorageGB = (cdrPerDay * 1000 * 500 * 30 * retentionMonths) / (1024 ** 3)
    const totalStorageGB = subscriberStorageGB + cdrStorageGB

    // Estimate queries: ~50 queries/day, scanning ~10% of data each
    const dailyQueryTB = (totalStorageGB * 0.1 * 50) / 1024
    const monthlyQueryTB = dailyQueryTB * 30

    // Streaming ingestion
    const dailyStreamingGB = (cdrPerDay * 1000 * 500) / (1024 ** 3)
    const monthlyStreamingGB = dailyStreamingGB * 30

    // Dataflow: ~2 vCPU per domain, 24/7
    const dataflowVcpuHrs = domainCount * 2 * 24 * 30

    // ML: ~4 hours per week for training
    const mlNodeHrs = 4 * 4.3 * domainCount * 0.3

    return Object.entries(CLOUD_PRICING).map(([key, pricing]) => {
      const storageCost = totalStorageGB * pricing.storage_per_gb
      const queryCost = monthlyQueryTB * pricing.query_per_tb
      const streamingCost = monthlyStreamingGB * pricing.streaming_per_gb
      const dataflowCost = dataflowVcpuHrs * pricing.dataflow_per_vcpu_hr
      const mlCost = mlNodeHrs * pricing.ml_per_node_hr
      const total = storageCost + queryCost + streamingCost + dataflowCost + mlCost

      return {
        cloud: key,
        label: pricing.label,
        color: pricing.color,
        storageCost,
        queryCost,
        streamingCost,
        dataflowCost,
        mlCost,
        total,
        storageGB: totalStorageGB,
        queryTB: monthlyQueryTB,
      }
    })
  }, [subscribers, cdrPerDay, selectedDomains, retentionMonths, domains.data])

  const formatCurrency = (n: number) =>
    n >= 1000 ? `$${(n / 1000).toFixed(1)}K` : `$${n.toFixed(0)}`

  return (
    <div className="page">
      <h2>Cost Estimator</h2>
      <p className="page-desc">
        Estimate monthly cloud infrastructure costs based on subscriber count, CDR volume, and domain selection. Compare across GCP, AWS, and Azure.
      </p>

      <div className="form-grid">
        <section className="card">
          <h3>Workload Parameters</h3>
          <div className="slider-group">
            <div className="slider-field">
              <label>Subscribers: <strong>{(subscribers / 1_000_000).toFixed(1)}M</strong></label>
              <input
                type="range"
                className="slider"
                min={100000}
                max={50000000}
                step={100000}
                value={subscribers}
                onChange={e => setSubscribers(Number(e.target.value))}
              />
              <div className="slider-range"><span>100K</span><span>50M</span></div>
            </div>
            <div className="slider-field">
              <label>CDR Events/day (thousands): <strong>{cdrPerDay.toLocaleString()}K</strong></label>
              <input
                type="range"
                className="slider"
                min={100}
                max={100000}
                step={100}
                value={cdrPerDay}
                onChange={e => setCdrPerDay(Number(e.target.value))}
              />
              <div className="slider-range"><span>100K</span><span>100M</span></div>
            </div>
            <div className="slider-field">
              <label>Data Retention: <strong>{retentionMonths} months</strong></label>
              <input
                type="range"
                className="slider"
                min={1}
                max={60}
                step={1}
                value={retentionMonths}
                onChange={e => setRetentionMonths(Number(e.target.value))}
              />
              <div className="slider-range"><span>1 mo</span><span>5 years</span></div>
            </div>
          </div>
        </section>

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
                <span className="chip-badge">{d.table_count}</span>
              </button>
            ))}
          </div>
        </section>
      </div>

      {/* Cloud comparison */}
      <div className="cost-comparison">
        {estimates.map(est => (
          <div key={est.cloud} className="cost-card">
            <div className="cost-card-header" style={{ borderColor: est.color }}>
              <div className="cost-cloud-icon" style={{ background: est.color }}>
                {est.cloud.toUpperCase().slice(0, 3)}
              </div>
              <div>
                <h3>{est.label}</h3>
                <div className="cost-total">{formatCurrency(est.total)}/mo</div>
              </div>
            </div>
            <div className="cost-breakdown">
              <div className="cost-line">
                <span>Storage ({est.storageGB.toFixed(0)} GB)</span>
                <span>{formatCurrency(est.storageCost)}</span>
              </div>
              <div className="cost-line">
                <span>Queries ({est.queryTB.toFixed(1)} TB/mo)</span>
                <span>{formatCurrency(est.queryCost)}</span>
              </div>
              <div className="cost-line">
                <span>Streaming Ingestion</span>
                <span>{formatCurrency(est.streamingCost)}</span>
              </div>
              <div className="cost-line">
                <span>Dataflow / Compute</span>
                <span>{formatCurrency(est.dataflowCost)}</span>
              </div>
              <div className="cost-line">
                <span>ML / AI Training</span>
                <span>{formatCurrency(est.mlCost)}</span>
              </div>
            </div>
          </div>
        ))}
      </div>

      <div className="lineage-summary" style={{ marginTop: '1.5rem' }}>
        Estimates are indicative based on published on-demand pricing. Committed use discounts can reduce costs by 30-60%.
      </div>
    </div>
  )
}
