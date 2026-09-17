import { useEffect, useMemo, useState } from 'react'
import {
  ArrowLeft,
  AlertTriangle,
  Bot,
  CarFront,
  Check,
  CheckCircle2,
  ChevronDown,
  CircleAlert,
  Clock3,
  ExternalLink,
  FileCheck2,
  History,
  Inbox,
  Languages,
  Link2,
  Mail,
  MessageCircle,
  PanelLeftClose,
  PhoneCall,
  Play,
  QrCode,
  RefreshCcw,
  Search,
  Send,
  Settings2,
  ShieldCheck,
  Sparkles,
  Smartphone,
  UserCheck,
  UserRound,
  X,
} from 'lucide-react'
import { QRCodeSVG } from 'qrcode.react'
import { initialConnectors, initialInquiries } from './data'
import type { Connector, Inquiry, InquiryClass } from './types'
import './manager.css'

type ManagerSection = 'inquiries' | 'workflow' | 'connections'
type InquiryFilter = 'all' | 'needs_review' | 'ready' | 'sent'

type VehicleWorkflowSummary = {
  jobId: string; registration: string; customerId: string; vehicle: string
  currentStage: string; currentOwnerRole: string; version: number; updatedAt: string
}
type WorkflowAction = {
  action: string; label: string; requiredRole: string; requiredRoleLabel: string
  nextStage: string; nextOwnerRole: string
}
type WorkflowHistoryItem = {
  previousStage: string; newStage: string; action: string; completedBy: string
  completedByRole: string; nextOwnerRole: string; notes: string; simulated: boolean; createdAt: string
}
type VehicleWorkflowDetail = VehicleWorkflowSummary & {
  currentStageCode: string; currentOwnerRoleCode: string
  allowedActions: WorkflowAction[]; history: WorkflowHistoryItem[]
}

const workflowRoles = [
  { code: 'RECEPTION', label: 'Reception' },
  { code: 'TECHNICIAN', label: 'Technician' },
  { code: 'QUALITY_CONTROLLER', label: 'Quality controller' },
  { code: 'SERVICE_ADVISER', label: 'Service adviser' },
]

const inquiryClasses: InquiryClass[] = [
  'Collection status',
  'Repair status',
  'Booking change',
  'Repeated enquiry',
  'General request',
]

const channelIcons = {
  WhatsApp: MessageCircle,
  Gmail: Mail,
  'Phone note': PhoneCall,
  'Web chat': MessageCircle,
}

function statusLabel(status: Inquiry['status']) {
  return {
    needs_review: 'Needs review',
    ready: 'Ready to approve',
    sent: 'Sent',
    rejected: 'Needs revision',
  }[status]
}

