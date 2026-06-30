# JobApplicationAgent — User Experience Flow

## Purpose

This document describes the end-to-end user experience of JobApplicationAgent from
the perspective of someone using the system. It is written for an agent
skills builder who needs to understand what the system does, what the user
sees and does at each step, and how the pieces connect — without needing
to understand the underlying implementation.

---

## Overview

The user interacts with JobApplicationAgent through a conversational chat interface.
The experience has three phases that happen in order:

1. **Setup** — the user provides their background once
2. **Analysis** — the user provides a job posting, gets a fit score
3. **Output** — the user receives a cover letter and refines it

After setup is complete, phases 2 and 3 repeat for each new job. The
user's background is remembered for the entire session, so they never
provide it again.

---

## Phase 1: Setup — Building the Candidate Profile

### What the user does

The user starts a conversation with the agent. If no profile exists yet,
the agent immediately asks for one before doing anything else.

The agent presents two options:

```
Welcome to JobApplicationAgent. Before we analyze any job postings, I need to
build your candidate profile.

You can either:
  1. Upload your resume (PDF)
  2. Paste your resume text or LinkedIn experience directly

Which would you prefer?
```

The user responds with either a file upload or by pasting their text.
They do not need to format it in any special way — the agent accepts
any resume format.

### What the agent does (invisibly to the user)

The agent reads the resume and extracts structured information: name,
current title, years of experience, technical skills organized by
category, notable projects with their technologies, work history, and
education. It also looks for a GitHub username, and if it finds one,
it fetches the user's public repositories to enrich the profile with
additional technology evidence and project summaries.

### What the user sees next

The agent presents its extraction as a readable summary and asks the
user to confirm:

```
Here's what I found in your resume. Please confirm or correct anything:

Name:        Stephen Tarter
Title:       Senior Software Architect
Experience:  20 years

Skills:
  Languages:      Java, Python, TypeScript
  Frameworks:     Spring Boot, React
  Infrastructure: AWS, Kubernetes, Kafka, Redis

Projects:
  • Roadrunner — Distributed vehicle simulation platform
    (Spring Boot, Kafka, Redis, Kubernetes)
  • roadrunner-k8s-orchestration — Terraform/Helm/EKS deployment
  • kaggle-playground-series — ML competition notebooks

GitHub: SteveTarter ✓ (3 public repos found)

Does this look right? Reply "looks good" to confirm, or tell me
what to add or change.
```

### What the user does

The user reviews the summary and either confirms it or corrects it
in plain language:

- "Looks good" → profile is locked in, ready for job analysis
- "I also have Go experience from a side project" → agent adds it
- "My title is Principal Architect, not Senior" → agent corrects it

Once the user confirms, the profile is saved for the session. The agent
will never ask for it again unless the user explicitly asks to update it.

### Key experience qualities

- The user provides their background exactly once
- They see and approve what was extracted before it is used
- Corrections happen in plain language, not by re-uploading
- The GitHub enrichment happens silently — the user just sees
  the result ("3 public repos found")

---

## Phase 2: Job Analysis — Reading the Posting

### What the user does

The user provides a job posting in one of three ways:

**Option A — Paste a URL:**
```
Here's a job I'm interested in:
https://boards.greenhouse.io/block/jobs/12345
```

**Option B — Paste the job description text:**
```
Here's the job description:

Senior Software Engineer, Backend
Block (Cash App) · Remote

We're looking for a senior backend engineer to join our
infrastructure team...
[full job description]
```

**Option C — Both at once (common):**
The user drops a URL and adds context in the same message. The agent
handles this naturally.

### What the agent does (invisibly to the user)

If a URL was provided, the agent fetches the page and cleans it,
stripping navigation, footers, cookie banners, and marketing copy.
It then extracts the structured content of the posting: the role
title, company, required skills, preferred skills, seniority level,
key responsibilities, and signals about the company's culture and
working style. It also runs a brief web search to learn what the
company does and any relevant recent context.

If the URL is behind a login wall (common with LinkedIn), the agent
detects this and asks the user to paste the text directly rather
than failing silently.

### What the agent does next (also invisibly)

With both the candidate profile and the job analysis in hand, the
agent scores the match across five dimensions:

- **Technical skills** — which required and preferred skills match,
  which are missing, weighted by importance
- **Experience level** — candidate years versus job requirement,
  with a curve that rewards being slightly over-qualified
