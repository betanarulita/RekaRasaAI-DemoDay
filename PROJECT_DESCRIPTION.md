# RekaRasa.ai — Project Description

**Tim Velo: Kheylina, Beta, Abigailly**
**Challenge C (The Creator Agent) · AI CAN DO IT — Tencent Cloud Hackathon Indonesia 2026**

---

## 1. Project Overview

### What RekaRasa.ai Is

RekaRasa.ai is a **creator workspace that turns a product brief into marketing copy — and refuses to let any copy through until its claims are backed by a source attached to the project**. Three AI agents propose content. Server-side deterministic code decides whether it passes. A human approves. The model never has the last word.

It is not a text generator with a review button. It is a **trust-boundary architecture** where no single component can wave content through.

### Target Scenarios

| Scenario | What Happens Today (Without RekaRasa) | What RekaRasa Does |
|---|---|---|
| An UMKM owner writes a caption claiming " menyembuhkan maag" for a ginger drink | The claim goes live, violating PerBPOM 18/2024 and UU 8/1999 | The regex guard in `save_review()` catches the disease-cure claim regardless of what the Reviewer model says, blocks approval, and asks for a revision |
| A cosmetic brand writes "tersertifikasi halal" without attaching proof | Unverified certification claim reaches the public | The halal guard checks attached sources; without documentation, the claim is rejected |
| A copywriter invents a BPOM notification number | Fictitious regulatory number is published | The certificate verifier cross-references `data/cert_registry_mock.csv`; an unknown/expired/revoked number adds a `Fail` finding |
| A marketer writes "teruji klinis" with no supporting source | Unsupported claim ships | The evidence-binding guard requires a `source_id` that is actually attached to the project for any factual `Pass`; no source = `Needs Evidence` |
| A content team drafts campaign copy across Instagram and Marketplace | Manual process, inconsistent compliance | Planner generates separate tasks per channel; Writer produces format-specific drafts; Reviewer checks each against project rules |

### Target Users

1. **UMKM / SME owners** — small Indonesian businesses producing food, cosmetic, and consumer goods who need marketing copy but lack a legal/compliance team to check claims before publication.
2. **Content creators and social media managers** — freelancers and in-house marketers producing multi-platform campaign copy who need a structured workflow from brief to approved deliverable.
3. **Brand compliance teams** — the "Penanggung Jawab / Tim Legal" who are the final authority but want a first-line filter so that obviously non-compliant content never reaches their desk.

### Value Proposition

> **RekaRasa.ai catches what the model misses — in code, not in prompts.**

The core insight: most "AI agent" demos ask the model to grade its own homework. That is not accountability — it is a second opinion from the same source of error. RekaRasa splits the work so that:

- The **model proposes** (drafts, findings, image concepts)
- The **code decides** (schema validation, source ownership, rule coverage, regex guards, certificate verification, evidence binding, character limits, format structure)
- The **human approves** (the final gate, always)

No prompt instruction can talk the code out of rejecting a disease-cure claim. No client-side request can bypass the `save_review()` guards. The trust boundary is architectural, not advisory.

---

## 2. Real-World Scenario Insights

### Source of Pain Points

The pain points driving RekaRasa come from real Indonesian regulatory and market conditions:

1. **PerBPOM 18/2024 (Cosmetics Advertising)** — Promotional content for cosmetics must be objective, honest, and not misleading; it must not give the impression of being a drug or disease preventative. Many small brands unknowingly cross this line with claims like "memperbaiki sel kulit mati dari dalam" (implies biological repair below the skin surface).

2. **UU 8/1999 (Consumer Protection)** — Articles 9 and 10 prohibit false or misleading statements about product characteristics, price, discounts, guarantees, and usage risks. Copywriters under deadline pressure routinely invent "facts" that have no basis in the product's actual documentation.

3. **Halal certification (BPJPH)** — Displaying a halal label requires an actual certificate. Claiming halal status without documentation is a compliance violation, but copywriters often add "halal" as a marketing word without verifying.

4. **BPOM notification numbers** — Cosmetics require a notification number (NA...). Using a fictitious or expired number in promotional copy is illegal, but there is no easy pre-publication check for small teams.

5. **The "AI says it, so it must be true" problem** — When generative AI writes marketing copy, it hallucinates confidently. A model that writes "terbukti menyembuhkan jerawat dalam 7 hari" is not malicious — it is optimizing for persuasive language. The result is still a regulatory violation.

### Core Problem Solved

**How do you let AI generate marketing copy without letting AI-generated hallucinations become legal liabilities?**

