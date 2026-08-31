import type { EvidenceDetailResponse } from '@/types/evidence'

// Mock data layer for the Evidence Detail page (Day 40), matching the real
// EvidenceDetailResponse shape from backend/src/api/models.py — see src/types/evidence.ts
// for the field-by-field mapping and the mock-only fields flagged there. Real integration
// happens on Day 41 (CLAUDE.md §9) — nothing here calls the live API.
//
// ---------------------------------------------------------------------------------------
// WHY THIS FILE HAS TWO TIERS ("showcase" + "filler")
//
// The Day 40 brief asks for 4-5 hand-authored evidence objects covering specific UI states
// (happy path, empty quote, long body, superseded+valid_to, multi-recipient), but also
// requires that EVERY evidence_id referenced anywhere in src/mocks/chatMocks.ts (citation
// `evidence_id` fields) and src/mocks/entityMocks.ts (claim `evidence_ids` arrays) resolves
// to a real mock, not a 404 — otherwise most citation badges and "View evidence" links in
// the already-built Day 37/39 UI would dead-end.
//
// SHOWCASE below is the 5 fully hand-written fixtures for the required states. FILLER_SPECS
// covers every other evidence_id referenced by chatMocks.ts/entityMocks.ts, built from data
// transcribed out of those two files (claim_type/subject/object/quote where chatMocks has
// it; claim_type/subject/object/status/dates where entityMocks has it) and expanded into a
// full EvidenceDetailResponse by buildFillerDetail() using small claim-type-keyed templates
// for the parts neither source file records (entityMocks' ClaimResult has no quote text at
// all — only evidence_id strings — so a one-line templated quote is synthesized for those).
//
// Neither chatMocks.ts nor entityMocks.ts exports its raw fixture arrays (only async mock*
// functions), and this session must not add exports to Day 37/39 files it isn't scoped to
// touch — so the transcribed values below are duplicated literals, not imports. Same
// accepted risk as entityMocks.ts's own header comment about its 14 ids copied from
// graphMocks.ts: if chatMocks.ts/entityMocks.ts change their citation/claim data later,
// these must be updated by hand to match.
//
// A REAL CROSS-FILE INCONSISTENCY WAS FOUND WHILE TRANSCRIBING THIS DATA, not introduced
// today: evidence_2211 is the second evidence_ids entry on entityMocks.ts's claim_001
// (Sally Beck reports_to John Lavorato), but chatMocks.ts's NORMAL_RESPONSE citation [2]
// uses the SAME evidence_id for a completely different claim (Sally Beck works_with Louise
// Kitchen, claim_8842) — with an actual quote text, which entityMocks' claim never carries.
// A real evidence node in the real schema belongs to exactly one claim, so this mock can't
// honor both. chatMocks.ts's version is treated as authoritative here (it's the only one of
// the two with real quote text), and entityMocks.ts's claim_001 evidence_2211 reference is
// therefore shown as the "Louise Kitchen" claim if reached — not a bug in today's build,
// but a pre-existing data drift between two hand-authored mock files, same class as the Day
// 39 log's "Relationships tab mislabel" cross-file bug. In practice this isn't user-visible
// today: ClaimCard.tsx only links to `evidence_ids[0]`, never `[1]`, so evidence_2211 is
// only reachable via chatMocks' own citation badge, which agrees with itself. Flagged here
// rather than silently resolved, per CLAUDE.md §5's "ask before deciding" — worth a look
// before Day 41 if evidence_ids beyond [0] ever become clickable.
// ---------------------------------------------------------------------------------------