- **Seniority** — title level alignment between candidate and role
- **Domain fit** — how well the candidate's industry background
  transfers to this role's domain
- **Culture fit** — alignment between the candidate's apparent work
  style and the company's stated culture signals

The first three are calculated from the data directly. The last two
involve the agent using judgment. All five feed into a single overall
score. The agent also identifies which projects from the candidate's
background are most relevant to this specific job.

Critically, the agent also produces a **strategic angle** — a one-sentence
direction for the cover letter — and a **gap narrative** — an honest
assessment of any shortfalls and how to address them in writing.

### What the user sees

```
Block · Senior Software Engineer, Backend
──────────────────────────────────────────
Match score:  82 · Strong match

Matched skills:   Java, Spring Boot, AWS, Kafka, Kubernetes
Missing required: Go
Missing preferred: gRPC, Terraform

Breakdown:
  Technical skills  88
  Experience level  85
  Seniority match   90
  Domain fit        70   ← You're coming from outside fintech
  Culture fit       75

Strategy: Lead with distributed systems credibility at scale.
Address the fintech domain gap directly — reframe infrastructure
reliability as domain-agnostic. Cite Roadrunner as concrete evidence
of production Kafka/Kubernetes work.

Ready to generate your cover letter? (yes / adjust anything first)
```

### Key experience qualities

- The user sees a transparent, explainable score — not a black box
- The domain fit score of 70 is honest, not inflated
- The user understands exactly what the letter will need to do
  before it is written
- They can pause here and adjust anything before proceeding

---

## Phase 3: Output — The Cover Letter

### What the user sees

The agent generates a three-paragraph letter and presents it alongside
a brief metadata summary:

```
COVER LETTER — DRAFT 1
──────────────────────────────────────────

Dear Hiring Manager,

Building distributed systems that process millions of transactions
reliably is the problem space I've spent the last decade on — which
is why Block's infrastructure challenges caught my attention.

My most recent work includes leading the architecture of Roadrunner,
a distributed vehicle simulation platform handling real-time telemetry
from thousands of concurrent vehicles using Spring Boot, Kafka, and
Redis, deployed on Kubernetes via Helm on AWS EKS. The reliability
and throughput demands of that system map directly to what Block's
payment infrastructure requires.

The one area I'll address directly: my background is in distributed
systems rather than financial services specifically. In my experience,
infrastructure reliability is domain-agnostic — the same patterns that
handle high-throughput telemetry translate to payment processing at
scale. I'd welcome the chance to bring that depth to Block's team.

Stephen Tarter
stephen@tarterware.com · github.com/SteveTarter

──────────────────────────────────────────
279 words · Go gap addressed · Roadrunner cited · Draft 1

Suggestions:
  • "Make the tone more formal"
  • "Shorten to 200 words"
  • "Emphasize my Kubernetes depth more"
  • "I actually have some Go experience — add that"

Or type your own instruction.
```

### What the user notices

Several things about this letter are specific and deliberate:

- The opening references what Block builds, not just that the user
  wants to work there
- The second paragraph names Roadrunner explicitly and makes a
  specific technical claim about the system
- The third paragraph names the gap (fintech) and reframes it
  rather than ignoring it or apologizing for it
- The letter does not use phrases like "I am writing to apply"
  or "I am passionate about"
- The word count and a brief evidence audit appear below the letter
  so the user can see the agent followed its own constraints

### Refinement — the conversation continues

The user can now refine the letter in plain language. Each instruction
produces a targeted edit, not a full regeneration:

**Example 1 — Tone adjustment:**
```
User: Make it a bit less formal. Block is a startup culture.

Agent: [produces revised letter with slightly more direct register,
        preserving all evidence and structure]

Draft 2 · 271 words
```

**Example 2 — Emphasis change:**
```
User: The second paragraph feels weak. Can you lean harder into
      the Kubernetes/EKS work specifically?

Agent: [restructures paragraph two to lead with infrastructure
        deployment depth rather than the Roadrunner project framing]

Draft 3 · 283 words
```

**Example 3 — New information:**
```
User: Actually I did use Go for a small internal tool last year.
      It's not major experience but it's not zero.

Agent: Updates your profile with Go experience.
       Revises the gap paragraph to reflect this honestly.

Draft 4 · 276 words · Go gap reframed (limited experience noted)
```