RekaRasa solves this by separating the generation layer (which is assumed fallible) from the decision layer (which is deterministic code). The model can write whatever it wants. The code checks every claim against:
- Does the cited `source_id` actually exist in this project?
- Does the cited `rule_id` exist in the project's rule registry?
- Does a factual `Pass` cite the source that states the fact?
- Did the Reviewer address every configured rule? (Missing = `Needs Evidence`, never silent `Pass`)
- Does a regex pattern catch disease-cure or undocumented halal claims even when the Reviewer says `Pass`?
- Does the draft meet minimum character requirements for its format?
- Does a marketplace listing have a TITLE and DESCRIPTION? Does a poster have HEADLINE, BODY, and CTA?
- Is the BPOM/Halal certificate number present and active in the registry?

### Target Audience

**Primary:** Indonesian UMKM and SME owners in food, cosmetic, and consumer goods categories who produce their own marketing content and operate without a dedicated compliance/legal team.

**Secondary:** Content agencies and freelance copywriters who serve multiple clients and need a structured, auditable workflow that produces defensible copy.

**Tertiary:** Brand compliance teams who want a first-line filter so that when content reaches legal review, the obviously non-compliant material has already been caught.

---

## 3. Comprehensive Solution Design

### Business Architecture

```
┌─────────────────────────────────────────────────────┐
│                    USER (Human)                      │
│         Final approval gate — always required        │
└──────────────────────┬──────────────────────────────┘
                       │
          ┌────────────▼────────────┐
          │    RekaRasa.ai App      │
          │  (Python stdlib WSGI)   │
          │                         │
          │  ┌─────┐ ┌──────┐ ┌─────┐  │
          │  │Rara │ │Reka  │ │Raya │  │
          │  │ Plan│ │Write │ │ Revi│  │
          │  │ ner │ │  er  │ │ ewer│  │
          │  └──┬──┘ └──┬───┘ └──┬──┘  │
          │     │       │        │     │
          │  ┌──▼───────▼────────▼──┐  │
          │  │   save_review()      │  │
          │  │  (DETERMINISTIC)     │  │
          │  │  7 code-level guards │  │
          │  │  Certificate verify  │  │
          │  │  Evidence binding    │  │
          │  └──────────┬───────────┘  │
          │             │              │
          │  ┌──────────▼───────────┐  │
          │  │   SQLite Audit Trail │  │
          │  │  (versions, findings,│  │
          │  │   approvals, tokens) │  │
          │  └──────────────────────┘  │
          └────────────┬───────────────┘
                       │
          ┌────────────▼────────────┐
          │   External Providers    │
          │  ┌──────┐  ┌─────────┐  │
          │  │ Groq │  │ ComfyUI │  │
          │  │ (LLM)│  │ (Image) │  │
          │  └──────┘  └─────────┘  │
          └─────────────────────────┘
```

**Key architectural principle: the trust boundary.** The three agents (Planner, Writer, Reviewer) live on the "can be wrong" side. The `save_review()` function and all validation guards live on the "cannot be talked out of it" side. The human lives on the "final authority" side. No component crosses into another's authority.

### Technical Architecture

**Stack:**
- **Backend:** Python 3.12, pure standard-library WSGI (`wsgiref.simple_server`) — no Flask, no Django, no external web framework
- **Database:** SQLite (single-file, per-account isolation, numbered SQL migrations)
- **LLM Provider:** Groq `openai/gpt-oss-20b` via OpenAI-compatible Chat Completions API with strict JSON Schema
- **Image Provider:** ComfyUI (local, SD 1.5 `v1-5-pruned-emaonly.safetensors`); optional Cloudflare text-to-image concepts
- **Frontend:** Vanilla HTML/CSS/JS (no build step, no framework)
- **Auth:** Salted PBKDF2 password hashes, expiring HTTP-only sessions, SameSite cookies, CSRF tokens on all mutations
- **Hosting:** WorkBuddy deployment platform / Render (Dockerfile + render.yaml blueprint)
- **Code size:** 3,458 lines (`app.py`) + 988 lines (`app.js`) + 861 lines (`styles.css`) + 1,838 lines (`test_app.py`) = ~7,145 lines

**54 API routes** handle: authentication, project management, source upload (Markdown/plain text, 250 KB cap), brief submission, planning, plan confirmation, draft generation, revision, review, approval, image generation (4 modes), composition, visual approval, export (SVG/PNG), history, calendar, and data export.

### How Prompts Drive AI Generation

