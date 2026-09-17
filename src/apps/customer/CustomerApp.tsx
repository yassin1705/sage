import { FormEvent, useEffect, useRef, useState } from 'react'
import {
  ArrowUp, Bot, CarFront, Check, ChevronDown, Clock3, Download, Headphones,
  KeyRound, Languages, LockKeyhole, Mail, Mic, PhoneCall, ShieldCheck, Sparkles,
} from 'lucide-react'
import type { CaseSummary, ChatMessage } from './types'
import './customer.css'

const initialMessages: ChatMessage[] = [{
  id: 'welcome', role: 'assistant', time: 'Now',
  text: 'Hello — I can help you check a vehicle or an existing service booking. What would you like to know?',
}]

const quickPrompts = [
  'Can I collect my car today?',
  'What is the status of my repair?',
  'I need to change my booking',
]

type CustomerProfile = { customerId: string; registration: string }
type CreateRequestResponse = { conversation_id: string; review_id: string; state: string; message: string; model: string }
type CustomerCaseResponse = {
  id: string; state: string; delivery_email: string; job_id: string
  review_status: string | null; final_response: string | null
  delivery_status: string | null; delivered_at: string | null
}

type InstallPromptEvent = Event & {
  prompt: () => Promise<void>
  userChoice: Promise<{ outcome: 'accepted' | 'dismissed' }>
}

function makeTime() {
  return new Intl.DateTimeFormat('en', { hour: '2-digit', minute: '2-digit' }).format(new Date())
}

function makeMessageId() {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID()
  }
  return `message-${Date.now()}-${Math.random().toString(36).slice(2)}`
}