export function ManagerApp() {
  const [section, setSection] = useState<ManagerSection>('inquiries')
  const [filter, setFilter] = useState<InquiryFilter>('all')
  const [search, setSearch] = useState('')
  const [inquiries, setInquiries] = useState(initialInquiries)
  const [selectedId, setSelectedId] = useState(initialInquiries[0].id)
  const [connectors, setConnectors] = useState(initialConnectors)
  const [configuring, setConfiguring] = useState<Connector['id'] | null>(null)
  const [accountLabel, setAccountLabel] = useState('')
  const [toast, setToast] = useState('')
  const [vehicleQuery, setVehicleQuery] = useState('')
  const [vehicleWorkflows, setVehicleWorkflows] = useState<VehicleWorkflowSummary[]>([])
  const [selectedJobId, setSelectedJobId] = useState<string | null>(null)
  const [vehicleWorkflow, setVehicleWorkflow] = useState<VehicleWorkflowDetail | null>(null)
  const [workflowRole, setWorkflowRole] = useState('QUALITY_CONTROLLER')
  const [workflowBusy, setWorkflowBusy] = useState(false)
  const [phoneDemoOpen, setPhoneDemoOpen] = useState(false)
  const [phoneDemoUrl, setPhoneDemoUrl] = useState(() => `${window.location.origin}/`)

  async function refreshInquiries() {
    try {
      const response = await fetch('/api/manager/inquiries')
      if (!response.ok) return
      const data = await response.json() as Inquiry[]
      setInquiries(data)
      if (data.length) setSelectedId((current) => data.some((item) => item.id === current) ? current : data[0].id)
    } catch {
      // Keep the seeded frontend data visible if the API is not running yet.
    }
  }

  useEffect(() => {
    void refreshInquiries()
    const poll = window.setInterval(() => void refreshInquiries(), 3000)
    return () => window.clearInterval(poll)
  }, [])

  async function refreshVehicleWorkflows(query = vehicleQuery) {
    try {
      const response = await fetch(`/api/manager/vehicles?query=${encodeURIComponent(query)}`)
      if (!response.ok) return
      const data = await response.json() as VehicleWorkflowSummary[]
      setVehicleWorkflows(data)
      const jobId = data.some((item) => item.jobId === selectedJobId) ? selectedJobId : data[0]?.jobId ?? null
      setSelectedJobId(jobId)
      if (jobId) {
        const detailResponse = await fetch(`/api/manager/vehicles/${jobId}/workflow`)
        if (detailResponse.ok) setVehicleWorkflow(await detailResponse.json() as VehicleWorkflowDetail)
      } else {
        setVehicleWorkflow(null)
      }
    } catch {
      setVehicleWorkflows([])
      setVehicleWorkflow(null)
    }
  }

  async function selectVehicleWorkflow(jobId: string) {
    setSelectedJobId(jobId)
    try {
      const response = await fetch(`/api/manager/vehicles/${jobId}/workflow`)
      if (response.ok) setVehicleWorkflow(await response.json() as VehicleWorkflowDetail)
    } catch {
      showToast('Vehicle workflow could not be loaded')
    }
  }

  const filteredInquiries = useMemo(() => {
    const query = search.trim().toLowerCase()
    return inquiries.filter((inquiry) => {
      const matchesFilter = filter === 'all' || inquiry.status === filter
      const matchesSearch = !query || [inquiry.id, inquiry.customerId, inquiry.message, inquiry.vehicle]
        .some((value) => value.toLowerCase().includes(query))
      return matchesFilter && matchesSearch
    })
  }, [filter, inquiries, search])
  const selected = filteredInquiries.find((inquiry) => inquiry.id === selectedId)
    ?? filteredInquiries[0]
    ?? inquiries[0]

  const counts = {
    review: inquiries.filter((item) => item.status === 'needs_review').length,
    ready: inquiries.filter((item) => item.status === 'ready').length,
    sent: inquiries.filter((item) => item.status === 'sent').length,
  }

  function updateInquiry(id: string, changes: Partial<Inquiry>) {
    setInquiries((current) => current.map((inquiry) => inquiry.id === id ? { ...inquiry, ...changes } : inquiry))
  }

  function showToast(message: string) {
    setToast(message)
    window.setTimeout(() => setToast(''), 2800)
  }

  async function approveSelected() {
    if (!selected) return
    try {
      const response = await fetch(`/api/manager/reviews/${selected.id}/approve`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ final_response: selected.proposedResponse, classification: selected.classification }),
      })
      const result = await response.json() as { status?: string; mode?: string; detail?: string }
      if (!response.ok) throw new Error(result.detail ?? 'The response could not be delivered')
      await refreshInquiries()
      showToast(result.mode === 'gmail_api'
        ? `Response for ${selected.id} sent through Gmail`
        : `Response for ${selected.id} delivered in simulation`)
    } catch (error) {
      showToast(error instanceof Error ? error.message : 'Delivery failed')
    }
  }

  async function rejectSelected() {
    if (!selected) return
    try {
      const response = await fetch(`/api/manager/reviews/${selected.id}/reject`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ note: 'Manager rejected the proposed decision' }),
      })
      if (!response.ok) throw new Error('The review could not be rejected')
      await refreshInquiries()
      showToast(`${selected.id} returned for revision`)
    } catch (error) {
      showToast(error instanceof Error ? error.message : 'Review update failed')
    }
  }

  async function applyWorkflowAction(action: WorkflowAction) {
    if (!vehicleWorkflow || workflowBusy) return
    setWorkflowBusy(true)
    try {
      const response = await fetch(`/api/manager/vehicles/${vehicleWorkflow.jobId}/workflow/transition`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action: action.action, actor_role: workflowRole }),
      })
      const result = await response.json() as VehicleWorkflowDetail & { detail?: string }
      if (!response.ok) throw new Error(result.detail ?? 'The workflow action could not be applied')
      setVehicleWorkflow(result)
      await refreshVehicleWorkflows(vehicleQuery)
      await refreshInquiries()
      showToast(`${action.label} completed; ownership passed to ${action.nextOwnerRole}`)
    } catch (error) {
      showToast(error instanceof Error ? error.message : 'Workflow update failed')
    } finally {
      setWorkflowBusy(false)
    }
  }

  async function resetVehicleDemo() {
    if (!vehicleWorkflow || workflowBusy) return
    setWorkflowBusy(true)
    try {
      const response = await fetch(`/api/manager/vehicles/${vehicleWorkflow.jobId}/workflow/reset-demo`, {
        method: 'POST',
      })
      const result = await response.json() as VehicleWorkflowDetail & { detail?: string }
      if (!response.ok) throw new Error(result.detail ?? 'The demonstration could not be reset')
      setVehicleWorkflow(result)
      await refreshVehicleWorkflows(vehicleQuery)
      await refreshInquiries()
      showToast('Synthetic workflow reset to quality control pending')
    } catch (error) {
      showToast(error instanceof Error ? error.message : 'Reset failed')
    } finally {
      setWorkflowBusy(false)
    }
  }

  function beginConfiguration(connector: Connector) {
    if (connector.status === 'planned') return
    setConfiguring(connector.id)
    setAccountLabel(connector.accountLabel ?? '')
  }

  function saveConfiguration() {
    if (!configuring || !accountLabel.trim()) return
    setConnectors((current) => current.map((connector) => connector.id === configuring
      ? { ...connector, status: 'connected', accountLabel: accountLabel.trim() }
      : connector))
    showToast('Simulated connection saved')
    setConfiguring(null)
    setAccountLabel('')
  }

  return (
    <main className="manager-app">
      <aside className="manager-nav">
        <div className="manager-brand">
          <span><ShieldCheck size={21} /></span>
          <div><strong>SAGE Service</strong><small>Porsche exercise prototype</small></div>
        </div>

        <nav aria-label="Manager navigation">
          <button className={section === 'inquiries' ? 'active' : ''} onClick={() => setSection('inquiries')} type="button">
            <Inbox size={18} /><span>Inquiries</span><b>{counts.review + counts.ready}</b>
          </button>
          <button className={section === 'workflow' ? 'active' : ''} onClick={() => { setSection('workflow'); void refreshVehicleWorkflows() }} type="button">
            <CarFront size={18} /><span>Vehicle workflow</span>
          </button>
          <button className={section === 'connections' ? 'active' : ''} onClick={() => setSection('connections')} type="button">
            <Link2 size={18} /><span>Connections</span>
          </button>
          <button type="button" disabled><History size={18} /><span>Activity</span><em>Later</em></button>
          <button type="button" disabled><Settings2 size={18} /><span>Settings</span><em>Later</em></button>
        </nav>

        <div className="manager-nav-bottom">
          <a href="/" target="_blank" rel="noreferrer"><ExternalLink size={16} />Open customer portal</a>
          <div className="manager-user"><span>CS</span><div><strong>Customer-service lead</strong><small>Synthetic dealership</small></div></div>
        </div>
      </aside>

      <section className="manager-main">
        <header className="manager-topbar">
          <div>
            <p>Porsche dealership service · Exercise prototype</p>
            <h1>{section === 'inquiries' ? 'Inquiry review' : section === 'workflow' ? 'Vehicle workflow' : 'Channel connections'}</h1>
          </div>
          <div className="manager-top-actions">
            <span className="simulation-state"><span />Synthetic data · Simulated sends</span>
            <button className="phone-demo-trigger" type="button" aria-label="Open phone demo QR code" onClick={() => setPhoneDemoOpen(true)}><QrCode size={19} /></button>
            <button type="button" aria-label="Collapse navigation" disabled><PanelLeftClose size={19} /></button>
          </div>
        </header>

        {section === 'inquiries' ? (
          <InquiryWorkspace
            inquiries={filteredInquiries}
            selected={selected}
            counts={counts}
            filter={filter}
            search={search}
            onFilter={setFilter}
            onSearch={setSearch}
            onSelect={setSelectedId}
            onUpdate={updateInquiry}
            onApprove={approveSelected}
            onReject={rejectSelected}
          />
        ) : section === 'workflow' ? (
          <VehicleWorkflowWorkspace
            query={vehicleQuery}
            vehicles={vehicleWorkflows}
            selectedJobId={selectedJobId}
            detail={vehicleWorkflow}
            role={workflowRole}
            busy={workflowBusy}
            onQuery={setVehicleQuery}
            onSearch={() => void refreshVehicleWorkflows(vehicleQuery)}
            onSelect={(jobId) => void selectVehicleWorkflow(jobId)}
            onRole={setWorkflowRole}
            onAction={(action) => void applyWorkflowAction(action)}
            onReset={() => void resetVehicleDemo()}
          />
        ) : (
          <ConnectionsWorkspace
            connectors={connectors}
            configuring={configuring}
            accountLabel={accountLabel}
            onAccountLabel={setAccountLabel}
            onConfigure={beginConfiguration}
            onCancel={() => setConfiguring(null)}
            onSave={saveConfiguration}
          />
        )}
      </section>

      <p className="manager-disclaimer">Hackathon prototype using synthetic data. Not commissioned, endorsed, or operated by Porsche.</p>
      {phoneDemoOpen && (
        <div className="phone-demo-backdrop" role="presentation" onMouseDown={() => setPhoneDemoOpen(false)}>
          <section className="phone-demo-dialog" role="dialog" aria-modal="true" aria-labelledby="phone-demo-title" onMouseDown={(event) => event.stopPropagation()}>
            <button className="phone-demo-close" type="button" aria-label="Close phone demo" onClick={() => setPhoneDemoOpen(false)}><X size={18} /></button>
            <span className="phone-demo-icon"><Smartphone size={22} /></span>
            <p className="phone-demo-kicker">Customer experience</p>
            <h2 id="phone-demo-title">Open the demo on a phone</h2>
            <p>Scan this code with the phone camera. The phone and laptop must be able to reach the URL below.</p>
            <div className="phone-demo-qr"><QRCodeSVG value={phoneDemoUrl || `${window.location.origin}/`} size={176} level="M" marginSize={2} /></div>
            <label><span>Customer portal URL</span><input value={phoneDemoUrl} onChange={(event) => setPhoneDemoUrl(event.target.value)} inputMode="url" /></label>
            {(phoneDemoUrl.includes('127.0.0.1') || phoneDemoUrl.includes('localhost')) && <div className="phone-demo-warning"><AlertTriangle size={16} /><span>Localhost only works on this computer. For a phone, replace it with your computer’s Wi-Fi IP or the public preview URL.</span></div>}
            <a href={phoneDemoUrl} target="_blank" rel="noreferrer"><ExternalLink size={15} />Test customer portal</a>
          </section>
        </div>
      )}
      {toast && <div className="manager-toast" role="status"><CheckCircle2 size={18} />{toast}</div>}
    </main>
  )
}