// ---- Canonical entity ids, duplicated from entityMocks.ts's own registry (same accepted
// risk noted above) — used so claim subject/object links on this page land on the exact
// same entity identity as the rest of the app wherever the name is a real registered one. ----
const ENTITY_IDS: Record<string, string> = {
  'Sally Beck': 'person:beck-sally:sally-beck-at-enron-com',
  'John Lavorato': 'person:lavorato-john:john-lavorato-at-enron-com',
  'Louise Kitchen': 'person:kitchen-louise:louise-kitchen-at-enron-com',
  'Fletcher Sturm': 'person:sturm-fletcher:fletcher-sturm-at-enron-com',
  'Kenneth Lay': 'person:lay-kenneth:kenneth-lay-at-enron-com',
  'John Zufferli': 'person:zufferli-john:john-zufferli-at-enron-com',
  'West Trading Desk': 'org:west-trading-desk:west-trading-desk',
  'Enron America': 'org:enron-america:enron-america',
  'Enron Legal': 'org:enron-legal:enron-legal',
  Finance: 'org:finance:finance',
  'Global Crossing Ltd': 'org:global-crossing-ltd:global-crossing-ltd',
  'Global Crossing Transaction': 'deal:global-crossing-transaction:global-crossing-transaction',
  'Approve Global Crossing Deal': 'decision:approve-global-crossing-deal:approve-global-crossing-deal',
  'August 2001 Reorganization': 'decision:august-2001-reorganization:august-2001-reorganization',
  'Jeffrey McMahon': 'person:mcmahon-jeffrey:jeffrey-mcmahon-at-enron-com',
  'Greg Whalley': 'person:whalley-greg:greg-whalley-at-enron-com',
  'Arthur Andersen': 'org:arthur-andersen:arthur-andersen',
  'Enron Broadband Services': 'org:enron-broadband-services:enron-broadband-services',
  'EOTT Energy Restructuring': 'deal:eott-energy-restructuring:eott-energy-restructuring',
  'Freeze 401(k) Trading Window': 'decision:freeze-401k-trading-window:freeze-401k-trading-window',
}

function slugify(name: string): string {
  return name
    .toLowerCase()
    .replace(/[^a-z0-9\s-]/g, '')
    .trim()
    .replace(/\s+/g, '-')
}

/** Looks up a real registered entity id by name; unregistered names (e.g. "Enron", "the
 * counterparty" — free-text mentions that never got their own entity profile in these
 * mocks) fall back to a synthetic id. Clicking through on one of those honestly lands on
 * the entity page's existing "not found" state rather than a broken link — a realistic
 * outcome for an imperfectly-resolved mention, not a bug. */
function idFor(name: string): string {
  return ENTITY_IDS[name] ?? `unresolved:${slugify(name)}`
}

function emailFor(name: string): string {
  if (name.includes('@')) return name
  const slug = name
    .toLowerCase()
    .replace(/[^a-z0-9\s]/g, '')
    .trim()
    .replace(/\s+/g, '.')
  return `${slug}@enron.com`
}

function firstName(name: string): string {
  return name.split(' ')[0] ?? name
}

function buildBody(openingTo: string, closingFrom: string, mainLine: string): string {
  return `Hi ${firstName(openingTo)},\n\n${mainLine}\n\nLet me know if you have any questions or if anything here changes.\n\nBest,\n${firstName(closingFrom)}`
}

// ---------------------------------------------------------------------------------------
// SHOWCASE — the 5 hand-authored fixtures required by the Day 40 brief.
// ---------------------------------------------------------------------------------------