export function CustomerApp() {
  const [messages, setMessages] = useState<ChatMessage[]>(initialMessages)
  const [draft, setDraft] = useState('')
  const [isThinking, setIsThinking] = useState(false)
  const [language, setLanguage] = useState('English')
  const [conversationId, setConversationId] = useState<string | null>(null)
  const [profile, setProfile] = useState<CustomerProfile>({ customerId: 'CUS-A', registration: 'ABC-123' })
  const [caseSummary, setCaseSummary] = useState<CaseSummary>({
    reference: 'Not created yet', vehicle: 'Not identified', status: 'Identifying vehicle',
    nextStep: 'Verify the synthetic customer, then tell us what you need.',
  })
  const [installPrompt, setInstallPrompt] = useState<InstallPromptEvent | null>(null)
  const endRef = useRef<HTMLDivElement>(null)
  const canSubmit = Boolean(profile.customerId.trim() && profile.registration.trim())

  useEffect(() => { endRef.current?.scrollIntoView({ behavior: 'smooth' }) }, [messages, isThinking])

  useEffect(() => {
    const captureInstallPrompt = (event: Event) => {
      event.preventDefault()
      setInstallPrompt(event as InstallPromptEvent)
    }
    window.addEventListener('beforeinstallprompt', captureInstallPrompt)
    return () => window.removeEventListener('beforeinstallprompt', captureInstallPrompt)
  }, [])

  async function installApp() {
    if (!installPrompt) return
    await installPrompt.prompt()
    await installPrompt.userChoice
    setInstallPrompt(null)
  }

  useEffect(() => {
    if (!conversationId) return
    const poll = window.setInterval(async () => {
      try {
        const response = await fetch(`/api/customer/cases/${conversationId}`)
        if (!response.ok) return
        const customerCase = await response.json() as CustomerCaseResponse
        if (customerCase.review_status === 'APPROVED' || customerCase.review_status === 'CORRECTED') {
          if (customerCase.final_response) {
            setMessages((current) => current.some((item) => item.id === `approved-${conversationId}`) ? current : [...current, {
              id: `approved-${conversationId}`, role: 'assistant', text: customerCase.final_response!, time: makeTime(), state: 'delivered',
            }])
          }
          const failed = customerCase.delivery_status === 'FAILED'
          setCaseSummary({
            reference: conversationId,
            vehicle: customerCase.job_id,
            status: failed ? 'Delivery failed' : 'Response emailed',
            nextStep: failed
              ? 'The approved response could not be delivered. The service team can retry it.'
              : `The approved response was delivered in ${customerCase.delivery_status === 'SIMULATED' ? 'simulation mode' : 'Gmail'}.`,
            deliveryEmail: customerCase.delivery_email,
          })
          if (!failed) window.clearInterval(poll)
        }
      } catch {
        // Temporary polling failures should not interrupt the customer experience.
      }
    }, 2500)
    return () => window.clearInterval(poll)
  }, [conversationId])

  async function submitMessage(text: string) {
    const cleanText = text.trim()
    if (!cleanText || isThinking || !canSubmit) return
    setMessages((current) => [...current, { id: makeMessageId(), role: 'customer', text: cleanText, time: makeTime(), state: 'delivered' }])
    setDraft('')
    setIsThinking(true)
    setCaseSummary({
      reference: conversationId ?? 'Creating case…', vehicle: `${profile.registration} · Checking records`,
      status: 'Checking records', nextStep: 'SAGE is classifying the request and checking the available evidence.',
    })

    try {
      const response = await fetch('/api/customer/requests', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ customer_id: profile.customerId, registration: profile.registration, language, message: cleanText }),
      })
      const result = await response.json() as CreateRequestResponse | { detail: string }
      if (!response.ok) throw new Error('detail' in result ? result.detail : 'The request could not be created')
      const created = result as CreateRequestResponse
      setConversationId(created.conversation_id)
      setMessages((current) => [...current,
        { id: makeMessageId(), role: 'assistant', text: created.message, time: makeTime(), state: 'pending' },
      ])
      setCaseSummary({
        reference: created.conversation_id, vehicle: `${profile.registration} · Service case`, status: 'Waiting for adviser',
        nextStep: 'The agent has shared a provisional update. A manager will review the evidence and approve the final email.',
      })
    } catch (error) {
      setMessages((current) => [...current, {
        id: makeMessageId(), role: 'assistant',
        text: error instanceof Error ? error.message : 'The service is temporarily unavailable.', time: makeTime(),
      }])
      setCaseSummary({
        reference: 'Not created', vehicle: profile.registration, status: 'Identifying vehicle',
        nextStep: 'Check the customer reference, registration, and backend connection.',
      })
    } finally {
      setIsThinking(false)
    }
  }

  function handleSubmit(event: FormEvent) { event.preventDefault(); void submitMessage(draft) }

  return (
    <main className="customer-app">
      <header className="customer-header">
        <a className="brand" href="#top" aria-label="SAGE home"><span className="brand-mark"><CarFront size={22} /></span><span><strong>SAGE</strong><small>Porsche service prototype</small></span></a>
        <div className="header-actions">
          {installPrompt && <button className="install-button" type="button" onClick={() => void installApp()}><Download size={16} />Install</button>}
          <label className="language-picker"><Languages size={17} aria-hidden="true" /><span className="sr-only">Conversation language</span><select value={language} onChange={(event) => setLanguage(event.target.value)}><option>English</option><option>Français</option></select><ChevronDown size={15} aria-hidden="true" /></label>
          <button className="voice-button" type="button" disabled aria-describedby="voice-help"><PhoneCall size={17} />Voice chat<span>Coming soon</span></button>
          <span id="voice-help" className="sr-only">Voice chat is not available in this prototype.</span>
        </div>
      </header>

      <section className="customer-layout" id="top">
        <section className="chat-shell" aria-label="Customer conversation">
          <div className="chat-heading"><div className="assistant-avatar"><Bot size={22} /></div><div><span className="experience-label">Porsche dealership service · Exercise prototype</span><h1>Your vehicle service assistant</h1><p><span className="online-dot" /> Online · Synthetic data · Final replies require adviser approval</p></div></div>

          <section className="customer-identity" aria-label="Synthetic customer verification">
            <div className="identity-copy"><KeyRound size={17} /><div><strong>Find your vehicle</strong><span>Enter the synthetic customer reference and registration supplied for this demonstration.</span></div></div>
            <div className="identity-fields">
              <label><span>Customer reference</span><input value={profile.customerId} onChange={(event) => setProfile({ ...profile, customerId: event.target.value })} /></label>
              <label><span>Registration</span><input value={profile.registration} onChange={(event) => setProfile({ ...profile, registration: event.target.value })} /></label>
            </div>
          </section>

          <div className="messages" aria-live="polite">
            <div className="date-divider"><span>Today</span></div>
            {messages.map((message) => <article className={`message-row ${message.role}`} key={message.id}>{message.role === 'assistant' && <div className="message-avatar"><Sparkles size={15} /></div>}<div><div className="message-bubble">{message.text}</div><div className="message-meta">{message.time}{message.role === 'customer' && <Check size={13} aria-label="Delivered" />}</div></div></article>)}
            {isThinking && <article className="message-row assistant"><div className="message-avatar"><Sparkles size={15} /></div><div className="typing" aria-label="Assistant is checking records"><i /><i /><i /></div></article>}
            <div ref={endRef} />
          </div>

          {messages.length === 1 && <div className="quick-prompts" aria-label="Suggested questions">{quickPrompts.map((prompt) => <button key={prompt} type="button" onClick={() => void submitMessage(prompt)} disabled={!canSubmit}>{prompt}</button>)}</div>}

          <form className="composer" onSubmit={handleSubmit}>
            <div className="composer-box">
              <textarea aria-label="Message" placeholder={canSubmit ? 'Ask about your vehicle or booking…' : 'Add an email and consent before sending…'} rows={1} value={draft} onChange={(event) => setDraft(event.target.value)} onKeyDown={(event) => { if (event.key === 'Enter' && !event.shiftKey) { event.preventDefault(); void submitMessage(draft) } }} />
              <button className="mic-button" type="button" disabled aria-label="Voice input coming soon"><Mic size={19} /></button>
              <button className="send-button" type="submit" disabled={!draft.trim() || isThinking || !canSubmit} aria-label="Send message"><ArrowUp size={19} /></button>
            </div>
            <p><LockKeyhole size={13} /> Use a test email address and synthetic identity data in this demonstration.</p>
          </form>
        </section>

        <aside className="customer-sidebar" aria-label="Case information">
          <section className="case-card"><div className="card-label">Vehicle service case</div><h2>{caseSummary.reference}</h2><div className={`case-status status-${caseSummary.status.toLowerCase().replaceAll(' ', '-')}`}><Clock3 size={16} /> {caseSummary.status}</div><dl><div><dt>Vehicle / registration</dt><dd>{caseSummary.vehicle}</dd></div>{caseSummary.deliveryEmail && <div><dt>Approved reply destination</dt><dd className="email-destination"><Mail size={13} />{caseSummary.deliveryEmail}</dd></div>}<div><dt>Next action</dt><dd>{caseSummary.nextStep}</dd></div></dl></section>
          <section className="trust-card"><ShieldCheck size={20} /><div><h2>Adviser-approved replies</h2><p>The assistant checks service evidence, but a dealership adviser owns the final response.</p></div></section>
          <section className="help-card"><Headphones size={19} /><div><h2>Human support remains visible</h2><p>Your adviser can edit or reject every proposed response before it is sent.</p></div></section>
          <p className="prototype-disclaimer">Hackathon prototype using synthetic data. Not commissioned, endorsed, or operated by Porsche.</p>
        </aside>
      </section>
    </main>
  )
}
