import { useEffect, useMemo, useState } from 'react'
import {
  ArrowLeft,
  Bot,
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
  RefreshCcw,
  Search,
  Send,
  Settings2,
  ShieldCheck,
  Sparkles,
  UserRound,
  X,
} from 'lucide-react'
import { initialConnectors, initialInquiries } from './data'
import type { Connector, Inquiry, InquiryClass } from './types'
import './manager.css'

type ManagerSection = 'inquiries' | 'connections'
type InquiryFilter = 'all' | 'needs_review' | 'ready' | 'sent'

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

  const selected = inquiries.find((inquiry) => inquiry.id === selectedId) ?? inquiries[0]
  const filteredInquiries = useMemo(() => {
    const query = search.trim().toLowerCase()
    return inquiries.filter((inquiry) => {
      const matchesFilter = filter === 'all' || inquiry.status === filter
      const matchesSearch = !query || [inquiry.id, inquiry.customerId, inquiry.message, inquiry.vehicle]
        .some((value) => value.toLowerCase().includes(query))
      return matchesFilter && matchesSearch
    })
  }, [filter, inquiries, search])

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
          <div><strong>Service desk</strong><small>Manager workspace</small></div>
        </div>

        <nav aria-label="Manager navigation">
          <button className={section === 'inquiries' ? 'active' : ''} onClick={() => setSection('inquiries')} type="button">
            <Inbox size={18} /><span>Inquiries</span><b>{counts.review + counts.ready}</b>
          </button>
          <button className={section === 'connections' ? 'active' : ''} onClick={() => setSection('connections')} type="button">
            <Link2 size={18} /><span>Connections</span>
          </button>
          <button type="button" disabled><History size={18} /><span>Activity</span><em>Later</em></button>
          <button type="button" disabled><Settings2 size={18} /><span>Settings</span><em>Later</em></button>
        </nav>

        <div className="manager-nav-bottom">
          <a href="/" target="_blank" rel="noreferrer"><ExternalLink size={16} />Open customer portal</a>
          <div className="manager-user"><span>YM</span><div><strong>Demo manager</strong><small>Synthetic workspace</small></div></div>
        </div>
      </aside>

      <section className="manager-main">
        <header className="manager-topbar">
          <div>
            <p>Customer operations</p>
            <h1>{section === 'inquiries' ? 'Inquiry review' : 'Channel connections'}</h1>
          </div>
          <div className="manager-top-actions">
            <span className="simulation-state"><span />Simulation mode</span>
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

      {toast && <div className="manager-toast" role="status"><CheckCircle2 size={18} />{toast}</div>}
    </main>
  )
}

type InquiryWorkspaceProps = {
  inquiries: Inquiry[]
  selected: Inquiry
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
  const ChannelIcon = channelIcons[selected.channel]

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
                <button key={inquiry.id} type="button" className={selected.id === inquiry.id ? 'selected' : ''} onClick={() => onSelect(inquiry.id)}>
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
              <div className="section-kicker"><UserRound size={15} />Customer request</div>
              <blockquote>{selected.message}</blockquote>
              <div className="customer-context">
                <span><strong>{selected.customerId}</strong> · {selected.vehicle}</span>
                <span><Languages size={14} />{selected.customerLanguage}</span>
              </div>
              {selected.customerEmail && <div className="customer-email"><Mail size={14} />Approved response will be delivered to <strong>{selected.customerEmail}</strong></div>}
            </section>

            <section className="review-section classification-section">
              <div className="section-title"><div><Sparkles size={16} /><h3>Agent classification</h3></div><span>{selected.confidence}% confidence</span></div>
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
              <div className="section-title"><div><MessageCircle size={16} /><h3>Proposed response</h3></div><span>Editable</span></div>
              <textarea value={selected.proposedResponse} onChange={(event) => onUpdate(selected.id, { proposedResponse: event.target.value })} rows={5} />
              {selected.deliveredAt && <p className="delivery-note"><CheckCircle2 size={15} />{selected.deliveryStatus === 'SENT' ? 'Sent through Gmail' : 'Delivered in simulation'} · {selected.deliveredAt}</p>}
            </section>
          </div>

          <footer className="review-actions">
            <button className="reject-action" type="button" onClick={onReject} disabled={selected.status === 'sent'}><X size={17} />Reject decision</button>
            <button className="approve-action" type="button" onClick={onApprove} disabled={selected.status === 'sent'}><Check size={17} />Approve &amp; email</button>
            <p>Delivery follows the backend Gmail configuration. The default mode is simulation.</p>
          </footer>
        </section>
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