const SHOWCASE: Record<string, EvidenceDetailResponse> = {
  // 1. Happy path — every field populated, quote clearly embedded in the body. Matches the
  // exact example in the Day 40 brief.
  evidence_2210: {
    evidence_id: 'evidence_2210',
    quote: 'Sally reports directly to John Lavorato as of the August reorg.',
    confidence: 0.85,
    claim_id: 'claim_8841',
    claim_type: 'reports_to',
    subject_name: 'Sally Beck',
    object_name: 'John Lavorato',
    email_subject: 'Re: Organizational changes',
    email_from: 'sally.beck@enron.com',
    email_date: '2001-08-15',
    email_body:
      "Hi John,\n\nAs discussed, I'll be reporting directly to you following the reorganization. " +
      "I've already started looping the team in on the updated org chart and will make sure " +
      'everyone knows the new lines of communication going forward.\n\n' +
      'Sally reports directly to John Lavorato as of the August reorg.\n\n' +
      "Please let me know if there are any changes to the team structure, or if you'd like me " +
      'to set up a call to go over transition details this week.\n\nBest,\nSally',
    subject_id: idFor('Sally Beck'),
    object_id: idFor('John Lavorato'),
    status: 'active',
    valid_from: '2001-08-01',
    valid_to: null,
    email_to: ['john.lavorato@enron.com', 'louise.kitchen@enron.com'],
  },

  // 2. Empty evidence_quote — real citation data (chatMocks.ts EMPTY_QUOTE_RESPONSE) with a
  // genuinely blank quote, exercising the graceful fallback.
  evidence_3390: {
    evidence_id: 'evidence_3390',
    quote: '',
    confidence: 0.62,
    claim_id: 'claim_9931',
    claim_type: 'negotiating_with',
    subject_name: 'Enron',
    object_name: 'Global Crossing',
    email_subject: 'Global Crossing — initial discussion',
    email_from: 'trading-desk@enron.com',
    email_date: '2001-06-04',
    email_body:
      'Hi team,\n\nWanted to flag that conversations with Global Crossing have been ongoing for ' +
      "a few weeks now. Nothing formal has been signed, but there's been back-and-forth on deal " +
      'structure and timing that seems worth keeping an eye on.\n\nWill send more as it develops.' +
      '\n\nBest,\nTrading Desk',
    subject_id: idFor('Enron'),
    object_id: idFor('Global Crossing'),
    status: 'active',
    valid_from: '2001-06-01',
    valid_to: null,
    email_to: ['legal@enron.com'],
  },

  // 3. Long email body (15+ lines) to test scrolling/readability.
  evidence_1980: {
    evidence_id: 'evidence_1980',
    quote:
      "We've moved past the initial term sheet and are now negotiating the final valuation " +
      "range with Global Crossing's team.",
    confidence: 0.84,
    claim_id: 'claim_014',
    claim_type: 'negotiating_with',
    subject_name: 'John Lavorato',
    object_name: 'Global Crossing Transaction',
    email_subject: 'Global Crossing — negotiation update',
    email_from: 'john.lavorato@enron.com',
    email_date: '2001-07-01',
    email_body: [
      'Hi all,',
      '',
      "Quick update on where things stand with Global Crossing. We've moved past the initial " +
        "term sheet and are now negotiating the final valuation range with Global Crossing's " +
        'team.',
      '',
      "Here's where the open items sit:",
      '',
      '1. Valuation — their side came in above what we modeled internally. Finance is re-running',
      '   the numbers with updated assumptions on network utilization.',
      '2. Structure — still deciding between an asset purchase and a longer-term capacity',
      '   swap arrangement. Legal has a preliminary view but wants more time.',
      '3. Timeline — they want to move quickly, ideally closing before end of Q3. That is',
      '   aggressive given the diligence still outstanding on their network assets.',
      '4. Counterparty risk — Finance flagged some concerns about their balance sheet that',
      '   we should factor into any deal structure, particularly around payment terms.',
      '',
      "I'd like to get the core team together this week to align on a target valuation range",
      'before our next call with their negotiating team. Please send me your availability.',
      '',
      "I'll keep circulating updates as this develops — this one is moving fast and I want",
      'everyone working off the same numbers.',
      '',
      'Best,',
      'John',
    ].join('\n'),
    subject_id: idFor('John Lavorato'),
    object_id: idFor('Global Crossing Transaction'),
    status: 'active',
    valid_from: '2001-07-01',
    valid_to: null,
    email_to: ['legal@enron.com', 'finance@enron.com'],
  },

  // 4. status: 'superseded' with a non-null valid_to.
  evidence_1750: {
    evidence_id: 'evidence_1750',
    quote:
      "Global Crossing's initial proposal set the deal value well below what Enron was targeting.",
    confidence: 0.72,
    claim_id: 'claim_017',
    claim_type: 'negotiating_with',
    subject_name: 'Global Crossing Ltd',
    object_name: 'Global Crossing Transaction',
    email_subject: 'Re: Proposed terms — early draft',
    email_from: 'contact@globalcrossing.com',
    email_date: '2001-05-03',
    email_body:
      "Hi John,\n\nThanks for the call yesterday. Attached is our initial thinking on structure " +
      "and pricing. Global Crossing's initial proposal set the deal value well below what Enron " +
      'was targeting. We expect this to be a starting point for discussion rather than a final ' +
      'number.\n\nLooking forward to your feedback.\n\nBest,\nGlobal Crossing Deal Team',
    subject_id: idFor('Global Crossing Ltd'),
    object_id: idFor('Global Crossing Transaction'),
    status: 'superseded',
    valid_from: '2001-05-01',
    valid_to: '2001-07-01',
    email_to: ['john.lavorato@enron.com'],
  },

  // 5. Multiple recipients in email_to.
  evidence_2260: {
    evidence_id: 'evidence_2260',
    quote:
      'Please be advised that the reorganization announced this week directly affects your ' +
      'reporting structure and team assignments effective immediately.',
    confidence: 0.71,
    claim_id: 'claim_020',
    claim_type: 'informs',
    subject_name: 'August 2001 Reorganization',
    object_name: 'Kenneth Lay',
    email_subject: 'August 2001 Reorganization — leadership notice',
    email_from: 'announcements@enron.com',
    email_date: '2001-08-10',
    email_body:
      'Leadership team,\n\nPlease be advised that the reorganization announced this week ' +
      'directly affects your reporting structure and team assignments effective immediately. ' +
      "Updated org charts will follow from HR by end of week.\n\nReach out to me directly if " +
      "you have questions about how this affects your group.\n\nBest,\nCorporate Communications",
    subject_id: idFor('August 2001 Reorganization'),
    object_id: idFor('Kenneth Lay'),
    status: 'active',
    valid_from: '2001-08-10',
    valid_to: null,
    email_to: [
      'kenneth.lay@enron.com',
      'john.lavorato@enron.com',
      'louise.kitchen@enron.com',
      'greg.whalley@enron.com',
    ],
  },
}

