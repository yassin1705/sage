import { FormEvent, useEffect, useRef, useState } from 'react'
import {
  ArrowUp, Bot, CarFront, Check, ChevronDown, Clock3, Headphones,
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

type CustomerProfile = { customerId: string; registration: string; email: string; consent: boolean }
type CreateRequestResponse = { conversation_id: string; review_id: string; state: string; message: string; model: string }
type CustomerCaseResponse = {
  id: string; state: string; delivery_email: string; job_id: string
  review_status: string | null; final_response: string | null
  delivery_status: string | null; delivered_at: string | null
}

function makeTime() {
  return new Intl.DateTimeFormat('en', { hour: '2-digit', minute: '2-digit' }).format(new Date())
}

export function CustomerApp() {
  const [messages, setMessages] = useState<ChatMessage[]>(initialMessages)
  const [draft, setDraft] = useState('')
  const [isThinking, setIsThinking] = useState(false)
  const [language, setLanguage] = useState('English')
  const [conversationId, setConversationId] = useState<string | null>(null)
  const [profile, setProfile] = useState<CustomerProfile>({ customerId: 'CUS-A', registration: 'ABC-123', email: '', consent: false })
  const [caseSummary, setCaseSummary] = useState<CaseSummary>({
    reference: 'Not created yet', vehicle: 'Not identified', status: 'Identifying vehicle',
    nextStep: 'Verify the synthetic customer, then tell us what you need.',
  })
  const endRef = useRef<HTMLDivElement>(null)
  const canSubmit = Boolean(profile.customerId.trim() && profile.registration.trim() && profile.email.trim() && profile.consent)

  useEffect(() => { endRef.current?.scrollIntoView({ behavior: 'smooth' }) }, [messages, isThinking])

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
    setMessages((current) => [...current, { id: crypto.randomUUID(), role: 'customer', text: cleanText, time: makeTime(), state: 'delivered' }])
    setDraft('')
    setIsThinking(true)
    setCaseSummary({
      reference: conversationId ?? 'Creating case…', vehicle: `${profile.registration} · Checking records`,
      status: 'Checking records', nextStep: 'SAGE is classifying the request and checking the available evidence.', deliveryEmail: profile.email,
    })

    try {
      const response = await fetch('/api/customer/requests', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ customer_id: profile.customerId, registration: profile.registration, email: profile.email, consent: profile.consent, message: cleanText }),
      })
      const result = await response.json() as CreateRequestResponse | { detail: string }
      if (!response.ok) throw new Error('detail' in result ? result.detail : 'The request could not be created')
      const created = result as CreateRequestResponse
      setConversationId(created.conversation_id)
      setMessages((current) => [...current, { id: crypto.randomUUID(), role: 'assistant', text: created.message, time: makeTime() }])
      setCaseSummary({
        reference: created.conversation_id, vehicle: `${profile.registration} · Service case`, status: 'Waiting for adviser',
        nextStep: 'A manager will review the evidence and proposed response.', deliveryEmail: profile.email,
      })
    } catch (error) {
      setMessages((current) => [...current, {
        id: crypto.randomUUID(), role: 'assistant',
        text: error instanceof Error ? error.message : 'The service is temporarily unavailable.', time: makeTime(),
      }])
      setCaseSummary({
        reference: 'Not created', vehicle: profile.registration, status: 'Identifying vehicle',
        nextStep: 'Check the customer reference, registration, and backend connection.', deliveryEmail: profile.email,
      })
    } finally {
      setIsThinking(false)
    }
  }

  function handleSubmit(event: FormEvent) { event.preventDefault(); void submitMessage(draft) }

  return (
    <main className="customer-app">
      <header className="customer-header">
        <a className="brand" href="#top" aria-label="SAGE home"><span className="brand-mark"><CarFront size={22} /></span><span><strong>SAGE</strong><small>Customer assistance</small></span></a>
        <div className="header-actions">
          <label className="language-picker"><Languages size={17} aria-hidden="true" /><span className="sr-only">Conversation language</span><select value={language} onChange={(event) => setLanguage(event.target.value)}><option>English</option><option>Français</option></select><ChevronDown size={15} aria-hidden="true" /></label>
          <button className="voice-button" type="button" disabled aria-describedby="voice-help"><PhoneCall size={17} />Voice chat<span>Coming soon</span></button>
          <span id="voice-help" className="sr-only">Voice chat is not available in this prototype.</span>
        </div>
      </header>

      <section className="customer-layout" id="top">
        <section className="chat-shell" aria-label="Customer conversation">
          <div className="chat-heading"><div className="assistant-avatar"><Bot size={22} /></div><div><h1>Customer service assistant</h1><p><span className="online-dot" /> Online · Replies use synthetic demonstration data</p></div></div>

          <section className="customer-identity" aria-label="Synthetic customer verification">
            <div className="identity-copy"><KeyRound size={17} /><div><strong>Demo verification</strong><span>Use synthetic identity details and choose where the approved answer should be delivered.</span></div></div>
            <div className="identity-fields">
              <label><span>Customer reference</span><input value={profile.customerId} onChange={(event) => setProfile({ ...profile, customerId: event.target.value })} /></label>
              <label><span>Registration</span><input value={profile.registration} onChange={(event) => setProfile({ ...profile, registration: event.target.value })} /></label>
              <label className="email-field"><span>Delivery email</span><input type="email" value={profile.email} onChange={(event) => setProfile({ ...profile, email: event.target.value })} placeholder="your-test-address@gmail.com" /></label>
            </div>
            <label className="consent-field"><input type="checkbox" checked={profile.consent} onChange={(event) => setProfile({ ...profile, consent: event.target.checked })} /><span>Send the manager-approved response to this email address.</span></label>
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
          <section className="case-card"><div className="card-label">Your request</div><h2>{caseSummary.reference}</h2><div className={`case-status status-${caseSummary.status.toLowerCase().replaceAll(' ', '-')}`}><Clock3 size={16} /> {caseSummary.status}</div><dl><div><dt>Vehicle case</dt><dd>{caseSummary.vehicle}</dd></div>{caseSummary.deliveryEmail && <div><dt>Email delivery</dt><dd className="email-destination"><Mail size={13} />{caseSummary.deliveryEmail}</dd></div>}<div><dt>Next step</dt><dd>{caseSummary.nextStep}</dd></div></dl></section>
          <section className="trust-card"><ShieldCheck size={20} /><div><h2>Safe answers first</h2><p>The assistant asks a manager to review every response before email delivery.</p></div></section>
          <section className="help-card"><Headphones size={19} /><div><h2>Need a person?</h2><p>The manager can edit or reject the agent’s proposed response.</p></div></section>
        </aside>
      </section>
    </main>
  )
}