type InquiryWorkspaceProps = {
  inquiries: Inquiry[]
  selected?: Inquiry
  counts: { review: number; ready: number; sent: number }
  filter: InquiryFilter
  search: string
  onFilter: (filter: InquiryFilter) => void
  onSearch: (search: string) => void
  onSelect: (id: string) => void
  onUpdate: (id: string, changes: Partial<Inquiry>) => void
  onApprove: () => void
  onReject: () => void
}

function InquiryWorkspace(props: InquiryWorkspaceProps) {
  const { inquiries, selected, counts, filter, search, onFilter, onSearch, onSelect, onUpdate, onApprove, onReject } = props
  const ChannelIcon = selected ? channelIcons[selected.channel] : MessageCircle

  return (
    <div className="manager-content">
      <div className="manager-metrics">
        <button type="button" onClick={() => onFilter('needs_review')} className={filter === 'needs_review' ? 'selected' : ''}>
          <span className="metric-icon review"><CircleAlert size={19} /></span><span><small>Needs review</small><strong>{counts.review}</strong></span>
        </button>
        <button type="button" onClick={() => onFilter('ready')} className={filter === 'ready' ? 'selected' : ''}>
          <span className="metric-icon ready"><FileCheck2 size={19} /></span><span><small>Ready to approve</small><strong>{counts.ready}</strong></span>
        </button>
        <button type="button" onClick={() => onFilter('sent')} className={filter === 'sent' ? 'selected' : ''}>
          <span className="metric-icon sent"><Send size={19} /></span><span><small>Sent</small><strong>{counts.sent}</strong></span>
        </button>
      </div>

      <div className="review-layout">
        <section className="inquiry-list" aria-label="Customer inquiry list">
          <div className="inquiry-toolbar">
            <label><Search size={16} /><input value={search} onChange={(event) => onSearch(event.target.value)} placeholder="Search requests…" /></label>
            <button type="button" onClick={() => onFilter('all')} className={filter === 'all' ? 'active' : ''}>All</button>
          </div>

          <div className="inquiry-rows">
            {inquiries.map((inquiry) => {
              const Icon = channelIcons[inquiry.channel]
              return (
                <button key={inquiry.id} type="button" className={selected?.id === inquiry.id ? 'selected' : ''} onClick={() => onSelect(inquiry.id)}>
                  <span className={`channel-icon ${inquiry.channel.toLowerCase().replace(' ', '-')}`}><Icon size={17} /></span>
                  <span className="inquiry-row-content">
                    <span><strong>{inquiry.customerId}</strong><time>{inquiry.receivedAt}</time></span>
                    <b>{inquiry.message}</b>
                    <span><em>{inquiry.classification}</em><i className={`inquiry-status ${inquiry.status}`}>{statusLabel(inquiry.status)}</i></span>
                  </span>
                </button>
              )
            })}
            {inquiries.length === 0 && <div className="empty-list">No inquiries match this view.</div>}
          </div>
        </section>

        {inquiries.length === 0 || !selected ? (
          <section className="review-detail-empty" aria-label="No matching inquiries">
            <Inbox size={34} />
            <h2>No inquiries match this view</h2>
            <p>Clear the search or choose another status filter to continue reviewing cases.</p>
            <button type="button" onClick={() => onFilter('all')}>Show all inquiries</button>
          </section>
        ) : (
        <section className="review-detail" aria-label={`Review ${selected.id}`}>
          <div className="review-detail-header">
            <div>
              <span className={`channel-icon ${selected.channel.toLowerCase().replace(' ', '-')}`}><ChannelIcon size={17} /></span>
              <div><h2>{selected.id}</h2><p>{selected.channel} · {selected.receivedAt}</p></div>
            </div>
            <span className={`detail-status ${selected.status}`}>{statusLabel(selected.status)}</span>
          </div>

          <div className="review-scroll">
            <section className="customer-request-block">
              <div className="section-kicker"><UserRound size={15} />Customer request · Synthetic case</div>
              <blockquote>{selected.message}</blockquote>
              <div className="customer-context">
                <span><strong>{selected.customerId}</strong> · {selected.vehicle}</span>
                <span><Languages size={14} />{selected.customerLanguage}</span>
              </div>
              {selected.customerEmail && <div className="customer-email"><Mail size={14} />Approved response will be delivered to <strong>{selected.customerEmail}</strong></div>}
            </section>

            <section className="review-section classification-section">
              <div className="section-title"><div><Sparkles size={16} /><h3>Agent classification</h3></div><span>Advisory · {selected.confidence}% confidence</span></div>
              <label>
                <span>Request class</span>
                <div className="manager-select">
                  <select value={selected.classification} onChange={(event) => onUpdate(selected.id, { classification: event.target.value as InquiryClass })}>
                    {inquiryClasses.map((item) => <option key={item}>{item}</option>)}
                  </select>
                  <ChevronDown size={16} />
                </div>
              </label>
            </section>

            <section className="review-section">
              <div className="section-title"><div><Bot size={16} /><h3>Decision and justification</h3></div></div>
              <p className="justification">{selected.justification}</p>
              <div className="rule-list">
                {selected.rules.map((rule) => <span key={rule}><ShieldCheck size={14} />{rule}</span>)}
              </div>
            </section>

            <section className="review-section">
              <div className="section-title"><div><FileCheck2 size={16} /><h3>Evidence checked</h3></div><span>{selected.evidence.length} sources</span></div>
              <div className="evidence-list">
                {selected.evidence.map((item) => (
                  <div key={`${item.source}-${item.value}`}>
                    <span><strong>{item.source}</strong><small>Observed {item.observedAt}</small></span>
                    <b className={item.tone ?? 'neutral'}>{item.value}</b>
                  </div>
                ))}
              </div>
            </section>

            <section className="review-section response-section">
              <div className="section-title"><div><MessageCircle size={16} /><h3>Proposed customer response</h3></div><span>Human-editable draft</span></div>
              <textarea value={selected.proposedResponse} onChange={(event) => onUpdate(selected.id, { proposedResponse: event.target.value })} rows={5} />
              {selected.deliveredAt && <p className="delivery-note"><CheckCircle2 size={15} />{selected.deliveryStatus === 'SENT' ? 'Sent through Gmail' : 'Delivered in simulation'} · {selected.deliveredAt}</p>}
            </section>
          </div>

          <footer className="review-actions">
            <button className="reject-action" type="button" onClick={onReject} disabled={selected.status === 'sent'}><X size={17} />Reject decision</button>
            <button className="approve-action" type="button" onClick={onApprove} disabled={selected.status === 'sent'}><Check size={17} />Human approve &amp; send</button>
            <p>The customer-service lead owns the final decision. Sending is simulated unless Gmail is explicitly configured.</p>
          </footer>
        </section>
        )}
      </div>
    </div>
  )
}