// ---------------------------------------------------------------------------------------
// FILLER — every other evidence_id referenced by chatMocks.ts citations or entityMocks.ts
// claims, transcribed from those files (see the header comment for the sourcing rule and
// the evidence_2211 conflict resolution).
// ---------------------------------------------------------------------------------------

interface FillerSpec {
  evidence_id: string
  claim_id: string
  claim_type: string
  subject_name: string
  object_name: string
  quote: string // '' -> a claim-type-templated one-line quote is synthesized
  confidence: number
  status: string
  valid_from: string
  valid_to: string | null
  email_date: string
  email_subject: string // '' -> a claim-type-templated subject is synthesized
  email_from?: string
  email_to?: string[]
}

// ---- Sourced from chatMocks.ts citations (real quote text, dates, subjects) ----
const CHAT_SOURCED: FillerSpec[] = [
  {
    evidence_id: 'evidence_2211',
    claim_id: 'claim_8842',
    claim_type: 'works_with',
    subject_name: 'Sally Beck',
    object_name: 'Louise Kitchen',
    quote: 'Sally and Louise have been coordinating on the real-time trading floor schedule all week.',
    confidence: 0.78,
    status: 'active',
    valid_from: '2001-09-04',
    valid_to: null,
    email_date: '2001-09-04',
    email_subject: 'Trading floor schedule — week of 9/3',
  },
  {
    evidence_id: 'evidence_2212',
    claim_id: 'claim_8843',
    claim_type: 'informs',
    subject_name: 'Sally Beck',
    object_name: 'Fletcher Sturm',
    quote: 'Please loop in Fletcher on the VAR numbers before Friday.',
    confidence: 0.71,
    status: 'active',
    valid_from: '2001-10-02',
    valid_to: null,
    email_date: '2001-10-02',
    email_subject: 'VAR numbers before Friday',
  },
  {
    evidence_id: 'evidence_2213',
    claim_id: 'claim_8844',
    claim_type: 'works_with',
    subject_name: 'Sally Beck',
    object_name: 'West Trading Desk',
    quote: 'Sally will coordinate scheduling directly with the West desk going forward.',
    confidence: 0.66,
    status: 'active',
    valid_from: '2001-07-23',
    valid_to: null,
    email_date: '2001-07-23',
    email_subject: 'West desk scheduling',
  },
  {
    evidence_id: 'evidence_4410',
    claim_id: 'claim_7710',
    claim_type: 'informs',
    subject_name: 'John Arnold',
    object_name: 'Enron Gas Trading Desk',
    quote: 'John raised concerns about our exposure if gas prices move against us on this one.',
    confidence: 0.74,
    status: 'active',
    valid_from: '2001-10-09',
    valid_to: null,
    email_date: '2001-10-09',
    email_subject: 'Re: deal exposure',
  },
  {
    evidence_id: 'evidence_4411',
    claim_id: 'claim_7711',
    claim_type: 'requests_from',
    subject_name: 'John Arnold',
    object_name: 'the counterparty',
    quote: 'Arnold wants tighter collateral terms before we move forward.',
    confidence: 0.68,
    status: 'active',
    valid_from: '2001-10-10',
    valid_to: null,
    email_date: '2001-10-10',
    email_subject: 'Collateral terms — action needed',
  },
  {
    evidence_id: 'evidence_4420',
    claim_id: 'claim_7720',
    claim_type: 'informs',
    subject_name: 'John Lavorato',
    object_name: 'Enron America',
    quote: 'Lavorato thinks this one looks good and wants to move faster on it.',
    confidence: 0.81,
    status: 'active',
    valid_from: '2001-10-11',
    valid_to: null,
    email_date: '2001-10-11',
    email_subject: 'Re: timeline',
  },
  {
    evidence_id: 'evidence_4421',
    claim_id: 'claim_7721',
    claim_type: 'requests_from',
    subject_name: 'John Lavorato',
    object_name: 'Finance',
    quote: 'Please confirm the counterparty credit rating before we sign anything.',
    confidence: 0.76,
    status: 'active',
    valid_from: '2001-10-12',
    valid_to: null,
    email_date: '2001-10-12',
    email_subject: 'Credit check before signing',
  },
  {
    evidence_id: 'evidence_4430',
    claim_id: 'claim_7730',
    claim_type: 'informs',
    subject_name: 'John Zufferli',
    object_name: 'Enron Legal',
    quote: 'Zufferli flagged that legal needs to sign off before we go further.',
    confidence: 0.69,
    status: 'active',
    valid_from: '2001-10-13',
    valid_to: null,
    email_date: '2001-10-13',
    email_subject: 'Re: legal review needed',
  },
  {
    evidence_id: 'evidence_4431',
    claim_id: 'claim_7731',
    claim_type: 'negotiating_with',
    subject_name: 'John Zufferli',
    object_name: "the counterparty's trading desk",
    quote: 'John has been going back and forth with their desk on pricing all week.',
    confidence: 0.72,
    status: 'active',
    valid_from: '2001-10-14',
    valid_to: null,
    email_date: '2001-10-14',
    email_subject: 'Pricing discussion — update',
  },
  {
    evidence_id: 'evidence_3391',
    claim_id: 'claim_9932',
    claim_type: 'negotiating_with',
    subject_name: 'Enron',
    object_name: 'Global Crossing',
    quote: '', // genuinely blank in chatMocks.ts too — preserved rather than invented
    confidence: 0.55,
    status: 'active',
    valid_from: '2001-11-19',
    valid_to: null,
    email_date: '2001-11-19',
    email_subject: 'FW: Global Crossing — status',
  },
  {
    evidence_id: 'evidence_2250',
    claim_id: 'claim_8850',
    claim_type: 'informs',
    subject_name: 'Sally Beck',
    object_name: 'sally.beck@enron.com',
    quote: 'You can reach me at sally.beck@enron.com for anything urgent.',
    confidence: 0.91,
    status: 'active',
    valid_from: '2001-06-11',
    valid_to: null,
    email_date: '2001-06-11',
    email_subject: 'Re: contact info',
  },
]

