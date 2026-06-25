---
name: job-matching
description: |
 Parses a job posting URL or description, fetches target company context using web search, and calculates a match fit score (0-100) across 5 dimensions (Technical, Experience, Seniority, Domain, Culture).
 Use when the user provides a job posting URL or text description.
 Do NOT use for candidate profiling or cover letter drafting.
version: 1.0.0
license: Apache-2.0
allowed-tools: run_skill_script load_web_page
---

# Job Matching Skill

## When to use
- User provides a job description URL (Greenhouse, Lever, Stripe, Block, etc.) or pastes the text directly.
- User wants to re-score an existing job fit after updating their profile.

## When NOT to use
- Setting up the candidate's initial resume profile.
- Generating the actual cover letter.

## Workflow
1. Parse the provided job posting. If a URL is provided, call `load_web_page` to fetch and clean the description. If the URL is gated/inaccessible, ask the user to paste the description.
2. Identify the target company name. Run `scripts/search_company.py` passing the company name to retrieve background context and recent news.
3. Compute candidate match scores (0-100) across 5 key dimensions:
   - **Technical skills**: Match candidate languages, frameworks, and infrastructure against job requirements and preferred skills.
   - **Experience level**: Candidate years vs. required years.
   - **Seniority**: Title and responsibility alignment.
   - **Domain fit**: Industry transferability (e.g., fintech, developer tools).
   - **Culture fit**: Stated company culture signals vs. candidate profile.
4. Formulate the **strategic angle** (direction of cover letter) and the **gap narrative** (how to address any missing required skills/experience in writing).
5. Identify which projects from the candidate's profile are most relevant to cite.
6. Display a fit score dashboard summarizing findings and ask: "Ready to generate your cover letter? (yes / adjust anything first)"
