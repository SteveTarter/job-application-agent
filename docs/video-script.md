# Video Script Draft

## Format

* Target runtime: 4:30
* Hard limit: 5:00
* Record screen + voiceover. No camera required.
* Sections marked [SCREEN] describe what should be visible.
* Keep each section to its target time — the demo section is the most important.

---

## Section 1: Problem Statement (0:00 - 0:45)

[SCREEN: Slide or plain text — "The problem with job searching"]  

"Searching for a senior engineering role means doing real research before writing a single word. You need to understand what the company actually builds, whether your background maps to their requirements, which of your projects is most relevant as evidence, and how to frame any gaps honestly.  

Most AI tools skip all of this. They produce fluent text that could have been written for any candidate applying to any job. The output sounds good and says nothing specific.  

The fix isn't better writing — it's better reasoning before writing. And that's exactly what an ADK Workflow pipeline can do."

---

## Section 2: Why Agents & Workflows (0:45 – 1:30)

[SCREEN: Architecture diagram showing AgentState and the Workflow Nodes]  

"I built JobAgent using Google ADK 2.0. The pipeline centers on a directed Workflow graph that manages a strict agent state.  

The state flows through specific nodes: Candidate Setup, Job Analysis, and Letter Generation. The setup node uses Gemini's multimodal API to read your resume PDF directly. The job analyzer turns a posting URL into structured data and uses Google Search Grounding to research the company. The fit scorer assesses your candidacy across five dimensions to generate a strategy. And the cover letter node uses that strategy to write something actually tailored to you."

---

## Section 3: Antigravity & ADK (1:30 – 2:00)

[SCREEN: IDE with app/agent.py and app/models.py Pydantic models visible]  

"I built this using ADK. Here you can see the Workflow definition and its routing logic. Notice how we use strict Pydantic schemas for the data contracts. When a node finishes an LLM call, it returns a strongly typed, validated model back to the agent's AgentState memory, preventing LLM hallucinations.  

By separating the workflow into distinct nodes, we can deterministically route the user using explicit phrases like 'job postings' or 'update profile'."  

---

## Section 4: Live Demo — Single Job (2:00 – 3:30)

[SCREEN: Terminal running 'docker compose up' then transitioning to the React web UI]  

"Let me show it running. The entire application—both the Python ADK backend and Next.js frontend—spins up in a single command using Docker Compose. Once it's ready, we open the web interface in the browser. First, the agent asks for my resume. I'll upload a PDF.  

[SCREEN: Upload PDF in web UI]  

"The setup node uses pypdf to extract my GitHub links from the file's annotations, then passes the binary to Gemini to build a candidate profile. Now, I'll paste in a job posting for a Backend role."  

[SCREEN: Paste job posting URL or text]  

"The Analyze Job node fetches the posting. If the company is unknown, it triggers a live Google Search Grounding fallback to grab recent news and context.  

[SCREEN: Fit score output with dimension breakdown]  

Now I see the fit score. Technical skills scored 88, experience level 85, seniority 90. Overall score: 82, which the system labels a Strong match. The scorer also generated a strategic gap narrative.  

[SCREEN: Cover letter appearing]  

The Generate Cover Letter node takes over. Notice the opening — it connects my background directly to what this company builds. It even outputs an evidence audit, counting the words and noting which projects it cited.  

[SCREEN: Refinement turn]  

Now watch what happens when I say 'make the tone less formal'. The workflow loops back into the letter node, incrementing the draft count and editing the text while preserving the evidence."

---

## Section 5: Batching & Session Isolation (3:30 – 4:15)

[SCREEN: Workflow handling multiple jobs]  

"When I want to look at another job, I just type 'job postings'. The workflow routes me back to the analyzer.  

Behind the scenes, the agent's state tracks a job_index. This isolates each job session to prevent cache collisions in the UI. I can evaluate multiple jobs against the same stored candidate profile, producing genuinely different strategic angles and letters without having to re-upload my resume."  

---

## Section 6: Close (4:15 – 4:30)

[SCREEN: GitHub repo README]  

"The full code is at https://github.com/SteveTarter/job-application-agent. The README covers local setup, the multi-agent architecture, and how to run the entire stack with Docker Compose.

Built for Kaggle's AI Agents hackathon. Thanks for watching."