// ---- Sourced from entityMocks.ts claims (no quote text recorded there — templated below) ----
const ENTITY_SOURCED: FillerSpec[] = [
  { evidence_id: 'evidence_1840', claim_id: 'claim_002', claim_type: 'works_with', subject_name: 'Sally Beck', object_name: 'Louise Kitchen', quote: '', confidence: 0.75, status: 'active', valid_from: '2001-03-15', valid_to: null, email_date: '2001-03-15', email_subject: '' },
  { evidence_id: 'evidence_1955', claim_id: 'claim_003', claim_type: 'informs', subject_name: 'Sally Beck', object_name: 'Fletcher Sturm', quote: '', confidence: 0.62, status: 'active', valid_from: '2001-05-10', valid_to: null, email_date: '2001-05-10', email_subject: '' },
  { evidence_id: 'evidence_1622', claim_id: 'claim_004', claim_type: 'works_with', subject_name: 'Sally Beck', object_name: 'West Trading Desk', quote: '', confidence: 0.81, status: 'active', valid_from: '2001-02-01', valid_to: null, email_date: '2001-02-01', email_subject: '' },
  { evidence_id: 'evidence_1623', claim_id: 'claim_004', claim_type: 'works_with', subject_name: 'Sally Beck', object_name: 'West Trading Desk', quote: '', confidence: 0.81, status: 'active', valid_from: '2001-02-01', valid_to: null, email_date: '2001-02-03', email_subject: '' },
  { evidence_id: 'evidence_1401', claim_id: 'claim_005', claim_type: 'works_with', subject_name: 'Sally Beck', object_name: 'Enron America', quote: '', confidence: 0.91, status: 'active', valid_from: '2000-11-01', valid_to: null, email_date: '2000-11-01', email_subject: '' },
  { evidence_id: 'evidence_1402', claim_id: 'claim_005', claim_type: 'works_with', subject_name: 'Sally Beck', object_name: 'Enron America', quote: '', confidence: 0.91, status: 'active', valid_from: '2000-11-01', valid_to: null, email_date: '2000-11-08', email_subject: '' },
  { evidence_id: 'evidence_1403', claim_id: 'claim_005', claim_type: 'works_with', subject_name: 'Sally Beck', object_name: 'Enron America', quote: '', confidence: 0.91, status: 'active', valid_from: '2000-11-01', valid_to: null, email_date: '2000-11-15', email_subject: '' },
  { evidence_id: 'evidence_0980', claim_id: 'claim_007', claim_type: 'reports_to', subject_name: 'Sally Beck', object_name: 'Kenneth Lay', quote: '', confidence: 0.45, status: 'superseded', valid_from: '2000-01-01', valid_to: '2001-07-31', email_date: '2000-01-05', email_subject: '' },
  { evidence_id: 'evidence_1105', claim_id: 'claim_008', claim_type: 'works_with', subject_name: 'John Lavorato', object_name: 'Enron America', quote: '', confidence: 0.79, status: 'active', valid_from: '2000-09-01', valid_to: null, email_date: '2000-09-01', email_subject: '' },
  { evidence_id: 'evidence_1290', claim_id: 'claim_009', claim_type: 'works_with', subject_name: 'Louise Kitchen', object_name: 'Enron America', quote: '', confidence: 0.7, status: 'active', valid_from: '2001-01-10', valid_to: null, email_date: '2001-01-10', email_subject: '' },
  { evidence_id: 'evidence_1710', claim_id: 'claim_010', claim_type: 'works_with', subject_name: 'Fletcher Sturm', object_name: 'Enron America', quote: '', confidence: 0.58, status: 'active', valid_from: '2001-04-01', valid_to: null, email_date: '2001-04-01', email_subject: '' },
  { evidence_id: 'evidence_0102', claim_id: 'claim_011', claim_type: 'works_with', subject_name: 'Kenneth Lay', object_name: 'Enron America', quote: '', confidence: 0.93, status: 'active', valid_from: '1999-01-01', valid_to: null, email_date: '1999-01-01', email_subject: '' },
  { evidence_id: 'evidence_0103', claim_id: 'claim_011', claim_type: 'works_with', subject_name: 'Kenneth Lay', object_name: 'Enron America', quote: '', confidence: 0.93, status: 'active', valid_from: '1999-01-01', valid_to: null, email_date: '1999-02-01', email_subject: '' },
  { evidence_id: 'evidence_2290', claim_id: 'claim_012', claim_type: 'informs', subject_name: 'August 2001 Reorganization', object_name: 'Enron America', quote: '', confidence: 0.66, status: 'active', valid_from: '2001-08-20', valid_to: null, email_date: '2001-08-20', email_subject: '' },
  { evidence_id: 'evidence_1981', claim_id: 'claim_014', claim_type: 'negotiating_with', subject_name: 'John Lavorato', object_name: 'Global Crossing Transaction', quote: '', confidence: 0.84, status: 'active', valid_from: '2001-07-01', valid_to: null, email_date: '2001-07-05', email_subject: '' },
  { evidence_id: 'evidence_2005', claim_id: 'claim_015', claim_type: 'requests_from', subject_name: 'Enron Legal', object_name: 'Global Crossing Transaction', quote: '', confidence: 0.68, status: 'active', valid_from: '2001-07-15', valid_to: null, email_date: '2001-07-15', email_subject: '' },
  { evidence_id: 'evidence_2006', claim_id: 'claim_015', claim_type: 'requests_from', subject_name: 'Enron Legal', object_name: 'Global Crossing Transaction', quote: '', confidence: 0.68, status: 'active', valid_from: '2001-07-15', valid_to: null, email_date: '2001-07-17', email_subject: '' },
  { evidence_id: 'evidence_2007', claim_id: 'claim_015', claim_type: 'requests_from', subject_name: 'Enron Legal', object_name: 'Global Crossing Transaction', quote: '', confidence: 0.68, status: 'active', valid_from: '2001-07-15', valid_to: null, email_date: '2001-07-19', email_subject: '' },
  { evidence_id: 'evidence_2150', claim_id: 'claim_016', claim_type: 'informs', subject_name: 'Approve Global Crossing Deal', object_name: 'Global Crossing Transaction', quote: '', confidence: 0.6, status: 'active', valid_from: '2001-08-01', valid_to: null, email_date: '2001-08-01', email_subject: '' },
  { evidence_id: 'evidence_2305', claim_id: 'claim_019', claim_type: 'informs', subject_name: 'August 2001 Reorganization', object_name: 'John Lavorato', quote: '', confidence: 0.63, status: 'active', valid_from: '2001-08-25', valid_to: null, email_date: '2001-08-25', email_subject: '' },
  { evidence_id: 'evidence_2261', claim_id: 'claim_020', claim_type: 'informs', subject_name: 'August 2001 Reorganization', object_name: 'Kenneth Lay', quote: '', confidence: 0.71, status: 'active', valid_from: '2001-08-10', valid_to: null, email_date: '2001-08-11', email_subject: '' },
  { evidence_id: 'evidence_2010', claim_id: 'claim_022', claim_type: 'informs', subject_name: 'Greg Whalley', object_name: 'August 2001 Reorganization', quote: '', confidence: 0.58, status: 'superseded', valid_from: '2001-07-01', valid_to: '2001-08-01', email_date: '2001-07-01', email_subject: '' },
]

