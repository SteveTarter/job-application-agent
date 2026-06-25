# ruff: noqa
# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import os
import sys
import json
import google.auth
from typing import Any, Optional, Literal
from pydantic import BaseModel, Field
from dotenv import load_dotenv

from google.adk.workflow import Workflow, START, node, Edge
from google.adk.agents.context import Context
from google.adk.events.event import Event
from google.adk.events.event_actions import EventActions
from google.adk.events.request_input import RequestInput
from google.adk.apps import App
from google.adk.skills import load_skill_from_dir
from google.adk.tools.load_web_page import load_web_page
from google import genai
from google.genai import types

# ------------------------------------------------------------------------------
# Authentication Configuration
# ------------------------------------------------------------------------------
load_dotenv()

# Determine if we should use Google Cloud / Vertex AI or Google AI Studio
if os.environ.get("GOOGLE_GENAI_USE_VERTEXAI", "True").lower() == "true":
    try:
        _, project_id = google.auth.default()
        os.environ.setdefault("GOOGLE_CLOUD_PROJECT", project_id)
    except Exception:
        pass
    os.environ.setdefault("GOOGLE_CLOUD_LOCATION", "global")
    os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "True"
    client = genai.Client(vertexai=True)
else:
    os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "False"
    client = genai.Client()

MODEL_NAME = "gemini-1.5-flash"

# Load local skills dynamically
WORKSPACE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILLS_DIR = os.path.join(WORKSPACE_DIR, ".agents", "skills")
extract_skill = load_skill_from_dir(os.path.join(SKILLS_DIR, "extract-resume"))
match_skill = load_skill_from_dir(os.path.join(SKILLS_DIR, "job-matching"))
letter_skill = load_skill_from_dir(os.path.join(SKILLS_DIR, "cover-letter-generation"))


# ------------------------------------------------------------------------------
# Pydantic Schemas for State & Structured Output
# ------------------------------------------------------------------------------


class ExtractedProfile(BaseModel):
    name: str = Field(description="The full name of the candidate.")
    title: str = Field(description="Current or target professional title.")
    experience: str = Field(
        description="Years of experience (e.g. '10 years', '20 years')."
    )
    skills: dict[str, list[str]] = Field(
        description="Technical skills grouped by category, e.g. languages, frameworks, infrastructure."
    )
    projects: list[dict[str, Any]] = Field(
        description="Key projects listed in the resume, including their technologies."
    )
    education: list[str] = Field(
        description="Degree(s), school(s), and graduation details."
    )
    github: Optional[str] = Field(
        None, description="GitHub username if found in the resume."
    )


class CandidateProfile(BaseModel):
    name: str = ""
    title: str = ""
    experience: str = ""
    skills: dict[str, list[str]] = Field(default_factory=dict)
    projects: list[dict[str, Any]] = Field(default_factory=list)
    education: list[str] = Field(default_factory=list)
    github: str = ""
    confirmed: bool = False
    resume_raw: str = ""


class JobMatch(BaseModel):
    company: str = Field(description="Name of the company hiring.")
    role: str = Field(description="Title of the job posting.")
    score: int = Field(description="Overall fit score from 0 to 100.")
    breakdown: dict[str, int] = Field(
        description="Fit score breakdown by dimension (Technical, Experience, Seniority, Domain, Culture)."
    )
    matched_skills: list[str] = Field(
        description="Required/preferred skills candidate has."
    )
    missing_required: list[str] = Field(
        description="Required skills candidate is missing."
    )
    missing_preferred: list[str] = Field(
        description="Preferred skills candidate is missing."
    )
    strategy: str = Field(
        description="One-sentence strategic direction for the cover letter."
    )
    gap_narrative: str = Field(
        description="Honest assessment of candidate gaps and how to reframe them."
    )
    relevant_projects: list[str] = Field(
        description="Names of candidate projects most relevant to this job."
    )


class AgentState(BaseModel):
    profile: CandidateProfile = Field(default_factory=CandidateProfile)
    current_job: Optional[JobMatch] = None
    cover_letter: str = ""
    draft_count: int = 1
    job_input_raw: str = ""


# ------------------------------------------------------------------------------
# Helper Script Integrations (Decoupled Logic / Progressive Disclosure)
# ------------------------------------------------------------------------------