Each of the three agent roles has a **separate system prompt, a separate JSON Schema contract, and a separate recorded run**. They share the same Groq model but never see each other's raw instructions.

#### Agent 1: Rara (Planner)

**Role:** Reads the brief and project context, then proposes an objective, supported product facts, constraints, missing information, and content tasks.

**Prompt architecture:**
- System prompt includes channel instructions, format requirements, and the grounding directive: "Exclude unsupported factual claims and explain that they were excluded in constraints."
- User payload includes: the brief text, project sources (with IDs), prior plan (if revising), catalog attachments, audience/tone preferences, and channel preferences.
- The Planner is explicitly instructed: "List `missing_information` only for a detail that makes the requested deliverable impossible to produce safely. Price, variants, discount, stock, audience, deadline, and tone are optional — proceed without asking."
- A **grounding function** (`keep_grounded_planner_facts()`) runs after the model returns: it strips any `product_facts` entry that cannot be traced to the brief or attached sources, and moves them into `constraints` with the notice: "Unsupported product details were excluded; do not invent or rely on them."

**Output schema (strict JSON):**
```json
{
  "objective": "string",
  "audience": "string",
  "product_facts": ["array of strings — each must be traceable to a source"],
  "constraints": ["array of strings"],
  "missing_information": ["array of strings — only genuinely blocking gaps"],
  "tasks": [{
    "title": "string",
    "format": "Social media post | Marketplace listing | Poster | ...",
    "platform": "Instagram | TikTok | Facebook | Threads | X | Marketplace | General",
    "angle": "string",
    "goal": "string",
    "selection_reason": "string"
  }]
}
```

**Classification layer (added this session):** `classify_planner_gaps()` splits `missing_information` into:
- **Blocking gaps** (e.g., "Product name is not found") → returned as `needs_clarification: true`
- **Optional gaps** (price, variants, discount, stock, audience, tone, hours, address) → moved into `constraints` so the Writer omits them gracefully; the plan proceeds

#### Agent 2: Reka (Writer)

**Role:** Creates each task's draft from the brief and attached project sources. Cites source IDs. Can make up to 3 revisions from review findings.

**Prompt architecture:**
- System prompt (`writer_instructions()`) is format-aware: a Social media post gets different instructions than a Marketplace listing or a Poster. Each includes channel-specific guidance (Instagram = portrait 4:5, TikTok = vertical 9:16, etc.).
- User payload includes: the brief, audience, tone, the specific task (title, format, platform, angle, goal, selection reason), the full plan (including constraints — this is how optional gaps reach the Writer), project sources with IDs, prior draft (if revising), and review findings (if remediating).
- The Writer is instructed to separate on-image text blocks (`HEADLINE`, `BODY`, `CTA`) from caption text (`CAPTION`) and visual direction (`VISUAL`) when the format requires it.
- For image formats: the configured image provider generates the base image; the backend composes the stored Writer text over it as deterministic SVG — the model is never asked to spell text on an image.

**Output schema:**
```json
{
  "drafts": [{
    "task_id": "string",
    "content": "string — structured with HEADLINE/BODY/CTA/CAPTION/VISUAL blocks",
    "source_ids": ["array — each must be a valid source attached to this project"]
  }]
}
```

**Server-side validation after model returns:**
1. The chosen draft's `source_ids` must be a subset of the project's actual sources. If not → `502 invalid_agent_output`.
2. The task is re-checked after the model call (not before) — if it was archived or already has a draft, the write is rejected. This prevents race conditions.
3. The draft is stored as a new immutable version; history is never overwritten.

#### Agent 3: Raya (Reviewer)

**Role:** Checks draft claims against attached sources and configured review rules. Returns findings (`Pass`, `Fail`, `Needs Evidence`).

**Prompt architecture:**
- System prompt includes the project's rule registry (rule IDs, versions, criteria text, whether evidence is required).
- User payload includes: the draft content, project sources, and the rules to evaluate.
- The Reviewer returns structured findings with: `rule_id`, `claim` (exact text from the draft), `result` (Pass/Fail/Needs Evidence), `evidence_source_id`, `explanation`, `recommendation`.

**The critical design decision: the Reviewer's output is not the verdict.** `save_review()` runs after the Reviewer returns and applies 7 deterministic checks that can override any model finding:

| # | Guard | What It Catches | Can the Model Override It? |
|---|---|---|---|
| 1 | Invalid `rule_id` | A rule not in the project registry | No — downgraded to `Needs Evidence` |
| 2 | Invalid `source_id` | A source not attached to this project | No — downgraded to `Needs Evidence` |
| 3 | Factual Pass without source | A `Pass` on a factual rule that cites no source | No — downgraded to `Needs Evidence` |
| 4 | Rule coverage | Any configured rule the Reviewer didn't address | No — auto-added as `Needs Evidence` |
| 5 | Disease-cure regex | Pattern like "menyembuhkan maag", "obat diabetes", "bebas dari jerawat" | No — auto-added as `Fail` even if Reviewer said `Pass` |
| 6 | Undocumented halal regex | The word "halal" without supporting documentation in sources | No — auto-added as `Fail` unless `halal_is_documented()` |
| 7 | Certificate verification | BPOM (NA...) and Halal (ID...) numbers checked against registry | No — unknown/expired/revoked numbers add `Fail` |

**Additional deterministic checks:**
- Every `Pass`/`Fail` must have `document_id`, `span_start`, `span_end` — a verdict without text location cannot be saved (evidence binding).
- Drafts below the character floor for their format are not deliverable.
- A revision that keeps less than half of the previous draft is flagged.
- A poster must label HEADLINE, BODY, CTA; a marketplace listing must label TITLE, DESCRIPTION.

### Image Pipeline

Four image modes are supported:

| Mode | Input | Engine | What Stays Fixed |
|---|---|---|---|
| Original composition | Project photo + validated Writer copy | Local SVG composition | Photo pixels, subject, lettering |
| Text-to-image | Visual prompt + brief context | ComfyUI (SD 1.5) | No product-identity guarantee |
| Image-to-image | Photo bytes + prompt + strength (0.1–0.85) | ComfyUI (LoadImage→ImageScale→VAEEncode→KSampler→VAEDecode) | Canvas size; subject details can change |
| Protected edit | Photo + prompt + protection mask | ComfyUI (inpaint/composite path) | Protected pixels composited at original resolution |

**Key principle:** The image provider generates the base image only. The backend places the stored, reviewed, and approved Writer text over it as deterministic SVG. The model is never asked to render text on an image — that eliminates the spelling/OCR problem entirely.

Visual approval requires: approved copy (latest version), a passing review, explicit visual inspection checkbox, and composition hash matching. Editing copy invalidates the old visual export.

### Remediation Flow

```
Draft → Review → save_review() decides
  → Pass            → human approval gate → approved
  → Fail/Needs Evidence → Writer remediation (max 3 attempts)
  → Limit reached      → escalate to human
  → Reviewer crashed   → draft preserved, review retried, never a dead end
```

Each state has exactly one meaning. A human edit produces a `pending` version that needs a *review*, not a rewrite — so a Writer retry can never silently overwrite work a person typed.

---

## 4. Business Value

### Quantifiable Metrics

| Metric | Value | Source |
|---|---|---|
| **Violation detection rate** | 100% (8/8) | `tests/run_live_reviewer.py` against 10 cases (8 violations, 2 legitimate) |
| **False-positive rate** | 0% (0/2) | Same harness — legitimate cosmetic claims under PerBPOM 18/2024 are not rejected |
| **Test coverage** | 201 tests pass across 6 test files | `test_app.py`, `test_image_modes.py`, `test_project_actions.py`, `test_visual_content.py`, `test_evidence_binding.py`, `test_claim_evaluation.py` |
| **Synthetic evaluation corpus** | 240 cases across 12 claim families, 2 evidence conditions, 10 placements | `evaluation/claims-v1.jsonl` with datacard |
| **Deterministic guards** | 7 code-level checks + certificate verification | All in `save_review()`, none in prompts |
| **API routes** | 54 | `app.py` |
| **Agent roles** | 3 content agents + 1 image editor | Planner, Writer, Reviewer, Image Editor |
| **Image modes** | 4 (composition, text-to-image, image-to-image, protected edit) | ComfyUI SD 1.5 backend |
| **Supported channels** | 6 (Instagram, TikTok, Facebook, Threads, X, Marketplace) | `visual_content.py` |
| **Max remediation attempts** | 3 (hard server limit) | `MAX_ITERATIONS` |
| **Code lines** | ~7,145 | `app.py` (3,458) + `app.js` (988) + `styles.css` (861) + `test_app.py` (1,838) |

### Defined Impact