const CLAIM_TYPE_QUOTE_TEMPLATES: Record<string, (subject: string, object: string) => string> = {
  reports_to: (s, o) => `${s} confirmed reporting directly to ${o}.`,
  works_with: (s, o) => `${s} has been working closely with ${o} on this.`,
  negotiating_with: (s, o) => `${s} is in active negotiation with ${o}.`,
  requests_from: (s, o) => `${s} requested this directly from ${o}.`,
  informs: (s, o) => `${s} flagged this for ${o}'s attention.`,
}

const CLAIM_TYPE_SUBJECT_TEMPLATES: Record<string, (object: string) => string> = {
  reports_to: (o) => `Re: reporting line — ${o}`,
  works_with: (o) => `Re: working with ${o}`,
  negotiating_with: (o) => `Re: negotiation — ${o}`,
  requests_from: (o) => `Re: request — ${o}`,
  informs: (o) => `FYI — ${o}`,
}

function buildFillerDetail(spec: FillerSpec): EvidenceDetailResponse {
  const quote = spec.quote || (CLAIM_TYPE_QUOTE_TEMPLATES[spec.claim_type]?.(spec.subject_name, spec.object_name) ?? '')
  const emailSubject = spec.email_subject || CLAIM_TYPE_SUBJECT_TEMPLATES[spec.claim_type]?.(spec.object_name) || 'Update'
  const emailFrom = spec.email_from ?? emailFor(spec.subject_name)
  const emailTo = spec.email_to ?? [emailFor(spec.object_name)]
  const mainLine = quote || `Wanted to send a quick update regarding ${spec.object_name}.`

  return {
    evidence_id: spec.evidence_id,
    quote,
    confidence: spec.confidence,
    claim_id: spec.claim_id,
    claim_type: spec.claim_type,
    subject_name: spec.subject_name,
    object_name: spec.object_name,
    email_subject: emailSubject,
    email_from: emailFrom,
    email_date: spec.email_date,
    email_body: buildBody(spec.object_name, spec.subject_name, mainLine),
    subject_id: idFor(spec.subject_name),
    object_id: idFor(spec.object_name),
    status: spec.status,
    valid_from: spec.valid_from,
    valid_to: spec.valid_to,
    email_to: emailTo,
  }
}

