import { useState, useEffect, useCallback } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'

interface TourStep {
  path: string
  title: string
  description: string
  target?: string
  position?: 'top' | 'bottom' | 'left' | 'right' | 'center'
}

const TOUR_STEPS: TourStep[] = [
  {
    path: '/',
    title: 'Welcome to TAA',
    description: 'The Telco Analytics Accelerator auto-generates production-ready BigQuery data warehouses, Terraform infrastructure, Dataflow pipelines, Airflow DAGs, and compliance reports — all from a single configuration.',
    position: 'center',
  },
  {
    path: '/',
    title: 'Business Impact',
    description: 'TAA reduces analytics platform build time by 95%. Generate 50+ tables across 7 telco domains with 910 columns, full PII classification, and compliance for 10 global jurisdictions — in minutes, not months.',
    target: '.benefits-grid',
    position: 'top',
  },
  {
    path: '/',
    title: 'Platform Integrations',
    description: 'End-to-end code generation across BigQuery, Terraform, Dataflow, Airflow, Vertex AI, Looker, and BSS/OSS vendors. Every artefact is production-ready with best practices baked in.',
    target: '.integrations-grid',
    position: 'top',
  },
  {
    path: '/generate',
    title: 'Step 1: Select Domains',
    description: 'Choose from 7 telco domains: subscriber, product catalogue, CDR events, revenue/invoicing, interconnect/roaming, network inventory, and usage analytics. Each domain contains pre-built tables with industry-standard schemas.',
    target: '.form-grid .card:first-child',
    position: 'right',
  },
  {
    path: '/generate',
    title: 'Step 2: Region & Jurisdiction',
    description: 'Filter by region (Middle East, Europe, Asia Pacific, Africa) to see applicable compliance jurisdictions. Each jurisdiction maps to a GCP region with specific data residency and encryption requirements.',
    target: '.form-grid .card:nth-child(2)',
    position: 'left',
  },
  {
    path: '/generate',
    title: 'Step 3: Choose Artefacts',
    description: 'Select which artefacts to generate: BigQuery DDL (always included), Terraform IaC, Dataflow pipelines, Airflow DAGs, and compliance reports. Download everything as a single ZIP package.',
    target: '.form-grid .card:nth-child(4)',
    position: 'left',
  },
  {
    path: '/domains',
    title: 'Domain Explorer',
    description: 'Browse the full Logical Data Model interactively. Click any domain to load its tables, then expand tables to see every column — with BigQuery types, nullability, and PII classifications highlighted.',
    position: 'center',
  },
  {
    path: '/compliance',
    title: 'Compliance Assessment',
    description: 'Run regulatory compliance checks across 10 jurisdictions. Filter by region to see applicable frameworks — GDPR, PDPL, POPIA, DPDP, and more. Each assessment evaluates data residency, encryption, and PII handling requirements.',
    target: '.jurisdiction-cards',
    position: 'top',
  },
  {
    path: '/analytics',
    title: 'Analytics Templates',
    description: '12 pre-built templates: 5 SQL analytics queries (ARPU, churn, revenue leakage), 3 Vertex AI notebooks (ML models for churn prediction, revenue leakage, subscriber LTV), and 4 Looker dashboard configurations.',
    position: 'center',
  },
  {
    path: '/users',
    title: 'Role-Based Access Control',
    description: 'Three roles with granular permissions: Users can view and generate, Admins can run compliance checks and upload schemas, Management has full access including user management. All actions are permission-gated.',
    position: 'center',
  },
  {
    path: '/',
    title: 'Tour Complete',
    description: 'You\'ve seen the full TAA platform. Start generating artefacts by clicking "Generate Artefacts" on the home page, or explore any section from the sidebar. TAA is ready for production use.',
    position: 'center',
  },
]

interface Props {
  active: boolean
  onEnd: () => void
}

export default function GuidedTour({ active, onEnd }: Props) {
  const [step, setStep] = useState(0)
  const navigate = useNavigate()
  const location = useLocation()

  const currentStep = TOUR_STEPS[step]
  const isLastStep = step === TOUR_STEPS.length - 1
  const progress = ((step + 1) / TOUR_STEPS.length) * 100

  const goToStep = useCallback((newStep: number) => {
    const target = TOUR_STEPS[newStep]
    if (target && target.path !== location.pathname) {
      navigate(target.path)
    }
    setStep(newStep)
  }, [location.pathname, navigate])

  useEffect(() => {
    if (active && currentStep.path !== location.pathname) {
      navigate(currentStep.path)
    }
  }, [active, currentStep.path, location.pathname, navigate])

  useEffect(() => {
    if (!active) {
      setStep(0)
    }
  }, [active])

  // Scroll target into view
  useEffect(() => {
    if (active && currentStep.target) {
      const timer = setTimeout(() => {
        const el = document.querySelector(currentStep.target!)
        if (el) {
          el.scrollIntoView({ behavior: 'smooth', block: 'center' })
        }
      }, 300)
      return () => clearTimeout(timer)
    }
  }, [active, step, currentStep.target])

  // Keyboard navigation
  useEffect(() => {
    if (!active) return
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'ArrowRight' || e.key === ' ') {
        e.preventDefault()
        if (isLastStep) onEnd()
        else goToStep(step + 1)
      } else if (e.key === 'ArrowLeft' && step > 0) {
        e.preventDefault()
        goToStep(step - 1)
      } else if (e.key === 'Escape') {
        onEnd()
      }
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [active, step, isLastStep, onEnd, goToStep])

  if (!active) return null

  return (
    <>
      <div className="tour-overlay" onClick={onEnd} />
      {currentStep.target && <TourHighlight target={currentStep.target} />}
      <div className={`tour-dialog tour-${currentStep.position || 'center'}`}>
        <div className="tour-progress">
          <div className="tour-progress-bar" style={{ width: `${progress}%` }} />
        </div>
        <div className="tour-step-count">
          Step {step + 1} of {TOUR_STEPS.length}
        </div>
        <h3 className="tour-title">{currentStep.title}</h3>
        <p className="tour-desc">{currentStep.description}</p>
        <div className="tour-actions">
          <button
            className="btn btn-sm"
            onClick={onEnd}
          >
            Skip Tour
          </button>
          <div className="tour-nav">
            {step > 0 && (
              <button
                className="btn btn-sm"
                onClick={() => goToStep(step - 1)}
              >
                Back
              </button>
            )}
            <button
              className="btn btn-sm btn-primary"
              onClick={() => {
                if (isLastStep) onEnd()
                else goToStep(step + 1)
              }}
            >
              {isLastStep ? 'Finish' : 'Next'}
            </button>
          </div>
        </div>
      </div>
    </>
  )
}

function TourHighlight({ target }: { target: string }) {
  const [rect, setRect] = useState<DOMRect | null>(null)

  useEffect(() => {
    const update = () => {
      const el = document.querySelector(target)
      if (el) setRect(el.getBoundingClientRect())
    }
    update()
    const timer = setTimeout(update, 350)
    return () => clearTimeout(timer)
  }, [target])

  if (!rect) return null

  return (
    <div
      className="tour-highlight"
      style={{
        top: rect.top - 8,
        left: rect.left - 8,
        width: rect.width + 16,
        height: rect.height + 16,
      }}
    />
  )
}
