# job-application-agent

A workflow-based agentic pipeline that parses multimodal resumes, analyzes job postings, scores candidate fit across five dimensions, and generates tailored cover letters.

Built with Python and Google ADK 2.0 for the Kaggle AI Agents Hackathon (Concierge Agents track).

---

## Demo

[INSERT DEMO GIF OR SCREENSHOT HERE]

---

## How It Works

```
User Input → ADK Workflow (Maintains AgentState)
                    │
                    ├── 1. Setup Node         → Validates CandidateProfile (via Multimodal PDF)
                    ├── 2. Analysis Node      → Validates JobMatch & Search Grounding
                    └── 3. Cover Letter Node  → Generates Letter & Iterative Refinement
```

One State Graph, Three Nodes, Deep Integrations:  

Component               | Type     | Responsibility
------------------------|----------|---------------
`app/agent.py`          | Workflow | Edge routing · explicit phrase traversals · state management
`setup_candidate`       | Node     | Multimodal PDF resume extraction · pypdf link parsing
`analyze_job`           | Node     | URL fetching · Google Search Grounding · 5-dimension scoring
`generate_cover_letter` | Node     | Letter generation · refinement loop · evidence auditing

Tool / Helper           | Purpose
------------------------|--------
`load_web_page`         | ADK tool to fetch and clean job posting URLs
`fetch_github_repos.py` | Runpy script to pull repo evidence for cover letter citations
`google_search`         | Gemini grounding fallback for company context

## Quickstart

### Prerequisites

* Python 3.11+
* `uv package manager`
* Google AI API key (or Google Cloud / Vertex AI credentials)

### Setup

```bash
# Clone the repo
git clone https://github.com/[USERNAME]/job-application-agent
cd job-application-agent

# Install dependencies using uv
uv sync --frozen

# Configure environment
cp .env.example .env
# Edit .env and add your GEMINI_API_KEY
```

### Run

```bash
# Launch the local development environment using agents-cli
agents-cli playground
```

### Test

```bash
# Run unit and integration tests
uv run pytest tests/unit tests/integration
```

---

## Project Structure

```
job-application-agent/
├── app/
│   ├── agent.py         # ADK workflow and edge definitions
│   ├── models.py        # Pydantic state and schema contracts
│   ├── helpers.py       # Runpy execution for local skills
│   └── nodes/           # Workflow nodes (setup, analysis, letter)
├── .agents/skills/      # Prompt instructions for LLM tasks
└── tests/               # Pytest integration and unit tests
```
See GEMINI.md for AI coding tool instructions and build conventions.

---

## Architecture Decisions

**ADK Workflow Orchestration.** Instead of a rigid single-prompt agent, a directed graph natively manages the `AgentState.` It dynamically traverses between setup, analysis, and generation nodes based on deterministic phrases like `"update profile"` or `"job postings"`.  
**Strict Pydantic Data Contracts.** Nodes never pass raw dictionaries. All outputs from LLM calls are rigorously validated using Pydantic models (`ExtractedProfile`, `ExtractedJobMatch`) to prevent LLM hallucinations and enforce strict schema adherence.  

**Multimodal PDF Parsing.** Instead of relying solely on text scrapers, the `setup_candidate` node uses `pypdf` to extract annotation hyperlinks, then passes the raw PDF bytes to Gemini for superior contextual extraction.  

**Search Grounding Fallback.** The job analyzer uses the `google_search` tool natively as a fallback to dynamically research company background and news if local scripts fail.  

**Session Isolation.** The state tracks a `job_index` parameter to prefix interrupt IDs. This isolates multi-job analysis sessions and prevents UI cache collisions when evaluating multiple roles.

---

## Environment Variables

Variable                    | Required | Description
----------------------------|----------|------------
`GEMINI_API_KEY`            | Yes\*    | Google AI API key (\*If not using Vertex AI)
`GOOGLE_GENAI_USE_VERTEXAI` | No       | Set to True to use Vertex AI application-default credentials
`GOOGLE_CLOUD_PROJECT`      | No       | Target GCP project ID

---

## Evaluation Criteria

Criterion | Where
----------|------
Multi-agent system (ADK) | `app/agent.py` and `app/nodes/` — State-driven Workflow Graph
MCP tools / Integrations | `app/helpers.py` — `load_web_page`, `pypdf`, and Search Grounding
Security features | `.env` pattern · strong Pydantic validation · no keys in code
Deployability | Dockerfile and `pyproject.toml` included
Agent skills / CLI | Defined in `agents-cli-manifest.yaml` and `GEMINI.md`

---

## License

MIT
