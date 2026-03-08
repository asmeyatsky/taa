import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { useAuth } from '../auth/AuthContext'
import { api } from '../api/client'

const integrations = [
  { name: 'BigQuery', icon: 'BQ', color: '#4285f4', desc: 'Auto-generated DDL with partitioning, clustering, and column-level security' },
  { name: 'Terraform', icon: 'TF', color: '#7b42bc', desc: 'Infrastructure-as-Code for datasets, KMS, DLP, audit logging, and IAM' },
  { name: 'Dataflow', icon: 'DF', color: '#4285f4', desc: 'Apache Beam pipelines with CDC, schema validation, and dead-letter queues' },
  { name: 'Airflow', icon: 'AF', color: '#017cee', desc: 'Production DAGs with inline SQL, data quality checks, and SLA alerting' },
  { name: 'Vertex AI', icon: 'VA', color: '#34a853', desc: 'Jupyter notebooks for churn prediction, revenue leakage, and subscriber LTV' },
  { name: 'Looker', icon: 'LK', color: '#4285f4', desc: 'Dashboard configurations for revenue assurance, churn, and 5G monetisation' },
  { name: 'GDPR / PDPL', icon: 'CP', color: '#ea4335', desc: '10 jurisdiction compliance frameworks with data residency and encryption rules' },
  { name: 'BSS/OSS', icon: 'BS', color: '#fbbc04', desc: 'Vendor schema import with auto-mapping for Amdocs, Ericsson, Nokia, Huawei' },
]

const benefits = [
  {
    title: 'Weeks to Minutes',
    stat: '95%',
    desc: 'Reduce analytics platform build time from months of manual work to automated code generation in minutes.',
  },
  {
    title: 'Production-Ready Output',
    stat: '50+',
    desc: 'Tables across 7 telco domains with 910 columns, partitioning strategies, and PII classification baked in.',
  },
  {
    title: 'Compliance by Default',
    stat: '10',
    desc: 'Jurisdictions covered — GDPR, PDPL, LGPD, POPIA, and more. Data residency and encryption requirements enforced automatically.',
  },
  {
    title: 'Vendor Agnostic',
    stat: '653',
    desc: 'Pre-built vendor field mappings across Amdocs, Ericsson, Nokia, and Huawei. Import any BSS schema and auto-map to the canonical model.',
  },
]

export default function HomePage() {
  const { user } = useAuth()
  const health = useQuery({ queryKey: ['health'], queryFn: api.health })
  const domains = useQuery({ queryKey: ['domains'], queryFn: api.getDomains })

  const totalTables = domains.data?.reduce((sum, d) => sum + d.table_count, 0) ?? 0

  return (
    <div className="page home-page">
      {/* Hero */}
      <section className="hero">
        <div className="hero-content">
          <h1>Telco Analytics Accelerator</h1>
          <p className="hero-subtitle">
            Auto-generate production-ready BigQuery data warehouses, Terraform infrastructure,
            Dataflow pipelines, Airflow DAGs, and compliance reports from telco BSS/OSS configurations
            — in minutes, not months.
          </p>
          <div className="hero-actions">
            <Link to="/generate" className="btn btn-primary btn-lg">
              Generate Artefacts
            </Link>
            <Link to="/domains" className="btn btn-lg">
              Explore Data Model
            </Link>
          </div>
          {health.data && (
            <div className="hero-status">
              <span className="status-dot" />
              System Online &middot; v{health.data.version}
              {domains.data && <> &middot; {domains.data.length} domains &middot; {totalTables} tables</>}
            </div>
          )}
        </div>
      </section>

      {/* Business Benefits */}
      <section className="section">
        <h2 className="section-title">Business Impact</h2>
        <div className="benefits-grid">
          {benefits.map(b => (
            <div key={b.title} className="benefit-card">
              <div className="benefit-stat">{b.stat}</div>
              <h3>{b.title}</h3>
              <p>{b.desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Integrations */}
      <section className="section">
        <h2 className="section-title">Platform Integrations</h2>
        <p className="section-desc">
          End-to-end code generation across the Google Cloud analytics stack, with built-in BSS vendor support and global compliance.
        </p>
        <div className="integrations-grid">
          {integrations.map(ig => (
            <div key={ig.name} className="integration-card">
              <div className="integration-icon" style={{ background: ig.color }}>
                {ig.icon}
              </div>
              <div className="integration-info">
                <h4>{ig.name}</h4>
                <p>{ig.desc}</p>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* Quick Access by Role */}
      {user && (
        <section className="section">
          <h2 className="section-title">Quick Access</h2>
          <div className="quick-access-grid">
            <Link to="/generate" className="quick-card">
              <span className="quick-icon">&#9889;</span>
              <h4>Generate Pack</h4>
              <p>Create DDL, Terraform, pipelines, DAGs, and compliance reports</p>
            </Link>
            <Link to="/domains" className="quick-card">
              <span className="quick-icon">&#128202;</span>
              <h4>Domain Explorer</h4>
              <p>Browse tables, columns, types, and PII classifications</p>
            </Link>
            <Link to="/compliance" className="quick-card">
              <span className="quick-icon">&#128274;</span>
              <h4>Compliance</h4>
              <p>Run regulatory assessments across 10 jurisdictions</p>
            </Link>
            <Link to="/analytics" className="quick-card">
              <span className="quick-icon">&#128200;</span>
              <h4>Analytics</h4>
              <p>SQL templates, Vertex AI notebooks, and Looker dashboards</p>
            </Link>
          </div>
        </section>
      )}
    </div>
  )
}