**Example 4 — Starting over on a new job:**
```
User: Here's another posting I want to apply for:
      https://stripe.com/jobs/...

Agent: Analyzes the new posting against the same candidate profile.
       Produces a new fit score and a new cover letter.
       Previous letter is still available if the user asks for it.
```

### Key experience qualities

- The letter cites specific evidence by name — not generic claims
- The gap is addressed honestly, not hidden
- Refinement is incremental — the user is editing a draft, not
  starting over
- The agent's suggestions are contextual — they reflect what it
  knows about the current letter, not generic placeholders
- The user can switch to a new job at any time without losing
  their profile

---

## Batch Mode

When the user has several jobs to evaluate, they can provide multiple
postings at once:

```
User: I have a few jobs I want to compare. Can you run them all?

https://boards.greenhouse.io/confluent/jobs/111
https://stripe.com/jobs/222
https://block.xyz/careers/333
```

The agent processes all three against the same profile and returns a
ranked comparison:

```
BATCH RESULTS — 3 jobs analyzed
─────────────────────────────────────────────────────────
#  Company    Role                         Score  Label
─────────────────────────────────────────────────────────
1  Confluent  Principal Architect          91     Strong match
2  Block      Sr. Software Engineer        82     Strong match
3  Stripe     Staff Engineer               74     Good match
─────────────────────────────────────────────────────────

Cover letters generated for all three.
Type "show letter 1" to view any letter.
Type "refine letter 2" to iterate on a specific one.
```

The ranking is immediate and actionable — the user knows at a glance
where to invest their application effort. Each individual letter is
available on demand and follows the same refinement flow as the
single-job path.

---

## Profile Updates Mid-Session

The user can update their profile at any point:

```
User: I forgot to mention I have Terraform experience.
      I wrote all the infrastructure-as-code for my last project.

Agent: Got it — added Terraform to your infrastructure skills.
       If you'd like me to re-score any open jobs with this update,
       just say so.
```

Profile updates propagate forward — any new job analysis will use
the updated profile. Previously generated letters can be re-run if
the user asks.

---

## What the User Never Sees

Several things happen behind the scenes that the user is not aware of:

- The agent fingerprints the ATS system from the URL to apply
  the right parsing strategy before fetching
- Job postings are cached so the same URL is never fetched twice
- GitHub repositories are fetched and summarized silently during
  profile setup — the user sees only the count and the summaries
- The web search for company context runs during job analysis —
  the user sees only the result in the company summary
- The fit scorer runs three deterministic calculations and two LLM
  calls — the user sees only the final score breakdown
- The cover letter prompt has explicit negative constraints
  ("never use the word passionate") — the user sees only the output

This is by design. The complexity of the pipeline should be
invisible. The user experience is: give me your background, give
me a job, get a letter, refine it. Everything else is the system's
problem.

---

## Edge Cases the User May Encounter

**Login-gated job posting:**
```
Agent: This posting requires a login to view. Could you paste
       the job description text directly?
```
The user pastes, and the flow continues normally.

**Very short or vague job posting:**
```
Agent: This posting has limited detail — I could only find 3
       required skills and no preferred skills listed. The score
       and letter may be less targeted than usual. Proceed?
```

**Overqualified candidate:**
The fit score seniority dimension flags this with a note:
```
Seniority match: 70  ← You may be overqualified for this role.
                        The letter addresses this proactively.
```

**Reach application (score below 65):**
```
Match score: 58 · Reach

Missing required: Go, gRPC, eBPF
Domain fit: 45 (significant domain gap)

This is a reach application. A cover letter can still be generated,
but you should be aware of the gaps going in. Proceed?
```

The agent is honest rather than encouraging. A system that always
tells the user their application is a strong match is less useful
than one that gives them accurate signal.

---

## Summary of the User's Journey

| Step | User action | What they see |
|------|-------------|---------------|
| 1 | Start conversation | Prompt to provide resume |
| 2 | Upload resume or paste text | Extracted profile summary for confirmation |
| 3 | Confirm or correct profile | Profile locked in |
| 4 | Provide job URL or paste text | Fit score with dimension breakdown and strategy |
| 5 | Confirm or adjust | Cover letter, draft 1 |
| 6 | Refine in plain language | Updated draft |
| 7 | Repeat 6 until satisfied | Final letter ready to copy |
| 8 | Provide another job (optional) | New score and letter, same profile |
| 9 | Provide multiple jobs (optional) | Ranked batch comparison table |
