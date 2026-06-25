---
name: extract-resume
description: |
 Extracts structured details (Name, Title, Years of Experience, Skills, Projects, Education) from a raw resume, enriches it via public GitHub repo data if a username is found, and formats a candidate profile summary.
 Use when the user uploads a resume or requests a profile setup.
 Do NOT use for scoring job postings or writing cover letters.
version: 1.0.0
license: Apache-2.0
allowed-tools: run_skill_script
---

# Extract Resume Skill

## When to use
- The user provides their resume text, PDF path, or LinkedIn experience.
- The user wants to update their candidate profile.

## When NOT to use
- Assessing a candidate's fit for a job posting.
- Drafting or refining cover letters.

## Workflow
1. Parse the provided resume text.
2. Extract the following details:
   - Candidate Name
   - Current / Target Title
   - Years of Experience
   - Skills (categorized into: Languages, Frameworks, Infrastructure)
   - Projects (with names and technologies)
   - Education details
3. Check if a GitHub username is found in the text (e.g. `github.com/username` or just a username). If found, run the `scripts/fetch_github_repos.py` script passing the username to fetch their public repositories.
4. Format the final output as a neat candidate profile dashboard showing name, title, experience, skills, projects (with the fetched GitHub repos integrated), and a status line indicating how many GitHub repos were found.
5. Present the dashboard and prompt the user to confirm with "looks good" or provide plain language corrections.
