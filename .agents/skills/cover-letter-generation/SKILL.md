---
name: cover-letter-generation
description: |
 Generates a tailored three-paragraph cover letter based on candidate profile and job match, and applies plain-language refinements.
 Use when the user requests a cover letter draft or wants to refine it.
 Do NOT use for candidate profiling or job analysis.
version: 1.0.0
license: Apache-2.0
allowed-tools: ""
---

# Cover Letter Generation Skill

## When to use
- Generating the initial cover letter draft.
- Editing or adjusting the cover letter draft based on user suggestions (e.g. "make it more formal", "shorten it", "add details about Kubernetes").

## When NOT to use
- Parsing candidate resumes.
- Retrieving company details or calculating match scores.

## Workflow
1. Generate a tailored three-paragraph cover letter using candidate profile details and match results:
   - **Header**: Start with the current date followed by a professional salutation (e.g. "Dear Hiring Manager,").
   - **Paragraph 1**: Lead with the company's product/mission and candidate interest. Explain *why* you are interested in their specific engineering challenges. Do NOT say "I am writing to apply..." or "I am passionate about...".
   - **Paragraph 2**: Cite specific technical evidence by name (e.g. Roadrunner project) and highlight concrete technologies and scale challenges.
   - **Paragraph 3**: Directly address any domain or skill gaps (e.g. lack of fintech background) honestly and reframe it (e.g., that distributed systems reliability is domain-agnostic).
2. Conclude with candidate contact information and full links (GitHub:, Email:, LinkedIn:, etc.).
3. Count the word count. Provide a short metadata footer below the draft showing:
   - Word count (aim for 200-300 words).
   - Evidence audit (e.g. "Go gap addressed", "Roadrunner cited").
   - Draft number.
4. Present 3-4 contextual refinement suggestions based on the draft.
5. Apply incremental edits (re-drafting) when the user provides plain-language instructions.
