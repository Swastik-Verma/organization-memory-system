# Ontology Design — Knowledge Graph Schema

## Core decision: reified claims (Model B)

Relationships between entities are stored as **nodes** (`:Claim`), not as
direct edges. A direct edge `(:Person)-[:REPORTS_TO]->(:Person)` is simpler,
but a Neo4j relationship cannot be the endpoint of another relationship — so
there is nowhere to attach:

- Multiple evidence items supporting the same fact
- A validity window (valid_from / valid_to)
- A supersession link to a newer contradicting claim
- A conflict link between two claims that disagree
- A confidence score
- Soft deletion flags

Reifying the claim as a node solves all of these. The cost is one extra hop
per query (Person → Claim → Person instead of Person → Person). The benefit
is that every feature in the plan (temporal queries, conflict detection,
confidence decay, evidence trails) works naturally.

## Node types

| Label | What it represents | ID strategy |
|---|---|---|
| Person | A real human | Slugified canonical name |
| Organization | A company, government body, etc. | Slugified canonical name |
| Deal | A business transaction or contract | Slugified name |
| Decision | An action or choice stated in email | Hash of message_id + description |
| Claim | A reified relationship between entities | Hash of message_id + type + subject + object + quote |
| Evidence | A verbatim quote from an email body | Hash of message_id + quote |
| Message | One email from the corpus | Original RFC 2822 Message-ID |

## Temporal model

- `valid_from` = date of the email that stated the fact (first observed)
- `valid_to` = null (still true) until a later email contradicts it
- This is "first observed at," not true validity — we cannot know when a
  fact actually started being true, only when we first saw evidence for it
- 535 emails have null dates — their claims get `valid_from = null`,
  excluded from point-in-time queries, included in full-history queries

## Org type normalization

The LLM produces 120+ free-text org_type values. These are normalized at
ingestion to a closed set: company, government, nonprofit, university,
internal_division, other.

## The affects problem (§9.1)

`Decision.affects` contains a mix of real names ("Cindy Olson") and
generic placeholders ("employees", "the team"). 91.3% match a known
person or org name — these become real AFFECTS edges. The remaining 8.7%
are stored as `affects_unresolved` text on the Decision node. No node is
created for unresolvable strings, preventing fake hub nodes from
corrupting graph metrics.

## Alternatives rejected

- **Direct edges instead of reified claims**: rejected because evidence,
  temporal windows, and supersession links cannot attach to Neo4j edges
- **Random UUIDs for node IDs**: rejected because MERGE becomes useless —
  re-running ingestion creates duplicates instead of being idempotent
- **LLM-reported confidence scores**: rejected because the model returns
  ~0.9 for everything regardless of actual certainty. Confidence will be
  computed deterministically from verifiable signals at ingestion (Days 8-11)