type VehicleWorkflowWorkspaceProps = {
  query: string
  vehicles: VehicleWorkflowSummary[]
  selectedJobId: string | null
  detail: VehicleWorkflowDetail | null
  role: string
  busy: boolean
  onQuery: (value: string) => void
  onSearch: () => void
  onSelect: (jobId: string) => void
  onRole: (role: string) => void
  onAction: (action: WorkflowAction) => void
  onReset: () => void
}

function VehicleWorkflowWorkspace(props: VehicleWorkflowWorkspaceProps) {
  const { query, vehicles, selectedJobId, detail, role, busy, onQuery, onSearch, onSelect, onRole, onAction, onReset } = props
  const qualityPending = detail?.currentStageCode === 'QUALITY_CHECK_PENDING'
  const readyForCollection = detail?.currentStageCode === 'READY_FOR_COLLECTION'

  return (
    <div className="manager-content workflow-content">
      <div className="workflow-intro">
        <div><h2>Vehicle service journey</h2><p>Search a Porsche vehicle, inspect its complete service history, and perform only actions authorized for the selected dealership role.</p></div>
        <span><ShieldCheck size={16} />Customer messages are read-only</span>
      </div>

      <div className="vehicle-workflow-layout">
        <section className="vehicle-search-panel">
          <div className="vehicle-search-box">
            <label><Search size={16} /><input value={query} onChange={(event) => onQuery(event.target.value)} onKeyDown={(event) => { if (event.key === 'Enter') onSearch() }} placeholder="Registration, job or customer…" /></label>
            <button type="button" onClick={onSearch}>Search</button>
          </div>
          <div className="vehicle-results">
            {vehicles.map((vehicle) => (
              <button type="button" key={vehicle.jobId} className={selectedJobId === vehicle.jobId ? 'selected' : ''} onClick={() => onSelect(vehicle.jobId)}>
                <span><CarFront size={17} /></span>
                <div><strong>{vehicle.registration}</strong><small>{vehicle.jobId} · {vehicle.customerId}</small><em>{vehicle.currentStage}</em></div>
              </button>
            ))}
            {vehicles.length === 0 && <div className="vehicle-empty">No vehicles match this search.</div>}
          </div>
        </section>

        {!detail ? (
          <section className="workflow-detail-empty"><CarFront size={34} /><h3>Select a vehicle</h3><p>Its current owner, allowed actions, and complete workflow history will appear here.</p></section>
        ) : (
          <section className="vehicle-workflow-detail">
            <header>
              <div><span><CarFront size={20} /></span><div><small className="vehicle-eyebrow">Vehicle identity</small><h2>{detail.registration}</h2><p>{detail.vehicle} · {detail.jobId}</p></div></div>
              <i>Version {detail.version}</i>
            </header>

            {(qualityPending || readyForCollection) && (
              <div className="vehicle-stage-track" aria-label="Vehicle service stages">
                <div className="complete"><b><Check size={14} /></b><span><small>Workshop</small><strong>Repair completed</strong></span></div>
                <div className={qualityPending ? 'active' : 'complete'}><b>{qualityPending ? '2' : <Check size={14} />}</b><span><small>Quality control</small><strong>{qualityPending ? 'Pending' : 'Completed'}</strong></span></div>
                <div className={readyForCollection ? 'active' : 'locked'}><b>3</b><span><small>Collection</small><strong>{readyForCollection ? 'Ready for adviser' : 'Locked'}</strong></span></div>
              </div>
            )}

            <div className="workflow-current-state">
              <div><small>Authoritative stage</small><strong>{detail.currentStage}</strong></div>
              <div><small>Assigned role</small><strong>{detail.currentOwnerRole}</strong></div>
              <div><small>Last updated</small><strong>{detail.updatedAt}</strong></div>
            </div>

            <section className="role-action-card">
              <div className="section-title"><div><UserCheck size={16} /><h3>Role-authorized action</h3></div><span>Simulated dealership role</span></div>
              <label><span>Acting role</span><select value={role} onChange={(event) => onRole(event.target.value)}>{workflowRoles.map((item) => <option value={item.code} key={item.code}>{item.label}</option>)}</select></label>
              {detail.allowedActions.map((action) => {
                const allowed = action.requiredRole === role
                return <div className={`available-transition ${allowed ? 'allowed' : 'blocked'}`} key={action.action}>
                  <div><strong>{action.label}</strong><span>Next: {action.nextStage} · Owner: {action.nextOwnerRole}</span>{!allowed && <small>Requires {action.requiredRoleLabel}</small>}</div>
                  <button type="button" disabled={!allowed || busy} onClick={() => onAction(action)}><Play size={14} />{busy ? 'Updating…' : 'Complete stage'}</button>
                </div>
              })}
              {detail.allowedActions.length === 0 && <div className="no-transition"><CheckCircle2 size={17} />No transition is available from this stage.</div>}
              {readyForCollection && <button className="workflow-reset" type="button" onClick={onReset} disabled={busy}><RefreshCcw size={14} />Reset synthetic scenario</button>}
            </section>

            <section className="workflow-history">
              <div className="section-title"><div><History size={16} /><h3>Past history</h3></div><span>{detail.history.length} events</span></div>
              <div>{detail.history.map((event, index) => <article key={`${event.createdAt}-${index}`}>
                <i className={event.simulated ? 'simulated' : ''}>{event.simulated ? 'Simulated' : 'Recorded'}</i>
                <div><strong>{event.action}</strong><p>{event.previousStage} → {event.newStage}</p><small>{event.completedByRole} · Next owner: {event.nextOwnerRole} · {event.createdAt}</small></div>
              </article>)}</div>
            </section>
          </section>
        )}
      </div>
    </div>
  )
}