const FILLER_DETAILS: Record<string, EvidenceDetailResponse> = Object.fromEntries(
  [...CHAT_SOURCED, ...ENTITY_SOURCED].map((spec) => [spec.evidence_id, buildFillerDetail(spec)]),
)

function delay(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

/** Simulates GET /api/evidence/{id}. Throws on an unknown id — callers should catch this
 * and render a "not found" state, same idiom as entityMocks.ts's mockFetchEntityDetail. */
export async function mockFetchEvidence(evidenceId: string): Promise<EvidenceDetailResponse> {
  await delay(300)
  const found = SHOWCASE[evidenceId] ?? FILLER_DETAILS[evidenceId]
  if (!found) {
    throw new Error(`Evidence "${evidenceId}" not found`)
  }
  return found
}

/** Dev-time integrity check, same pattern as graphMocks.ts's validateMockIntegrity() and
 * entityMocks.ts's validateEntityMockIntegrity(): catches (1) an evidence_id accidentally
 * defined twice across SHOWCASE/FILLER_DETAILS, and (2) a non-empty quote that doesn't
 * actually appear in its own email_body — which would silently break the Day 40 brief's
 * highlighting requirement (`email_body.includes(quote)`). */
export function validateEvidenceMockIntegrity(): string[] {
  const problems: string[] = []
  const seen = new Set<string>()

  for (const spec of [...CHAT_SOURCED, ...ENTITY_SOURCED]) {
    if (SHOWCASE[spec.evidence_id]) {
      problems.push(`"${spec.evidence_id}" is defined in both SHOWCASE and a filler spec.`)
    }
    if (seen.has(spec.evidence_id)) {
      problems.push(`"${spec.evidence_id}" is defined more than once in the filler specs.`)
    }
    seen.add(spec.evidence_id)
  }

  for (const evidence of [...Object.values(SHOWCASE), ...Object.values(FILLER_DETAILS)]) {
    if (evidence.quote && !evidence.email_body?.includes(evidence.quote)) {
      problems.push(`"${evidence.evidence_id}" has a quote that does not appear verbatim in its email_body.`)
    }
  }

  return problems
}

if (import.meta.env.DEV) {
  const problems = validateEvidenceMockIntegrity()
  if (problems.length > 0) {
    console.error('evidenceMocks.ts integrity check failed:\n' + problems.join('\n'))
  }
}
