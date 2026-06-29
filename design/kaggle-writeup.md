# Job Application Agent — Project Writeup

> Target: under 2,500 words. Replace bracketed placeholders before submitting.

---

## Title

**JobAgent: A Skill-Based Agentic Pipeline for Tailored Job Applications**

## Subtitle

From job posting URL to evidence-backed cover letter in seconds, using ADK 2.0 Workflows, multimodal PDF processing, and a five-dimension fit scorer.

---

## The Problem

Job searching at a senior level is a research problem, not a writing problem. Before writing a single word, you need to understand what the company actually builds, whether your background genuinely maps to their requirements, which of your projects is most relevant as evidence, and how to frame any gaps honestly without underselling yourself.

Most candidates skip this analysis entirely and send generic cover letters. Most AI tools make this worse, not better. They produce fluent text that still fails to connect the candidate's specific experience to the specific job. The output reads like it was written for anyone, because it was.

The real opportunity for agents isn't writing, it's the reasoning that should happen before writing. Agents can analyze, score, plan, and only then draft. A single-prompt approach can't do this reliably; a graph-based pipeline can.

---

## Why Agents & Workflows

Three properties of this problem make it a natural fit for an ADK 2.0 Workflow architecture:

**Separation of concerns.** Extracting a job posting, scoring fit, and writing a cover letter are genuinely different tasks requiring different tools and different reasoning strategies. Cramming them into one prompt produces mediocre results on all three. Dedicated workflow nodes for each task produce better results on each.  

**Tool use & Multimodality.** The pipeline needs to fetch URLs, natively read PDF binaries, and search for company context. These are I/O operations that belong in dedicated helper scripts and API integrations, not just prompts. The workflow executes tools, validates the returned structured data, and passes it back to the agent's working state.  

**Iterative refinement.** A cover letter is rarely right on the first try. The conversational agent model, where the user types "update profile" or refines a draft, is a natural fit. Stateless single-prompt approaches can't support this without re-running the entire pipeline.

---

## Technical Architecture

[INSERT ARCHITECTURE DIAGRAM SCREENSHOT HERE]

The pipeline is centered around an ADK 2.0 `Workflow` graph (`root_agent`) managing the `AgentState`. The state flows through specialized nodes:  

**Entry Node** acts as the initial router, silently checking if a confirmed profile exists to direct the user to job analysis or candidate setup.  

**Setup Candidate Node** converts a pasted resume or an uploaded PDF into a structured Pydantic object. It utilizes `pypdf` to extract hyperlinked URLs (like LinkedIn or GitHub) from PDF annotations and feeds the raw binary directly into Gemini's multimodal API for comprehensive extraction.  

**Analyze Job Node** handles job descriptions and URL fetching via ADK's `load_web_page`. It evaluates the candidate against the role across five dimensions: Technical skills, Experience level, Seniority, Domain fit, and Culture fit. It calculates a fit score and produces a strategic `gap_narrative`.  

**Generate Cover Letter Node** generates a three-paragraph tailored letter using the job analyzer's strategic angle. It handles iterative refinement by accepting the current draft and user instructions to edit the existing text.

---

## Tools & Integrations

Three primary integrations serve the pipeline:

**Multimodal PDF Processing:** Uses local file path detection and `pypdf` to read PDF binary contents and extract candidate hyperlinks, processing the file directly via Gemini's multimodal capabilities.  

**GitHub & Web Fetching:** Helper scripts (`fetch_github_repos.py`) dynamically execute via `runpy` to fetch public repos, enriching the candidate profile. Job URLs are scraped seamlessly using the ADK's `load_web_page` tool.  

**Google Search Grounding:** Uses a two-step search fallback. If a company is unknown, the agent bypasses controlled generation and utilizes the native Gemini Google Search tool to retrieve real-time company background and news, summarizing it into a structured schema for the job analyzer.  

---

## Key Design Decisions

**Explicit Phrase Traversals.** Workflow routing relies on deterministic string matching. Typing `"job postings"` transitions the state from candidate setup to job analysis, and `"update profile"` safely routes the user back to the setup phase from anywhere in the flow.  

**Session Isolation for Batching.** Multi-job session isolation is managed by tracking a `job_index` within the `AgentState`. This prefixes all job-related interrupts to prevent frontend cache collisions, ensuring users can evaluate multiple jobs reliably in a single session.  

**Strict Pydantic Data Contracts.** Instead of passing loose dictionaries between nodes, all outputs return strictly typed Pydantic models (`ExtractedProfile`, `ExtractedJobMatch`, etc.). This enforces schema validation on the LLM outputs and prevents hallucinated keys.  

---

## Implementation Highlights

[INSERT ORCHESTRATOR ROUTING DIAGRAM SCREENSHOT HERE]
The migration to an ADK Workflow architecture enables a clean state machine. If a user asks to analyze a job, the `entry_node` natively routes them to `setup_candidate` first if their profile isn't populated.  

[INSERT COVER LETTER BEFORE/AFTER SCREENSHOT HERE]

The refinement loop demonstrates the conversational agent model perfectly. After the first draft, the user can provide adjustments. The workflow passes the user's instruction and the existing draft back into the loop, incrementing the `draft_count` and editing the existing text rather than regenerating from scratch.  

---

## Results

[INSERT EXAMPLE COVER LETTER OUTPUT HERE — redact personal details as needed]
The system produces cover letters that:
- Cite specific GitHub projects by name with technical claims.
- Address gaps honestly using the fit scorer's strategic framing.
- Mirror the company's own culture language.
- Track word counts and provide an evidence audit explicitly alongside the draft. 

---

## What I Learned

**Multimodal inputs beat pure text parsing.** Passing the raw PDF bytes alongside extracted annotation links resulted in far richer candidate profiles than traditional text scraping.  

**Search Grounding as a fallback.** Utilizing Google Search natively as a tool parameter dramatically improved the agent's ability to deduce the culture and specific industry context for obscure or newly founded startups.  

**State Isolation is critical.** Adding a `job_index` tracking variable was necessary to prevent frontend client-side cache collisions when users wanted to evaluate multiple jobs in a single sitting.  

---

## Repository and Demo

-   **GitHub:** [REPO URL]
-   **Video:** [YOUTUBE URL]
-   **Track:** Concierge Agents 

Setup instructions are in the README. The system requires a `GEMINI_API_KEY` and uses `uv` for lightning-fast dependency management.  

---

## Acknowledgments

Built using Google ADK 2.0 and submitted as a capstone project for Kaggle's 5-Day AI Agents: Intensive Vibe Coding Course with Google.