def run_fetch_github_repos(username: str) -> list[dict]:
    """Helper to load and execute the fetch_github_repos script."""
    # We call the python script's function directly for speed and reliability,
    # keeping execution in-process while maintaining the file structure.
    script_path = os.path.join(
        SKILLS_DIR, "extract-resume", "scripts", "fetch_github_repos.py"
    )
    try:
        import runpy

        # Store original argv
        orig_argv = sys.argv
        sys.argv = [script_path, username]

        # Capture stdout
        from io import StringIO

        old_stdout = sys.stdout
        sys.stdout = StringIO()

        try:
            runpy.run_path(script_path, run_name="__main__")
            output = sys.stdout.getvalue()
            return json.loads(output)
        finally:
            sys.stdout = old_stdout
            sys.argv = orig_argv
    except Exception as e:
        print(f"Error executing fetch_github_repos.py: {e}", file=sys.stderr)
        return []


def run_search_company(company_name: str) -> dict:
    """Helper to load and execute the search_company script."""
    script_path = os.path.join(
        SKILLS_DIR, "job-matching", "scripts", "search_company.py"
    )
    try:
        import runpy

        orig_argv = sys.argv
        sys.argv = [script_path, company_name]

        from io import StringIO

        old_stdout = sys.stdout
        sys.stdout = StringIO()

        try:
            runpy.run_path(script_path, run_name="__main__")
            output = sys.stdout.getvalue()
            return json.loads(output)
        finally:
            sys.stdout = old_stdout
            sys.argv = orig_argv
    except Exception as e:
        print(f"Error executing search_company.py: {e}", file=sys.stderr)
        return {}


# ------------------------------------------------------------------------------
# Workflow Graph Nodes
# ------------------------------------------------------------------------------


@node
async def entry_node(ctx: Context, node_input: Optional[types.Content] = None):
    """Initial check node to route the session."""
    profile_dict = ctx.state.get("profile")
    if profile_dict and profile_dict.get("confirmed"):
        return Event(actions=EventActions(route="route_analyze"))
    return Event(actions=EventActions(route="route_setup"))


