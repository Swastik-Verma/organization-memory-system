import type { ChatResponse } from '@/types/chat'

// Fixture responses matching the real ChatResponse shape (backend/src/api/models.py).
// Used to develop the chat UI without spending Gemini quota — see CLAUDE.md §9.
// Real integration happens on Day 41.

const NORMAL_RESPONSE: ChatResponse = {
  question: '',
  effective_question: null,
  answer:
    'Sally Beck reports to John Lavorato [1], who led Enron America following the ' +
    'August 2001 reorganization. She works closely with Louise Kitchen on trading ' +
    'floor operations [2], and has been coordinating with Fletcher Sturm on risk ' +
    'management matters [3]. She also handles scheduling directly with the West ' +
    'trading desk [4].',
  citations: [
    {
      marker: '[1]',
      index: 1,
      claim_id: 'claim_8841',
      claim_type: 'reports_to',
      subject_name: 'Sally Beck',
      object_name: 'John Lavorato',
      evidence_quote: 'Sally reports directly to John Lavorato as of the August reorg.',
      evidence_id: 'evidence_2210',
      confidence: 0.85,
      message_date: '2001-08-15',
      message_subject: 'Re: Organizational changes',
    },
    {
      marker: '[2]',
      index: 2,
      claim_id: 'claim_8842',
      claim_type: 'works_with',
      subject_name: 'Sally Beck',
      object_name: 'Louise Kitchen',
      evidence_quote: 'Sally and Louise have been coordinating on the real-time trading floor schedule all week.',
      evidence_id: 'evidence_2211',
      confidence: 0.78,
      message_date: '2001-09-04',
      message_subject: 'Trading floor schedule — week of 9/3',
    },
    {
      marker: '[3]',
      index: 3,
      claim_id: 'claim_8843',
      claim_type: 'informs',
      subject_name: 'Sally Beck',
      object_name: 'Fletcher Sturm',
      evidence_quote: 'Please loop in Fletcher on the VAR numbers before Friday.',
      evidence_id: 'evidence_2212',
      confidence: 0.71,
      message_date: '2001-10-02',
      message_subject: 'VAR numbers before Friday',
    },
    {
      marker: '[4]',
      index: 4,
      claim_id: 'claim_8844',
      claim_type: 'works_with',
      subject_name: 'Sally Beck',
      object_name: 'West Trading Desk',
      evidence_quote: 'Sally will coordinate scheduling directly with the West desk going forward.',
      evidence_id: 'evidence_2213',
      confidence: 0.66,
      message_date: '2001-07-23',
      message_subject: 'West desk scheduling',
    },
  ],
  clarification: null,
  session_id: null,
}

const CLARIFICATION_RESPONSE: ChatResponse = {
  question: '',
  effective_question: null,
  answer: '',
  citations: [],
  clarification: {
    message: 'There are multiple people named John in the corpus. Which one did you mean?',
    options: [
      { id: 'person:arnold-john:john-arnold-at-enron-com', name: 'John Arnold', type: 'person' },
      { id: 'person:lavorato-john:john-lavorato-at-enron-com', name: 'John Lavorato', type: 'person' },
      { id: 'person:zufferli-john:john-zufferli-at-enron-com', name: 'John Zufferli', type: 'person' },
    ],
  },
  session_id: null,
}

const JOHN_ARNOLD_RESPONSE: ChatResponse = {
  question: '',
  effective_question: null,
  answer:
    "John Arnold flagged concerns about the deal's exposure to gas price volatility [1], " +
    'and requested tighter collateral terms from the counterparty before Enron proceeded [2].',
  citations: [
    {
      marker: '[1]',
      index: 1,
      claim_id: 'claim_7710',
      claim_type: 'informs',
      subject_name: 'John Arnold',
      object_name: 'Enron Gas Trading Desk',
      evidence_quote: 'John raised concerns about our exposure if gas prices move against us on this one.',
      evidence_id: 'evidence_4410',
      confidence: 0.74,
      message_date: '2001-10-09',
      message_subject: 'Re: deal exposure',
    },
    {
      marker: '[2]',
      index: 2,
      claim_id: 'claim_7711',
      claim_type: 'requests_from',
      subject_name: 'John Arnold',
      object_name: 'the counterparty',
      evidence_quote: 'Arnold wants tighter collateral terms before we move forward.',
      evidence_id: 'evidence_4411',
      confidence: 0.68,
      message_date: '2001-10-10',
      message_subject: 'Collateral terms — action needed',
    },
  ],
  clarification: null,
  session_id: null,
}

const JOHN_LAVORATO_RESPONSE: ChatResponse = {
  question: '',
  effective_question: null,
  answer:
    'John Lavorato said the deal looked favorable and pushed to accelerate the negotiation ' +
    'timeline [1]. He also asked finance to confirm the counterparty\'s credit rating before ' +
    'signing [2].',
  citations: [
    {
      marker: '[1]',
      index: 1,
      claim_id: 'claim_7720',
      claim_type: 'informs',
      subject_name: 'John Lavorato',
      object_name: 'Enron America',
      evidence_quote: 'Lavorato thinks this one looks good and wants to move faster on it.',
      evidence_id: 'evidence_4420',
      confidence: 0.81,
      message_date: '2001-10-11',
      message_subject: 'Re: timeline',
    },
    {
      marker: '[2]',
      index: 2,
      claim_id: 'claim_7721',
      claim_type: 'requests_from',
      subject_name: 'John Lavorato',
      object_name: 'Finance',
      evidence_quote: 'Please confirm the counterparty credit rating before we sign anything.',
      evidence_id: 'evidence_4421',
      confidence: 0.76,
      message_date: '2001-10-12',
      message_subject: 'Credit check before signing',
    },
  ],
  clarification: null,
  session_id: null,
}

