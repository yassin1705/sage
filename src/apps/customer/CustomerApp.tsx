import { FormEvent, useEffect, useRef, useState } from 'react'
import {
  ArrowUp,
  Bot,
  CarFront,
  Check,
  ChevronDown,
  Clock3,
  Headphones,
  Languages,
  LockKeyhole,
  Mic,
  PhoneCall,
  ShieldCheck,
  Sparkles,
} from 'lucide-react'
import type { CaseSummary, ChatMessage } from './types'
import './customer.css'

const initialMessages: ChatMessage[] = [
  {
    id: 'welcome',
    role: 'assistant',
    text: 'Hello — I can help you check a vehicle or an existing service booking. What would you like to know?',
    time: 'Now',
  },
]

const quickPrompts = [
  'Can I collect my car today?',
  'What is the status of my repair?',
  'I need to change my booking',
]

function makeTime() {
  return new Intl.DateTimeFormat('en', {
    hour: '2-digit',
    minute: '2-digit',
  }).format(new Date())
}

function getSimulatedAnswer(message: string) {
  const normalized = message.toLowerCase()

  if (normalized.includes('collect') || normalized.includes('ready')) {
    return 'I found the service record. The workshop has finished the work, but the final quality check is still pending. I cannot confirm collection yet, so I have prepared this for a service adviser to review.'
  }

  if (normalized.includes('booking') || normalized.includes('appointment')) {
    return 'I found the current booking. Because changes need to be confirmed by a service adviser, I can prepare a callback request for you.'
  }

  if (normalized.includes('status') || normalized.includes('repair')) {
    return 'I can check that for you. Please share the vehicle registration number and your customer reference so I can find the correct service record.'
  }

  return 'I can help with that. Please share the vehicle registration number and your customer reference so I can check the correct service record.'
}