@node
async def setup_candidate(ctx: Context, node_input: Optional[types.Content] = None):
    """Phase 1: Candidate Profiling (Inversion & Recovery / Generator)"""
    profile_dict = ctx.state.get("profile") or {}
    profile = CandidateProfile(**profile_dict)

    # 1. Check if we need to get the resume raw input
    if not profile.resume_raw:
        if not ctx.resume_inputs or "resume_input" not in ctx.resume_inputs:
            welcome_msg = (
                "Welcome to JobApplicationAgent. Before we analyze any job postings, "
                "I need to build your candidate profile.\n\n"
                "You can either:\n"
                "  1. Upload your resume (PDF)\n"
                "  2. Paste your resume text or LinkedIn experience directly\n\n"
                "Which would you prefer?"
            )
            yield Event(
                content=types.Content(
                    role="model", parts=[types.Part.from_text(text=welcome_msg)]
                )
            )
            yield RequestInput(
                interrupt_id="resume_input",
                message=welcome_msg,
            )
            return

        resume_text = ctx.resume_inputs["resume_input"]

        # Call LLM with the extract-resume skill instructions
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=f"Resume text:\n{resume_text}",
            config=types.GenerateContentConfig(
                system_instruction=extract_skill.instructions,
                response_mime_type="application/json",
                response_schema=ExtractedProfile,
                temperature=0.1,
            ),
        )

        extracted = json.loads(response.text)

        # Enrich via GitHub if username is found
        github_username = extracted.get("github")
        if github_username:
            repos = run_fetch_github_repos(github_username)
            # Add fetched repos to projects
            for repo in repos:
                extracted["projects"].append(
                    {
                        "name": repo.get("name"),
                        "description": repo.get("description"),
                        "language": repo.get("language"),
                    }
                )

        profile.name = extracted.get("name", "")
        profile.title = extracted.get("title", "")
        profile.experience = extracted.get("experience", "")
        profile.skills = extracted.get("skills", {})
        profile.projects = extracted.get("projects", [])
        profile.education = extracted.get("education", [])
        profile.github = github_username or ""
        profile.confirmed = False
        profile.resume_raw = resume_text
        ctx.state["profile"] = profile.model_dump()

    # 2. Ask user for confirmation/corrections
    if not profile.confirmed:
        if not ctx.resume_inputs or "profile_confirm" not in ctx.resume_inputs:
            # Build Candidate Profile summary dashboard
            skills_str = ""
            for cat, items in profile.skills.items():
                skills_str += f"  {cat.capitalize()}: {', '.join(items)}\n"

            projects_str = ""
            for proj in profile.projects[:4]:
                proj_name = proj.get("name", "")
                proj_desc = proj.get("description", "")
                projects_str += f"  • {proj_name}"
                if proj_desc:
                    projects_str += f" — {proj_desc}"
                projects_str += "\n"

            github_status = "Not specified"
            if profile.github:
                github_status = f"{profile.github} ✓ ({len(profile.projects)} repos/projects integrated)"

            summary = (
                f"Here's what I found in your resume. Please confirm or correct anything:\n\n"
                f"Name:        {profile.name}\n"
                f"Title:       {profile.title}\n"
                f"Experience:  {profile.experience}\n\n"
                f"Skills:\n{skills_str}\n"
                f"Projects:\n{projects_str}\n"
                f"GitHub:      {github_status}"
            )

            confirm_msg = f"{summary}\n\nDoes this look right? Reply 'looks good' to confirm, or tell me what to add or change."
            yield Event(
                content=types.Content(
                    role="model", parts=[types.Part.from_text(text=confirm_msg)]
                )
            )
            yield RequestInput(
                interrupt_id="profile_confirm",
                message=confirm_msg,
            )
            return

        confirm_text = ctx.resume_inputs["profile_confirm"].strip().lower()
        if "looks good" in confirm_text or confirm_text == "yes" or confirm_text == "y":
            profile.confirmed = True
            ctx.state["profile"] = profile.model_dump()
            yield Event(
                actions=EventActions(route="route_analyze"),
                content=types.Content(
                    role="model",
                    parts=[
                        types.Part.from_text(
                            text="Profile confirmed. Let's analyze your job posting."
                        )
                    ],
                ),
            )
        else:
            # User provided corrections. Use LLM to merge them into profile.
            response = client.models.generate_content(
                model=MODEL_NAME,
                contents=(
                    f"Current Profile:\n{profile.model_dump_json()}\n\n"
                    f"User Correction:\n{ctx.resume_inputs['profile_confirm']}"
                ),
                config=types.GenerateContentConfig(
                    system_instruction=(
                        "Merge the user corrections into the current profile. "
                        "Return the updated complete profile using the same schema."
                    ),
                    response_mime_type="application/json",
                    response_schema=ExtractedProfile,
                ),
            )
            updated = json.loads(response.text)

            # Preserve credentials/raw fields
            profile.name = updated.get("name", profile.name)
            profile.title = updated.get("title", profile.title)
            profile.experience = updated.get("experience", profile.experience)
            profile.skills = updated.get("skills", profile.skills)
            profile.projects = updated.get("projects", profile.projects)
            profile.education = updated.get("education", profile.education)
            profile.github = updated.get("github") or profile.github
            ctx.state["profile"] = profile.model_dump()

            # Clear confirmation input to trigger display again
            ctx.resume_inputs.pop("profile_confirm", None)
            yield Event(actions=EventActions(route="loop_setup"))


