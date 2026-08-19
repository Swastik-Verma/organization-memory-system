EXTRACTION_INSTRUCTIONS = """You are analyzing an internal company email to extract structured organizational knowledge.

Read the email below and extract ONLY information that is explicitly stated in the text. Do not guess, correct, infer, or invent details that are not directly supported by the email content.

Extract:

- People: anyone mentioned by name, including sender/recipients and anyone referenced in the body.
  - Write names in proper human form ("John Arnold"), never as an email handle ("john.arnold"). If only an email address is available and no written name appears, convert it to proper capitalized name form.
  - Only include an email address if it appears EXACTLY as written in the email metadata or body. Do not guess, complete, or "fix" a malformed or partial email address. If unsure, leave the email field empty.
  - Only include role/title if it is explicitly stated in the email.

- Organizations: companies, business divisions, or departments that are clearly organizational entities relevant to the email's content.
  - Do NOT treat someone's personal email domain (e.g. gmail.com, aol.com, or a small ISP) as an organization unless the email clearly indicates that domain represents a real company the person works for or does business with.

- Deals: genuine business transactions, contracts, or professional projects only.
  - Do NOT classify personal or social plans as deals — trips, parties, receptions, or social gatherings are NOT deals.
  - Do NOT extract document titles, file names, attachment names, or archive/log entries as deals. A line like "Media info (created by ...)" is a document reference, not a deal.
  - Do NOT extract a word as a deal just because it appears in a subject line or meeting/dial-in note. Only extract a deal if the email describes actual business substance about it.

- Decisions: an explicit choice, commitment, agreement, or instruction stated in the email (e.g. "I will send the report by Friday", "we approved the contract", "please arrange X").
  - The `made_by` field must name the person who MADE or STATED the decision — NOT the person being asked to perform the action. If someone requests or instructs something, the REQUESTER is `made_by`. Example: if Kay asks Suzanne to update a calendar, `made_by` is Kay, and Suzanne belongs in `affects`.
  - If the decision-maker is not clearly identifiable from the text, leave `made_by` empty rather than guessing.
  - Do NOT extract a plain description of something that already happened as a decision, unless it states an actual approval or choice.

- Relationships: connections between people that are directly evidenced in the email text.
  - Use ONLY one of these relationship_type values: reports_to, works_with, requests_from, negotiating_with, informs.
  - The `evidence` field MUST contain an exact verbatim quote from the email body that supports the relationship. If you cannot quote a specific phrase from the body, DO NOT extract that relationship at all.
  - Greetings ("Hi guys", "Dear team") are NOT evidence. Generic descriptions of the email itself ("internal communication regarding X") are NOT evidence — those are your own reasoning, not a quote.
  - Do NOT infer a relationship merely because two people share an email domain, appear on the same distribution list, or are both mentioned in the same email. There must be a stated interaction between them.

If the email contains nothing relevant for a category, return an empty list for that category. An empty list is a valid, correct answer — do not fabricate content to avoid returning an empty list.

---
EMAIL METADATA:
From: {from_addr}
To: {to_addrs}
Subject: {subject}

EMAIL BODY:
{body}
---

Extract the structured information now."""


def build_prompt(from_addr: str, to_addrs: list[str], subject: str, body: str) -> str:
    return EXTRACTION_INSTRUCTIONS.format(
        from_addr=from_addr,
        to_addrs=", ".join(to_addrs) if to_addrs else "(none listed)",
        subject=subject or "(no subject)",
        body=body,
    )