export function CustomerApp() {
  const [messages, setMessages] = useState<ChatMessage[]>(initialMessages)
  const [draft, setDraft] = useState('')
  const [isThinking, setIsThinking] = useState(false)
  const [language, setLanguage] = useState('English')
  const [caseSummary, setCaseSummary] = useState<CaseSummary>({
    reference: 'Not created yet',
    vehicle: 'Not identified',
    status: 'Identifying vehicle',
    nextStep: 'Tell us what you need help with.',
  })
  const endRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, isThinking])

  function submitMessage(text: string) {
    const cleanText = text.trim()
    if (!cleanText || isThinking) return

    const customerMessage: ChatMessage = {
      id: crypto.randomUUID(),
      role: 'customer',
      text: cleanText,
      time: makeTime(),
      state: 'delivered',
    }

    setMessages((current) => [...current, customerMessage])
    setDraft('')
    setIsThinking(true)
    setCaseSummary({
      reference: 'CASE-104',
      vehicle: 'JOB-1 · Registration pending',
      status: 'Checking records',
      nextStep: 'The assistant is checking the available evidence.',
    })

    window.setTimeout(() => {
      const answer = getSimulatedAnswer(cleanText)
      const needsReview = cleanText.toLowerCase().includes('collect') || cleanText.toLowerCase().includes('ready')

      setMessages((current) => [
        ...current,
        {
          id: crypto.randomUUID(),
          role: 'assistant',
          text: answer,
          time: makeTime(),
        },
      ])
      setCaseSummary({
        reference: 'CASE-104',
        vehicle: 'JOB-1 · Registration pending',
        status: needsReview ? 'Waiting for adviser' : 'Answered',
        nextStep: needsReview
          ? 'A service adviser needs to confirm the response.'
          : 'Continue the conversation if you need more help.',
      })
      setIsThinking(false)
    }, 850)
  }

  function handleSubmit(event: FormEvent) {
    event.preventDefault()
    submitMessage(draft)
  }

  return (
    <main className="customer-app">
      <header className="customer-header">
        <a className="brand" href="#top" aria-label="Service companion home">
          <span className="brand-mark"><CarFront size={22} /></span>
          <span>
            <strong>Service companion</strong>
            <small>Customer assistance</small>
          </span>
        </a>

        <div className="header-actions">
          <label className="language-picker">
            <Languages size={17} aria-hidden="true" />
            <span className="sr-only">Conversation language</span>
            <select value={language} onChange={(event) => setLanguage(event.target.value)}>
              <option>English</option>
              <option>Français</option>
            </select>
            <ChevronDown size={15} aria-hidden="true" />
          </label>

          <button className="voice-button" type="button" disabled aria-describedby="voice-help">
            <PhoneCall size={17} />
            Voice chat
            <span>Coming soon</span>
          </button>
          <span id="voice-help" className="sr-only">Voice chat is not available in this prototype.</span>
        </div>
      </header>

      <section className="customer-layout" id="top">
        <section className="chat-shell" aria-label="Customer conversation">
          <div className="chat-heading">
            <div className="assistant-avatar"><Bot size={22} /></div>
            <div>
              <h1>Customer service assistant</h1>
              <p><span className="online-dot" /> Online · Replies use synthetic demonstration data</p>
            </div>
          </div>

          <div className="messages" aria-live="polite">
            <div className="date-divider"><span>Today</span></div>
            {messages.map((message) => (
              <article className={`message-row ${message.role}`} key={message.id}>
                {message.role === 'assistant' && <div className="message-avatar"><Sparkles size={15} /></div>}
                <div>
                  <div className="message-bubble">{message.text}</div>
                  <div className="message-meta">
                    {message.time}
                    {message.role === 'customer' && <Check size={13} aria-label="Delivered" />}
                  </div>
                </div>
              </article>
            ))}

            {isThinking && (
              <article className="message-row assistant">
                <div className="message-avatar"><Sparkles size={15} /></div>
                <div className="typing" aria-label="Assistant is checking records"><i /><i /><i /></div>
              </article>
            )}
            <div ref={endRef} />
          </div>

          {messages.length === 1 && (
            <div className="quick-prompts" aria-label="Suggested questions">
              {quickPrompts.map((prompt) => (
                <button key={prompt} type="button" onClick={() => submitMessage(prompt)}>{prompt}</button>
              ))}
            </div>
          )}

          <form className="composer" onSubmit={handleSubmit}>
            <div className="composer-box">
              <textarea
                aria-label="Message"
                placeholder="Ask about your vehicle or booking…"
                rows={1}
                value={draft}
                onChange={(event) => setDraft(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === 'Enter' && !event.shiftKey) {
                    event.preventDefault()
                    submitMessage(draft)
                  }
                }}
              />
              <button className="mic-button" type="button" disabled aria-label="Voice input coming soon"><Mic size={19} /></button>
              <button className="send-button" type="submit" disabled={!draft.trim() || isThinking} aria-label="Send message">
                <ArrowUp size={19} />
              </button>
            </div>
            <p><LockKeyhole size={13} /> Do not enter real personal information in this demonstration.</p>
          </form>
        </section>

        <aside className="customer-sidebar" aria-label="Case information">
          <section className="case-card">
            <div className="card-label">Your request</div>
            <h2>{caseSummary.reference}</h2>
            <div className={`case-status status-${caseSummary.status.toLowerCase().replaceAll(' ', '-')}`}>
              <Clock3 size={16} /> {caseSummary.status}
            </div>

            <dl>
              <div><dt>Vehicle case</dt><dd>{caseSummary.vehicle}</dd></div>
              <div><dt>Next step</dt><dd>{caseSummary.nextStep}</dd></div>
            </dl>
          </section>

          <section className="trust-card">
            <ShieldCheck size={20} />
            <div>
              <h2>Safe answers first</h2>
              <p>The assistant will ask a service adviser to review anything uncertain or requiring a promise.</p>
            </div>
          </section>

          <section className="help-card">
            <Headphones size={19} />
            <div>
              <h2>Need a person?</h2>
              <p>You can ask for a service adviser at any time during the conversation.</p>
            </div>
          </section>
        </aside>
      </section>
    </main>
  )
}