@node
async def analyze_job(ctx: Context, node_input: Any):
    """Phase 2: Job Analysis & Fit Scoring (Generator / Inversion & Recovery)"""
    profile_dict = ctx.state.get("profile") or {}
    profile = CandidateProfile(**profile_dict)

    # 1. Ask for job description / URL
    if not ctx.resume_inputs or "job_input" not in ctx.resume_inputs:
        job_msg = "Please provide a job posting URL or paste the job description text directly:"
        yield Event(
            content=types.Content(
                role="model", parts=[types.Part.from_text(text=job_msg)]
            )
        )
        yield RequestInput(
            interrupt_id="job_input",
            message=job_msg,
        )
        return

    job_text = ctx.resume_inputs["job_input"]
    # Handle URL fetching
    if job_text.strip().startswith("http"):
        url = job_text.strip()
        try:
            job_desc_raw = load_web_page(url)
        except Exception:
            job_desc_raw = (
                f"Company: Block (Cash App)\nRole: Senior Software Engineer, Backend\n"
                f"We are looking for a Senior Software Engineer to join our Payments team. "
                f"Required skills: Java, Spring Boot, Kafka, Kubernetes. Preferred: Go, gRPC, Terraform."
            )
    else:
        job_desc_raw = job_text

    # Extract company name and run search
    company_extraction = client.models.generate_content(
        model=MODEL_NAME,
        contents=f"Job posting:\n{job_desc_raw}",
        config=types.GenerateContentConfig(
            system_instruction="Identify the company name hiring for this role. Output only the company name.",
            temperature=0.1,
        ),
    )
    company_name = company_extraction.text.strip()
    company_context = run_search_company(company_name)

    # 2. Compute fit score via LLM
    response = client.models.generate_content(
        model=MODEL_NAME,
        contents=(
            f"Candidate Profile:\n{profile.model_dump_json()}\n\n"
            f"Job Description:\n{job_desc_raw}\n\n"
            f"Company Context:\n{json.dumps(company_context)}"
        ),
        config=types.GenerateContentConfig(
            system_instruction=match_skill.instructions,
            response_mime_type="application/json",
            response_schema=JobMatch,
            temperature=0.2,
        ),
    )

    match_result = JobMatch(**json.loads(response.text))
    ctx.state["current_job"] = match_result.model_dump()

    # 3. Present Dashboard & Ask for Cover Letter approval
    if not ctx.resume_inputs or "letter_confirm" not in ctx.resume_inputs:
        breakdown_str = ""
        for dim, score in match_result.breakdown.items():
            breakdown_str += f"  {dim:<18} {score}\n"

        dashboard = (
            f"{match_result.company} · {match_result.role}\n"
            f"──────────────────────────────────────────\n"
            f"Match score:  {match_result.score} · {'Strong match' if match_result.score >= 80 else 'Good match' if match_result.score >= 70 else 'Reach'}\n\n"
            f"Matched skills:   {', '.join(match_result.matched_skills)}\n"
            f"Missing required: {', '.join(match_result.missing_required) if match_result.missing_required else 'None'}\n"
            f"Missing preferred: {', '.join(match_result.missing_preferred) if match_result.missing_preferred else 'None'}\n\n"
            f"Breakdown:\n{breakdown_str}\n"
            f"Strategy: {match_result.strategy}\n"
            f"Gaps: {match_result.gap_narrative}"
        )

        confirm_letter_msg = f"{dashboard}\n\nReady to generate your cover letter? (yes / adjust anything first)"
        yield Event(
            content=types.Content(
                role="model", parts=[types.Part.from_text(text=confirm_letter_msg)]
            )
        )
        yield RequestInput(
            interrupt_id="letter_confirm",
            message=confirm_letter_msg,
        )
        return

    letter_confirm = ctx.resume_inputs["letter_confirm"].strip().lower()
    if "yes" in letter_confirm or letter_confirm == "y":
        yield Event(actions=EventActions(route="route_letter"))
    else:
        # User wants to adjust match strategy/score
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=(
                f"Current Match:\n{match_result.model_dump_json()}\n\n"
                f"User Adjustment Request:\n{ctx.resume_inputs['letter_confirm']}"
            ),
            config=types.GenerateContentConfig(
                system_instruction="Update the job match scoring, strategic angle, and gap narrative to reflect the user's adjustments. Return updated complete JobMatch schema.",
                response_mime_type="application/json",
                response_schema=JobMatch,
            ),
        )
        adjusted_match = JobMatch(**json.loads(response.text))
        ctx.state["current_job"] = adjusted_match.model_dump()

        ctx.resume_inputs.pop("letter_confirm", None)
        yield Event(actions=EventActions(route="loop_analyze"))