type ConnectionsWorkspaceProps = {
  connectors: Connector[]
  configuring: Connector['id'] | null
  accountLabel: string
  onAccountLabel: (label: string) => void
  onConfigure: (connector: Connector) => void
  onCancel: () => void
  onSave: () => void
}

function ConnectionsWorkspace(props: ConnectionsWorkspaceProps) {
  const { connectors, configuring, accountLabel, onAccountLabel, onConfigure, onCancel, onSave } = props
  const icons = { whatsapp: MessageCircle, gmail: Mail, voice: PhoneCall }

  return (
    <div className="manager-content connections-content">
      <div className="connections-intro">
        <div><h2>Bring customer channels into one queue</h2><p>Configure where inquiries arrive from and where approved responses will eventually be delivered.</p></div>
        <span><ShieldCheck size={17} />Credentials are not collected in this prototype</span>
      </div>

      <div className="connector-grid">
        {connectors.map((connector) => {
          const Icon = icons[connector.id]
          const isConfiguring = configuring === connector.id
          return (
            <article className={`connector-card ${connector.id}`} key={connector.id}>
              <div className="connector-heading">
                <span><Icon size={23} /></span>
                <div><h3>{connector.name}</h3><p>{connector.description}</p></div>
                <i className={connector.status}>{connector.status === 'connected' ? 'Connected' : connector.status === 'planned' ? 'Planned' : 'Not connected'}</i>
              </div>

              {connector.accountLabel && <div className="connected-account"><CheckCircle2 size={16} /><span><small>Connected account</small><strong>{connector.accountLabel}</strong></span></div>}

              {isConfiguring ? (
                <div className="connector-form">
                  <label><span>{connector.id === 'gmail' ? 'Business email label' : 'Business number label'}</span><input autoFocus value={accountLabel} onChange={(event) => onAccountLabel(event.target.value)} placeholder={connector.id === 'gmail' ? 'service@example.com' : '+212 …'} /></label>
                  <p>This saves display information only. No external account or credential is accessed.</p>
                  <div><button type="button" onClick={onCancel}>Cancel</button><button type="button" onClick={onSave} disabled={!accountLabel.trim()}>Save simulation</button></div>
                </div>
              ) : (
                <button className="configure-button" type="button" onClick={() => onConfigure(connector)} disabled={connector.status === 'planned'}>
                  {connector.status === 'connected' ? <><RefreshCcw size={16} />Edit configuration</> : connector.status === 'planned' ? <><Clock3 size={16} />Coming later</> : <><Link2 size={16} />Configure</>}
                </button>
              )}
            </article>
          )
        })}
      </div>

      <section className="connection-boundary">
        <CircleAlert size={19} />
        <div><h3>Prototype boundary</h3><p>These controls demonstrate the future account setup experience. Gmail, WhatsApp and voice APIs are not connected, and approval actions remain local simulations.</p></div>
      </section>
    </div>
  )
}