const JOHN_ZUFFERLI_RESPONSE: ChatResponse = {
  question: '',
  effective_question: null,
  answer:
    'John Zufferli said the deal would need legal review before Enron could commit [1], and ' +
    "was in active discussion with the counterparty's trading desk on pricing [2].",
  citations: [
    {
      marker: '[1]',
      index: 1,
      claim_id: 'claim_7730',
      claim_type: 'informs',
      subject_name: 'John Zufferli',
      object_name: 'Enron Legal',
      evidence_quote: 'Zufferli flagged that legal needs to sign off before we go further.',
      evidence_id: 'evidence_4430',
      confidence: 0.69,
      message_date: '2001-10-13',
      message_subject: 'Re: legal review needed',
    },
    {
      marker: '[2]',
      index: 2,
      claim_id: 'claim_7731',
      claim_type: 'negotiating_with',
      subject_name: 'John Zufferli',
      object_name: "the counterparty's trading desk",
      evidence_quote: 'John has been going back and forth with their desk on pricing all week.',
      evidence_id: 'evidence_4431',
      confidence: 0.72,
      message_date: '2001-10-14',
      message_subject: 'Pricing discussion — update',
    },
  ],
  clarification: null,
  session_id: null,
}

const EMPTY_QUOTE_RESPONSE: ChatResponse = {
  question: '',
  effective_question: null,
  answer:
    'Enron discussed a potential transaction with Global Crossing in late 2001 [1]. ' +
    'The negotiation involved multiple stakeholders and was ultimately not finalized [2].',
  citations: [
    {
      marker: '[1]',
      index: 1,
      claim_id: 'claim_9931',
      claim_type: 'negotiating_with',
      subject_name: 'Enron',
      object_name: 'Global Crossing',
      evidence_quote: '',
      evidence_id: 'evidence_3390',
      confidence: 0.62,
      message_date: null,
      message_subject: null,
    },
    {
      marker: '[2]',
      index: 2,
      claim_id: 'claim_9932',
      claim_type: 'negotiating_with',
      subject_name: 'Enron',
      object_name: 'Global Crossing',
      evidence_quote: '',
      evidence_id: 'evidence_3391',
      confidence: 0.55,
      message_date: '2001-11-19',
      message_subject: 'FW: Global Crossing — status',
    },
  ],
  clarification: null,
  session_id: null,
}

const FOLLOW_UP_RESPONSE: ChatResponse = {
  question: '',
  effective_question: "What is Sally Beck's email address?",
  answer: "Sally Beck's email address is sally.beck@enron.com [1].",
  citations: [
    {
      marker: '[1]',
      index: 1,
      claim_id: 'claim_8850',
      claim_type: 'informs',
      subject_name: 'Sally Beck',
      object_name: 'sally.beck@enron.com',
      evidence_quote: 'You can reach me at sally.beck@enron.com for anything urgent.',
      evidence_id: 'evidence_2250',
      confidence: 0.91,
      message_date: '2001-06-11',
      message_subject: 'Re: contact info',
    },
  ],
  clarification: null,
  session_id: null,
}

function delay(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

function withSession(base: ChatResponse, question: string, sessionId: string | null): ChatResponse {
  return {
    ...base,
    question,
    session_id: sessionId ?? crypto.randomUUID(),
  }
}

/**
 * Simulates POST /api/chat. Waits ~1s like a real network call, then routes to a
 * fixture based on keywords in the question so every UI state (happy path,
 * clarification, empty evidence quotes, follow-up rewrite, error) is reachable
 * from the input box during development.
 */
export async function mockChatApi(question: string, sessionId: string | null): Promise<ChatResponse> {
  await delay(900 + Math.random() * 400)

  const q = question.toLowerCase().trim()

  if (q.includes('error')) {
    throw new Error('The mock API was asked to simulate a network failure.')
  }

  if (sessionId && (q.includes('her ') || q.includes('she ') || q.startsWith('what about'))) {
    return withSession(FOLLOW_UP_RESPONSE, question, sessionId)
  }

  // Exact full-name matches — how ClarificationCard resends a clicked option
  // (see ChatPage's onSelectClarificationOption) — must be checked before the
  // generic "john" clarification trigger below, or every option re-triggers
  // the same clarification card since each name still contains "john".
  if (q === 'john arnold') {
    return withSession(JOHN_ARNOLD_RESPONSE, question, sessionId)
  }
  if (q === 'john lavorato') {
    return withSession(JOHN_LAVORATO_RESPONSE, question, sessionId)
  }
  if (q === 'john zufferli') {
    return withSession(JOHN_ZUFFERLI_RESPONSE, question, sessionId)
  }

  if (q.includes('john')) {
    return withSession(CLARIFICATION_RESPONSE, question, sessionId)
  }
  if (q.includes('global crossing') || q.includes('deal')) {
    return withSession(EMPTY_QUOTE_RESPONSE, question, sessionId)
  }
  return withSession(NORMAL_RESPONSE, question, sessionId)
}

export const SUGGESTED_PROMPTS = [
  'Who does Sally Beck report to?',
  'What did John say about the deal?',
  'Tell me about the Global Crossing deal.',
  'Trigger a network error (demo)',
]