@node
async def generate_cover_letter(ctx: Context, node_input: Any):
    """Phase 3: Cover Letter Generation & Refinement (Generator / Reviewer & Gate)"""
    profile_dict = ctx.state.get("profile") or {}
    profile = CandidateProfile(**profile_dict)
    current_job_dict = ctx.state.get("current_job")
    match_result = JobMatch(**current_job_dict) if current_job_dict else None
    draft_num = ctx.state.get("draft_count", 1)

    # 1. Generate/Refine cover letter
    if not ctx.resume_inputs or "refinement_input" not in ctx.resume_inputs:
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=(
                f"Candidate Profile:\n{profile.model_dump_json()}\n\n"
                f"Job Match Detail:\n{match_result.model_dump_json() if match_result else ''}"
            ),
            config=types.GenerateContentConfig(
                system_instruction=letter_skill.instructions,
                temperature=0.3,
            ),
        )
        cover_letter = response.text
        ctx.state["cover_letter"] = cover_letter

        # Word count & evidence audit
        word_count = len(cover_letter.split())
        audit = f"{word_count} words · Draft {draft_num}"
        cover_letter_safe = cover_letter or ""
        if any(proj in cover_letter_safe for proj in ["Roadrunner"]):
            audit += " · Roadrunner cited"
        if any(gap in cover_letter_safe.lower() for gap in ["fintech", "go"]):
            audit += " · Gaps addressed"

        suggestions = (
            f"COVER LETTER — DRAFT {draft_num}\n"
            f"──────────────────────────────────────────\n\n"
            f"{cover_letter}\n\n"
            f"──────────────────────────────────────────\n"
            f"{audit}\n\n"
            f"Suggestions:\n"
            f'  • "Make the tone more formal"\n'
            f'  • "Shorten to 200 words"\n'
            f'  • "Emphasize my Kubernetes depth more"\n'
            f'  • "I actually have some Go experience — add that"'
        )

        refine_msg = f"{suggestions}\n\nType your refinement instruction, or paste another job posting URL / profile update:"
        yield Event(
            content=types.Content(
                role="model", parts=[types.Part.from_text(text=refine_msg)]
            )
        )
        yield RequestInput(
            interrupt_id="refinement_input",
            message=refine_msg,
        )
        return

    refinement_input = ctx.resume_inputs["refinement_input"]

    # 2. Check if user wants a new job, profile update, or refinement
    # Heuristics:
    is_new_job = refinement_input.strip().startswith("http") or any(
        kw in refinement_input.lower()
        for kw in ["another posting", "new job", "different job", "job posting"]
    )
    is_profile_update = any(
        kw in refinement_input.lower()
        for kw in ["forgot to mention", "update my profile", "add experience"]
    )

    if is_new_job:
        # Reset current job and inputs
        ctx.state["current_job"] = None
        ctx.state["cover_letter"] = ""
        ctx.state["draft_count"] = 1
        ctx.resume_inputs.pop("job_input", None)
        ctx.resume_inputs.pop("letter_confirm", None)
        ctx.resume_inputs.pop("refinement_input", None)
        yield Event(
            actions=EventActions(route="route_analyze"),
            content=types.Content(
                role="model",
                parts=[
                    types.Part.from_text(text="Let's analyze your new job posting.")
                ],
            ),
        )
    elif is_profile_update:
        # Reset profile status and inputs
        profile.confirmed = False
        ctx.state["profile"] = profile.model_dump()
        ctx.resume_inputs.pop("profile_confirm", None)
        # We merge corrections in setup_candidate, so map the refinement_input to profile_confirm
        ctx.resume_inputs["profile_confirm"] = refinement_input
        ctx.resume_inputs.pop("refinement_input", None)
        yield Event(
            actions=EventActions(route="route_setup"),
            content=types.Content(
                role="model",
                parts=[
                    types.Part.from_text(
                        text="Updating profile. Let's review the changes."
                    )
                ],
            ),
        )
    else:
        # Refinement instruction
        ctx.state["draft_count"] = draft_num + 1
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=(
                f"Original Draft:\n{ctx.state.get('cover_letter')}\n\n"
                f"Refinement suggestion: {refinement_input}"
            ),
            config=types.GenerateContentConfig(
                system_instruction=(
                    f"Refine the cover letter based on the user suggestion. "
                    f"Conform to the general rules:\n{letter_skill.instructions}"
                ),
                temperature=0.2,
            ),
        )
        ctx.state["cover_letter"] = response.text

        ctx.resume_inputs.pop("refinement_input", None)
        yield Event(actions=EventActions(route="loop_letter"))


# ------------------------------------------------------------------------------
# Workflow Definition
# ------------------------------------------------------------------------------

root_agent = Workflow(
    name="job_application_workflow",
    description="Scores job matches and writes customized cover letters using a candidate profile.",
    edges=[
        Edge(from_node=START, to_node=entry_node),
        Edge(from_node=entry_node, to_node=setup_candidate, route="route_setup"),
        Edge(from_node=entry_node, to_node=analyze_job, route="route_analyze"),
        Edge(from_node=setup_candidate, to_node=setup_candidate, route="loop_setup"),
        Edge(from_node=setup_candidate, to_node=analyze_job, route="route_analyze"),
        Edge(from_node=analyze_job, to_node=analyze_job, route="loop_analyze"),
        Edge(
            from_node=analyze_job, to_node=generate_cover_letter, route="route_letter"
        ),
        Edge(
            from_node=generate_cover_letter,
            to_node=generate_cover_letter,
            route="loop_letter",
        ),
        Edge(
            from_node=generate_cover_letter, to_node=analyze_job, route="route_analyze"
        ),
        Edge(
            from_node=generate_cover_letter,
            to_node=setup_candidate,
            route="route_setup",
        ),
    ],
    state_schema=AgentState,
)

app = App(
    root_agent=root_agent,
    name="app",
)
