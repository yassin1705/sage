export type InquiryClass =
  | 'Collection status'
  | 'Repair status'
  | 'Booking change'
  | 'Repeated enquiry'
  | 'General request'

export type InquiryStatus = 'needs_review' | 'ready' | 'sent' | 'rejected'

export type EvidenceItem = {
  source: string
  value: string
  observedAt: string
  tone?: 'neutral' | 'warning' | 'positive'
}

export type Inquiry = {
  id: string
  customerId: string
  customerLanguage: string
  customerEmail?: string
  channel: 'WhatsApp' | 'Gmail' | 'Phone note' | 'Web chat'
  receivedAt: string
  message: string
  jobId: string
  vehicle: string
  classification: InquiryClass
  confidence: number
  status: InquiryStatus
  justification: string
  rules: string[]
  evidence: EvidenceItem[]
  proposedResponse: string
  nextAction: string
  nextActionOwner: string
  uncertainty: string
  workflowStage: string
  workflowOwner: string
  workflowVersion: number
  canCompleteQualityCheck: boolean
  canResetWorkflowDemo: boolean
  deliveredAt?: string
  deliveryStatus?: string
}

export type Connector = {
  id: 'whatsapp' | 'gmail' | 'voice'
  name: string
  description: string
  status: 'connected' | 'not_connected' | 'planned'
  accountLabel?: string
}
