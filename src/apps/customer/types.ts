export type ChatMessage = {
  id: string
  role: 'assistant' | 'customer'
  text: string
  time: string
  state?: 'delivered' | 'pending'
}

export type CaseSummary = {
  reference: string
  vehicle: string
  status: 'Identifying vehicle' | 'Checking records' | 'Waiting for adviser' | 'Answered' | 'Response emailed' | 'Delivery failed'
  nextStep: string
  deliveryEmail?: string
}