**For UMKM/SME owners:**
- **Pre-publication compliance filtering:** Claims that would violate PerBPOM 18/2024 (disease-cure, drug-like implications), UU 8/1999 (false/misleading statements), or halal certification requirements are caught *before* content reaches the public, not after a regulatory complaint.
- **Zero-cost entry:** The app runs on free-tier infrastructure (Groq free tier, local ComfyUI, SQLite). No paid API key is bundled — the operator provides their own.
- **Multi-platform output from a single brief:** One brief produces separate tasks for Instagram, Marketplace, and other channels — each with format-appropriate structure.

**For content teams:**
- **Auditable workflow:** Every decision is recorded — versions, findings, rule IDs, source IDs, claim spans, approvals, token usage, and audit events. A reviewer can trace exactly why a claim was rejected and where in the draft it appeared.
- **Bounded remediation:** The 3-attempt limit prevents infinite AI self-correction loops. After 3 failed revisions, a human takes over — the system escalates rather than spiraling.
- **Immutable history:** Every revision creates a new version. History is never overwritten. A human edit produces a `pending` version that needs review, so AI can never silently overwrite human work.

**For compliance teams:**
- **First-line filter:** By the time content reaches legal review, the obviously non-compliant material (disease-cure claims, undocumented halal, fictitious BPOM numbers, unsupported factual claims) has already been caught. The legal team's time is spent on nuanced judgment calls, not on catching "menyembuhkan maag" in a ginger drink ad.
- **Honest disclosure:** The system explicitly states what it does and does not verify. Certificate checks use a local mock registry, not official BPOM/BPJPH databases. No claim of legal completeness is made. This transparency is itself a Responsible AI practice under SE Menkominfo 9/2023.

**For the hackathon (Challenge C):**
- **Architecture as evidence:** The trust boundary is not a marketing claim — it is visible in the code. `save_review()` is 200+ lines of deterministic guards that any judge can read and audit.
- **Real provider verification:** The full flow (register → plan → confirm → generate → review → approve) was verified against the live Groq API on 29 October 2026. Image generation was verified against a local ComfyUI server on 6 November 2026.
- **Indonesian regulatory context:** The system maps directly to PerBPOM 3/2022, PerBPOM 18/2024, SE Menkominfo 9/2023, UU PDP 27/2022, UU PK 8/1999, and BPJPH halal verification — not as legal automation, but as a compliance-aware content tool.

### Why This Matters

The gap RekaRasa fills is not "AI can't write good copy" — it can. The gap is: **AI writes copy that is confidently wrong, and there is no structured way to stop the wrongness from becoming a legal liability before publication.**

Existing solutions fall into two camps:
1. **Plain text generators** (ChatGPT, etc.) — fast, but no compliance layer, no source grounding, no audit trail. Every claim is the model's opinion.
2. **Enterprise compliance platforms** — thorough, but expensive, slow, and designed for large teams with dedicated legal resources. UMKM owners cannot use them.

RekaRasa occupies the middle: **AI-generated copy with deterministic compliance guards, a structured approval workflow, and an honest statement of its own limits.** It is a first-line filter, not a legal oracle — and it says so explicitly.

---

## 5. Architecture Diagram

```
BRIEF → Planner (Rara)
         │  Grounding: strips unsupported product_facts
         │  Classification: optional gaps → constraints (not blockers)
         │
         ▼
      PLAN (tasks per channel/format)
         │
         ▼
      Writer (Reka)
         │  Format-aware instructions per channel
         │  Source IDs required in output
         │  HEADLINE/BODY/CTA/CAPTION/VISUAL blocks
         │
         ▼
      DRAFT (immutable version)
         │
         ▼
      Reviewer (Raya)
         │  Checks claims against rules + sources
         │  Returns Pass/Fail/Needs Evidence
         │
         ▼
   ═══════════════════════════════
   ║   save_review() — CODE      ║   ← TRUST BOUNDARY
   ║   7 deterministic guards    ║   ← Model cannot override
   ║   Certificate verification  ║   ← Deterministic
   ║   Evidence binding (spans)  ║   ← Required for every verdict
   ║   Rule coverage check       ║   ← Missing = Needs Evidence
   ╚═════════════════════════════╝
         │
    ┌────┴────┐
    │ Pass    │ → Human approval gate → APPROVED → Export (SVG/PNG)
    │ Fail    │ → Writer remediation (max 3) → Re-review
    │ Needs   │ → Writer remediation or human escalation
    │ Evidence│
    └─────────┘
```

---

*Built for **AI CAN DO IT — Tencent Cloud Hackathon Indonesia 2026**, Challenge C (The Creator Agent). Tim Velo: Kheylina, Beta, Abigailly.*
