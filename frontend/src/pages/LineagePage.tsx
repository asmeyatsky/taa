import { useQuery } from '@tanstack/react-query'
import { api } from '../api/client'

interface PipelineStage {
  id: string
  label: string
  type: 'source' | 'ingestion' | 'warehouse' | 'transform' | 'analytics' | 'output'
  color: string
  items: string[]
}

const STAGES: PipelineStage[] = [
  {
    id: 'bss',
    label: 'BSS/OSS Sources',
    type: 'source',
    color: '#fbbc04',
    items: ['Amdocs CRM', 'Ericsson BSCS', 'Huawei CBS', 'Oracle BRM', 'CDR Streams', 'Network Elements'],
  },
  {
    id: 'ingestion',
    label: 'Dataflow Ingestion',
    type: 'ingestion',
    color: '#4285f4',
    items: ['CDC Pipeline', 'Schema Validation', 'PII Detection', 'Dead Letter Queue', 'Batch / Streaming'],
  },
  {
    id: 'warehouse',
    label: 'BigQuery Warehouse',
    type: 'warehouse',
    color: '#4285f4',
    items: ['Raw Layer', 'Curated Layer', 'Analytics Layer', 'Partitioned Tables', 'Column-Level Security'],
  },
  {
    id: 'orchestration',
    label: 'Airflow Orchestration',
    type: 'transform',
    color: '#017cee',
    items: ['Daily DAGs', 'Data Quality Checks', 'SLA Monitoring', 'Alerting', 'Dependency Management'],
  },
  {
    id: 'analytics',
    label: 'Analytics & ML',
    type: 'analytics',
    color: '#34a853',
    items: ['Vertex AI Notebooks', 'BigQuery ML', 'Churn Prediction', 'Revenue Leakage', 'Subscriber LTV'],
  },
  {
    id: 'output',
    label: 'Dashboards & Reports',
    type: 'output',
    color: '#ea4335',
    items: ['Looker Dashboards', 'Compliance Reports', 'Revenue Assurance', 'Churn Analytics', '5G Monetisation'],
  },
]

export default function LineagePage() {
  const domains = useQuery({ queryKey: ['domains'], queryFn: api.getDomains })
  const totalTables = domains.data?.reduce((sum, d) => sum + d.table_count, 0) ?? 0

  return (
    <div className="page">
      <h2>Data Pipeline & Lineage</h2>
      <p className="page-desc">
        End-to-end data flow from BSS/OSS sources through ingestion, warehousing, orchestration, and analytics to dashboards and reports.
      </p>

      {/* Pipeline flow */}
      <div className="pipeline-flow">
        {STAGES.map((stage, i) => (
          <div key={stage.id} className="pipeline-stage-wrapper">
            <div className="pipeline-stage">
              <div className="stage-header" style={{ borderColor: stage.color }}>
                <div className="stage-icon" style={{ background: stage.color }}>
                  {stage.label.charAt(0)}
                </div>
                <h3>{stage.label}</h3>
              </div>
              <div className="stage-items">
                {stage.items.map(item => (
                  <div key={item} className="stage-item">{item}</div>
                ))}
              </div>
            </div>
            {i < STAGES.length - 1 && (
              <div className="pipeline-arrow">
                <svg width="40" height="24" viewBox="0 0 40 24">
                  <path d="M0 12 L30 12 M24 6 L30 12 L24 18" stroke="var(--text-dim)" strokeWidth="2" fill="none" />
                </svg>
              </div>
            )}
          </div>
        ))}
      </div>

      {/* Domain lineage detail */}
      <section className="card" style={{ marginTop: '2rem' }}>
        <h3>Domain Coverage</h3>
        <p className="page-desc" style={{ marginBottom: '1rem' }}>
          Each domain flows through all pipeline stages. TAA generates every artefact needed for the complete journey.
        </p>
        <div className="lineage-domain-grid">
          {domains.data?.map(d => (
            <div key={d.name} className="lineage-domain-card">
              <div className="lineage-domain-header">
                <span className="lineage-domain-name">{d.name}</span>
                <span className="badge">{d.table_count} tables</span>
              </div>
              <div className="lineage-artefacts">
                <span className="lineage-tag lineage-ddl">DDL</span>
                <span className="lineage-tag lineage-tf">Terraform</span>
                <span className="lineage-tag lineage-df">Dataflow</span>
                <span className="lineage-tag lineage-dag">DAG</span>
                <span className="lineage-tag lineage-comp">Compliance</span>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* Infrastructure overview */}
      <section className="card">
        <h3>Infrastructure Components</h3>
        <div className="infra-grid">
          <div className="infra-card">
            <h4>Terraform Modules</h4>
            <div className="infra-items">
              <div className="infra-item">BigQuery Datasets & Tables</div>
              <div className="infra-item">Cloud KMS Encryption Keys</div>
              <div className="infra-item">DLP Inspection Templates</div>
              <div className="infra-item">Audit Logging Configuration</div>
              <div className="infra-item">Vertex AI Workbench</div>
              <div className="infra-item">IAM Bindings</div>
            </div>
          </div>
          <div className="infra-card">
            <h4>Data Quality Checks</h4>
            <div className="infra-items">
              <div className="infra-item">Row count validation</div>
              <div className="infra-item">Null percentage thresholds</div>
              <div className="infra-item">Duplicate detection</div>
              <div className="infra-item">Schema drift monitoring</div>
              <div className="infra-item">Freshness SLA alerts</div>
              <div className="infra-item">Custom SQL assertions</div>
            </div>
          </div>
          <div className="infra-card">
            <h4>Security & Compliance</h4>
            <div className="infra-items">
              <div className="infra-item">Column-level policy tags</div>
              <div className="infra-item">PII auto-classification</div>
              <div className="infra-item">KMS key rotation</div>
              <div className="infra-item">Data residency enforcement</div>
              <div className="infra-item">Encryption at rest</div>
              <div className="infra-item">Audit trail logging</div>
            </div>
          </div>
        </div>
      </section>

      {domains.data && (
        <div className="lineage-summary">
          {domains.data.length} domains &middot; {totalTables} tables &middot; 6 pipeline stages &middot; 5 artefact types per domain
        </div>
      )}
    </div>
  )
}
