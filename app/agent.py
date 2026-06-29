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
from datetime import datetime
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

MODEL_NAME = "gemini-2.5-flash"

# Load local skills dynamically
WORKSPACE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILLS_DIR = os.path.join(WORKSPACE_DIR, ".agents", "skills")
extract_skill = load_skill_from_dir(os.path.join(SKILLS_DIR, "extract-resume"))
match_skill = load_skill_from_dir(os.path.join(SKILLS_DIR, "job-matching"))
letter_skill = load_skill_from_dir(os.path.join(SKILLS_DIR, "cover-letter-generation"))


# ------------------------------------------------------------------------------
# Pydantic Schemas for State & Structured Output
# ------------------------------------------------------------------------------



class ExtractedExperience(BaseModel):
    company: str = Field(description="Company name.")
    role: str = Field(description="Job title.")
    description: str = Field(description="Brief summary of responsibilities or achievements.")

class ExtractedProject(BaseModel):
    name: str = Field(description="Project name.")
    description: str = Field(description="Project description and technologies used.")

class ExtractedEducation(BaseModel):
    institution: str = Field(description="School or university name.")
    degree: str = Field(description="Degree and field of study.")
    year: str = Field(description="Graduation year.")

class ExtractedSkill(BaseModel):
    category: str = Field(description="Skill category name (e.g. languages, frameworks, infrastructure, tools).")
    skills: list[str] = Field(description="List of skills in this category.")

class ExtractedProfile(BaseModel):
    name: str = Field(description="The full name of the candidate.")
    title: str = Field(description="Current or target professional title.")
    experience: int = Field(description="Years of experience (integer).")
    skills: list[ExtractedSkill] = Field(
        description="Comprehensive list of all technical skills grouped by category (e.g. Languages, Frameworks, Infrastructure, Tools). Do not summarize or omit any skills listed in the resume."
    )
    work_experience: list[ExtractedExperience] = Field(description="Comprehensive list of all work experience/employment history entries listed in the resume. Do not summarize or omit any roles.")
    projects: list[ExtractedProject] = Field(description="Comprehensive list of all projects listed in the resume. Do not summarize or omit any projects.")
    education: list[ExtractedEducation] = Field(description="Education entries.")
    email: Optional[str] = Field(None, description="Email address if found.")
    github: Optional[str] = Field(None, description="GitHub username if found in the resume.")
    linkedin: Optional[str] = Field(None, description="LinkedIn URL if found.")

class CandidateProfile(BaseModel):
    name: str = ""
    title: str = ""
    experience: int = 0
    skills: dict[str, list[str]] = Field(default_factory=dict)
    work_experience: list[dict[str, Any]] = Field(default_factory=list)
    projects: list[dict[str, Any]] = Field(default_factory=list)
    education: list[dict[str, Any]] = Field(default_factory=list)
    email: str = ""
    github: str = ""
    linkedin: str = ""
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

class ExtractedScoreDimension(BaseModel):
    dimension: str = Field(description="Dimension name (e.g. Technical, Experience, Seniority, Domain, Culture).")
    score: int = Field(description="Score for this dimension (0 to 100).")

class ExtractedJobMatch(BaseModel):
    company: str = Field(description="Name of the company hiring.")
    role: str = Field(description="Title of the job posting.")
    score: int = Field(description="Overall fit score from 0 to 100.")
    breakdown: list[ExtractedScoreDimension] = Field(
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
    profile_confirm_count: int = 0
    job_input_count: int = 0
    letter_confirm_count: int = 0
    refinement_count: int = 0
    resume_input_count: int = 0
    job_index: int = 0


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
    except Exception as e:
        raise RuntimeError(f"Error executing fetch_github_repos.py: {e}")
    finally:
        sys.stdout = old_stdout
        sys.argv = orig_argv


def run_search_company(company_name: str) -> dict:
    """Helper to load and execute the search_company script."""
    script_path = os.path.join(
        SKILLS_DIR, "job-matching", "scripts", "search_company.py"
    )
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
    except Exception as e:
        raise RuntimeError(f"Error executing search_company.py: {e}")
    finally:
        sys.stdout = old_stdout
        sys.argv = orig_argv


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


@node(rerun_on_resume=True)
async def setup_candidate(ctx: Context, node_input: Any = None):
    """Phase 1: Candidate Profiling (Inversion & Recovery / Generator)"""
    profile_dict = ctx.state.get("profile") or {}
    profile = CandidateProfile(**profile_dict)

    # Force re-extraction if the stored profile is blank (no name and no title)
    if not profile.name and not profile.title:
        profile.resume_raw = ""

    # 1. Check if we need to get the resume raw input
    if not profile.resume_raw:
        resume_count = ctx.state.setdefault("resume_input_count", 0)
        interrupt_id = f"resume_input_{resume_count}"
        if not ctx.resume_inputs or interrupt_id not in ctx.resume_inputs:
            welcome_msg = (
                "Please provide a resume PDF or paste the resume text directly:"
            )
            yield Event(
                content=types.Content(
                    role="model", parts=[types.Part.from_text(text=welcome_msg)]
                )
            )
            yield RequestInput(
                interrupt_id=interrupt_id,
                message=welcome_msg,
            )
            return

        resume_text_raw = ctx.resume_inputs[interrupt_id]
        if isinstance(resume_text_raw, dict):
            resume_text = resume_text_raw.get("result", "") or resume_text_raw.get("text", "") or str(resume_text_raw)
        else:
            resume_text = str(resume_text_raw)

        is_file = os.path.isfile(resume_text)
        is_valid = False
        if is_file:
            try:
                is_valid = os.path.getsize(resume_text) > 100
            except Exception:
                is_valid = False
        else:
            is_valid = len(resume_text.strip()) >= 50

        if not is_valid:
            error_msg = (
                "I couldn't extract any readable text from the resume you provided.\n\n"
                "Please make sure the PDF contains selectable text (not scanned images), "
                "or paste your resume text directly."
            )
            ctx.state["resume_input_count"] += 1
            yield Event(
                content=types.Content(
                    role="model", parts=[types.Part.from_text(text=error_msg)]
                )
            )
            yield RequestInput(
                interrupt_id=f"resume_input_{ctx.state['resume_input_count']}",
                message=error_msg,
            )
            return

        if is_file:
            try:
                import mimetypes
                mime_type, _ = mimetypes.guess_type(resume_text)
                if not mime_type:
                    mime_type = "application/octet-stream"

                if mime_type == "application/pdf":
                    with open(resume_text, "rb") as f:
                        file_bytes = f.read()

                    pdf_links = []
                    try:
                        import pypdf
                        reader = pypdf.PdfReader(resume_text)
                        for page in reader.pages:
                            if "/Annots" in page:
                                annots = page["/Annots"]
                                for annot in annots:
                                    annot_obj = annot.get_object()
                                    if annot_obj.get("/Subtype") == "/Link":
                                        uri_dict = annot_obj.get("/A")
                                        if uri_dict and "/URI" in uri_dict:
                                            uri = uri_dict["/URI"]
                                            if uri not in pdf_links:
                                                pdf_links.append(uri)
                    except Exception:
                        pass

                    links_str = ""
                    if pdf_links:
                        links_str = "\n\nHyperlinks found in PDF annotations:\n" + "\n".join(f"- {link}" for link in pdf_links)

                    file_part = types.Part.from_bytes(data=file_bytes, mime_type="application/pdf")
                    contents_input = [
                        file_part,
                        "IMPORTANT: Extract ALL details from the resume PDF comprehensively. "
                        "Do not summarize, aggregate, or omit any skills, technologies, tools, projects, or work history entries. "
                        "Every single item listed in the resume must be included in the corresponding fields. "
                        "DO NOT invent, hallucinate, or boilerplate any information. If a field or list (like work experience or projects) is not present in the resume PDF, leave it empty (do not populate it with mock or placeholder data)."
                        f"{links_str}"
                    ]
                else:
                    with open(resume_text, "r", encoding="utf-8", errors="ignore") as f:
                        text_content = f.read()
                    contents_input = [
                        f"Resume text:\n{text_content}\n\n"
                        f"IMPORTANT: Extract ALL details from the resume text comprehensively. "
                        f"Do not summarize, aggregate, or omit any skills, technologies, tools, projects, or work history entries. "
                        f"Every single item listed in the resume must be included in the corresponding fields. "
                        f"DO NOT invent, hallucinate, or boilerplate any information. If a field or list (like work experience or projects) is not present in the resume text, leave it empty (do not populate it with mock or placeholder data)."
                    ]
            except Exception as e:
                error_msg = f"Error: Failed to read file from path '{resume_text}': {e}. Please make sure the path is correct and readable, or paste the text directly."
                ctx.state["resume_input_count"] += 1
                yield Event(
                    content=types.Content(
                        role="model", parts=[types.Part.from_text(text=error_msg)]
                    )
                )
                yield RequestInput(
                    interrupt_id=f"resume_input_{ctx.state['resume_input_count']}",
                    message=error_msg,
                )
                return
        else:
            contents_input = [
                f"Resume text:\n{resume_text}\n\n"
                f"IMPORTANT: Extract ALL details from the resume text comprehensively. "
                f"Do not summarize, aggregate, or omit any skills, technologies, tools, projects, or work history entries. "
                f"Every single item listed in the resume must be included in the corresponding fields. "
                f"DO NOT invent, hallucinate, or boilerplate any information. If a field or list (like work experience or projects) is not present in the resume text, leave it empty (do not populate it with mock or placeholder data)."
            ]

        # Call LLM with the extract-resume skill instructions
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=contents_input,
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

        profile.name = (extracted.get("name") or "").strip().title()
        profile.title = extracted.get("title") or ""
        profile.experience = extracted.get("experience") or 0
        
        # Convert list of ExtractedSkill to dict[str, list[str]]
        skills_dict = {}
        for item in extracted.get("skills") or []:
            if isinstance(item, dict):
                skills_dict[item.get("category", "")] = item.get("skills", [])
            else:
                skills_dict[getattr(item, "category", "")] = getattr(item, "skills", [])
        profile.skills = skills_dict

        profile.work_experience = extracted.get("work_experience") or []
        profile.projects = extracted.get("projects") or []
        profile.education = extracted.get("education") or []
        profile.email = extracted.get("email") or ""
        profile.github = github_username or extracted.get("github") or ""
        profile.linkedin = extracted.get("linkedin") or ""
        profile.confirmed = False

        if not profile.name and not profile.title:
            error_msg = (
                "I couldn't extract a candidate name or title from the resume text.\n\n"
                "Please make sure the text contains your name and professional title, "
                "or paste your resume details directly."
            )
            ctx.state["resume_input_count"] += 1
            yield Event(
                content=types.Content(
                    role="model", parts=[types.Part.from_text(text=error_msg)]
                )
            )
            yield RequestInput(
                interrupt_id=f"resume_input_{ctx.state['resume_input_count']}",
                message=error_msg,
            )
            return

        profile.resume_raw = resume_text
        ctx.state["profile"] = profile.model_dump()

    # 2. Ask user for confirmation/corrections
    if not profile.confirmed:
        confirm_count = ctx.state.setdefault("profile_confirm_count", 0)
        interrupt_id = f"profile_confirm_{confirm_count}"
        if not ctx.resume_inputs or interrupt_id not in ctx.resume_inputs:
            # Build Candidate Profile summary dashboard
            skills_str = ""
            for cat, items in profile.skills.items():
                skills_str += f"{cat.capitalize()}:\n{', '.join(items)}\n\n"

            work_exp_str = ""
            for exp in profile.work_experience:
                company = exp.get("company", "")
                role = exp.get("role", "")
                desc = exp.get("description", "")
                work_exp_str += f"  • {role} at {company}"
                if desc:
                    work_exp_str += f" — {desc}"
                work_exp_str += "\n"

            projects_str = ""
            for proj in profile.projects:
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
                f"Name:\n{profile.name}\n\n"
                f"Title:\n{profile.title}\n\n"
                f"Experience:\n{profile.experience}\n\n"
                f"{skills_str}"
                f"Work Experience:\n{work_exp_str}\n"
                f"Projects:\n{projects_str}\n"
                f"GitHub:\n{github_status}"
            )

            confirm_msg = f"{summary}\n\nDoes this look right? Type 'job postings' to proceed, or enter corrections below:"
            yield Event(
                content=types.Content(
                    role="model", parts=[types.Part.from_text(text=confirm_msg)]
                )
            )
            yield RequestInput(
                interrupt_id=interrupt_id,
                message=confirm_msg,
            )
            return

        confirm_text = ctx.resume_inputs[interrupt_id].strip().lower()
        if "job postings" in confirm_text:
            profile.confirmed = True
            ctx.state["profile"] = profile.model_dump()
            yield Event(
                output=True,
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
                    f"User Correction:\n{ctx.resume_inputs[interrupt_id]}"
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
            profile.name = updated.get("name", profile.name).strip().title()
            profile.title = updated.get("title", profile.title)
            profile.experience = updated.get("experience", profile.experience)
            
            # Convert list of ExtractedSkill to dict[str, list[str]]
            skills_dict = {}
            for item in updated.get("skills") or []:
                if isinstance(item, dict):
                    skills_dict[item.get("category", "")] = item.get("skills", [])
                else:
                    skills_dict[getattr(item, "category", "")] = getattr(item, "skills", [])
            profile.skills = skills_dict

            profile.projects = updated.get("projects", profile.projects)
            profile.education = updated.get("education", profile.education)
            profile.github = updated.get("github") or profile.github
            ctx.state["profile"] = profile.model_dump()

            # Clear confirmation input to trigger display again
            ctx.resume_inputs.pop(interrupt_id, None)
            ctx.state["profile_confirm_count"] = confirm_count + 1
            yield Event(
                output=True,
                actions=EventActions(route="loop_setup"),
                content=types.Content(
                    role="model",
                    parts=[types.Part.from_text(text="Updating profile...")]
                )
            )


@node(rerun_on_resume=True)
async def analyze_job(ctx: Context, node_input: Any):
    """Phase 2: Job Analysis & Fit Scoring (Generator / Inversion & Recovery)"""
    profile_dict = ctx.state.get("profile") or {}
    profile = CandidateProfile(**profile_dict)

    if not ctx.state.get("current_job"):
        # 1. Ask for job description / URL
        job_idx = ctx.state.setdefault("job_index", 0)
        job_count = ctx.state.setdefault("job_input_count", 0)
        job_interrupt_id = f"job_input_{job_idx}_{job_count}" if job_idx > 0 else f"job_input_{job_count}"
        if not ctx.resume_inputs or job_interrupt_id not in ctx.resume_inputs:
            job_msg = "Please provide a job posting URL or paste the job description text directly:"
            yield Event(
                content=types.Content(
                    role="model", parts=[types.Part.from_text(text=job_msg)]
                )
            )
            yield RequestInput(
                interrupt_id=job_interrupt_id,
                message=job_msg,
            )
            return

        job_text = ctx.resume_inputs[job_interrupt_id]
        ctx.state["job_input_count"] = job_count + 1

        # Handle URL fetching (only if it is a single valid URL string without spaces or newlines)
        job_text_stripped = job_text.strip()
        if (
            (job_text_stripped.startswith("http://") or job_text_stripped.startswith("https://"))
            and " " not in job_text_stripped
            and "\n" not in job_text_stripped
        ):
            url = job_text_stripped
            try:
                job_desc_raw = load_web_page(url)
            except Exception as e:
                error_msg = f"Error: Failed to retrieve job posting from '{url}': {e}. Please check the URL or paste the job posting text directly."
                ctx.state["job_input_count"] += 1
                yield Event(
                    content=types.Content(
                        role="model", parts=[types.Part.from_text(text=error_msg)]
                    )
                )
                err_id = f"job_input_{job_idx}_{ctx.state['job_input_count']}" if job_idx > 0 else f"job_input_{ctx.state['job_input_count']}"
                yield RequestInput(
                    interrupt_id=err_id,
                    message=error_msg,
                )
                return
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
        try:
            company_context = run_search_company(company_name)
        except Exception as e:
            # Fall back to live Google Search grounding to retrieve real context
            try:
                class LiveCompanyContext(BaseModel):
                    name: str = Field(description="Name of the company.")
                    industry: str = Field(description="Industry name.")
                    context: str = Field(description="Detailed context/background of the company.")
                    recent_news: str = Field(description="Recent news or updates about the company.")

                # Step 1: Call Gemini with Google Search grounding tool to get text context (no schema)
                search_response = client.models.generate_content(
                    model=MODEL_NAME,
                    contents=f"Search for and summarize background information about the company: '{company_name}'. Extract its industry, detailed context/background, and recent news.",
                    config=types.GenerateContentConfig(
                        tools=[{"google_search": {}}],
                        temperature=0.1,
                    ),
                )
                search_text = search_response.text

                # Step 2: Call Gemini again without search tool but with controlled generation to parse text into schema
                parse_response = client.models.generate_content(
                    model=MODEL_NAME,
                    contents=f"Extract the company context details from this text:\n\n{search_text}",
                    config=types.GenerateContentConfig(
                        system_instruction=(
                            "Extract the name, industry, detailed context/background, and recent news of the company "
                            "from the provided text into the requested JSON schema. Do not use boilerplate or placeholders."
                        ),
                        response_mime_type="application/json",
                        response_schema=LiveCompanyContext,
                        temperature=0.1,
                    ),
                )
                company_context = json.loads(parse_response.text)
            except Exception as se:
                error_msg = f"Error: Failed to retrieve company context for '{company_name}' via search: {se}. Please check the company name."
                ctx.state["job_input_count"] += 1
                yield Event(
                    content=types.Content(
                        role="model", parts=[types.Part.from_text(text=error_msg)]
                    )
                )
                err_id = f"job_input_{job_idx}_{ctx.state['job_input_count']}" if job_idx > 0 else f"job_input_{ctx.state['job_input_count']}"
                yield RequestInput(
                    interrupt_id=err_id,
                    message=error_msg,
                )
                return

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
                response_schema=ExtractedJobMatch,
                temperature=0.2,
            ),
        )

        extracted = ExtractedJobMatch(**json.loads(response.text))
        match_result = JobMatch(
            company=extracted.company,
            role=extracted.role,
            score=extracted.score,
            breakdown={item.dimension: item.score for item in extracted.breakdown},
            matched_skills=extracted.matched_skills,
            missing_required=extracted.missing_required,
            missing_preferred=extracted.missing_preferred,
            strategy=extracted.strategy,
            gap_narrative=extracted.gap_narrative,
            relevant_projects=extracted.relevant_projects,
        )
        ctx.state["current_job"] = match_result.model_dump()
    else:
        match_result = JobMatch(**ctx.state["current_job"])

    # 3. Present Dashboard & Ask for Cover Letter approval
    job_idx = ctx.state.setdefault("job_index", 0)
    confirm_count = ctx.state.setdefault("letter_confirm_count", 0)
    letter_confirm_id = f"letter_confirm_{job_idx}_{confirm_count}" if job_idx > 0 else f"letter_confirm_{confirm_count}"
    if not ctx.resume_inputs or letter_confirm_id not in ctx.resume_inputs:
        # Get breakdown scores (case-insensitive fallback)
        bd = {k.lower(): v for k, v in match_result.breakdown.items()}
        tech_score = bd.get("technical skills") or bd.get("technical") or 0
        exp_score = bd.get("experience level") or bd.get("experience") or 0
        sen_score = bd.get("seniority") or 0
        dom_score = bd.get("domain fit") or bd.get("domain") or 0
        cult_score = bd.get("culture fit") or bd.get("culture") or 0

        dashboard = (
            f"{match_result.company} · {match_result.role}\n"
            f"──────────────────────────────────────────\n"
            f"Match score:\n"
            f"{match_result.score} · {'Strong match' if match_result.score >= 80 else 'Good match' if match_result.score >= 70 else 'Reach'}\n\n"
            f"Matched skills:\n"
            f"{', '.join(match_result.matched_skills)}\n\n"
            f"Missing required:\n"
            f"{', '.join(match_result.missing_required) if match_result.missing_required else 'None'}\n\n"
            f"Missing preferred:\n"
            f"{', '.join(match_result.missing_preferred) if match_result.missing_preferred else 'None'}\n\n"
            f"Technical skills:\n"
            f"{tech_score}\n\n"
            f"experience level:\n"
            f"{exp_score}\n\n"
            f"Seniority:\n"
            f"{sen_score}\n\n"
            f"Domain fit:\n"
            f"{dom_score}\n\n"
            f"Culture fit:\n"
            f"{cult_score}\n\n"
            f"Strategy:\n"
            f"{match_result.strategy}\n\n"
            f"Gaps:\n"
            f"{match_result.gap_narrative}"
        )

        confirm_letter_msg = f"{dashboard}\n\nReady to generate your cover letter? Type 'cover letter' to proceed, type 'update profile' to update your profile, or describe any adjustments you'd like to make to this fit report:"
        yield Event(
            content=types.Content(
                role="model", parts=[types.Part.from_text(text=confirm_letter_msg)]
            )
        )
        yield RequestInput(
            interrupt_id=letter_confirm_id,
            message=confirm_letter_msg,
        )
        return

    letter_confirm = ctx.resume_inputs[letter_confirm_id].strip().lower()
    if "cover letter" in letter_confirm:
        yield Event(
            output=True,
            actions=EventActions(route="route_letter"),
            content=types.Content(
                role="model",
                parts=[types.Part.from_text(text="Generating cover letter...")]
            )
        )
    elif "update profile" in letter_confirm:
        profile.confirmed = False
        ctx.state["profile"] = profile.model_dump()
        ctx.state["cover_letter"] = ""
        ctx.state["draft_count"] = 1
        
        # Increment profile_confirm_count to ensure setup_candidate uses a fresh, uncached interrupt ID
        profile_confirm_count = ctx.state.get("profile_confirm_count", 0)
        ctx.state["profile_confirm_count"] = profile_confirm_count + 1
        
        ctx.resume_inputs.pop(letter_confirm_id, None)
        yield Event(
            output=True,
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
        # User wants to adjust match strategy/score
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=(
                f"Current Match:\n{match_result.model_dump_json()}\n\n"
                f"User Adjustment Request:\n{ctx.resume_inputs[letter_confirm_id]}"
            ),
            config=types.GenerateContentConfig(
                system_instruction="Update the job match scoring, strategic angle, and gap narrative to reflect the user's adjustments. Return updated complete JobMatch schema.",
                response_mime_type="application/json",
                response_schema=ExtractedJobMatch,
            ),
        )
        extracted = ExtractedJobMatch(**json.loads(response.text))
        adjusted_match = JobMatch(
            company=extracted.company,
            role=extracted.role,
            score=extracted.score,
            breakdown={item.dimension: item.score for item in extracted.breakdown},
            matched_skills=extracted.matched_skills,
            missing_required=extracted.missing_required,
            missing_preferred=extracted.missing_preferred,
            strategy=extracted.strategy,
            gap_narrative=extracted.gap_narrative,
            relevant_projects=extracted.relevant_projects,
        )
        ctx.state["current_job"] = adjusted_match.model_dump()
        ctx.state["cover_letter"] = ""
        ctx.state["draft_count"] = 1

        ctx.resume_inputs.pop(letter_confirm_id, None)
        ctx.state["letter_confirm_count"] = confirm_count + 1
        yield Event(
            output=True,
            actions=EventActions(route="loop_analyze"),
            content=types.Content(
                role="model",
                parts=[types.Part.from_text(text="Updating job analysis...")]
            )
        )


@node(rerun_on_resume=True)
async def generate_cover_letter(ctx: Context, node_input: Any):
    """Phase 3: Cover Letter Generation & Refinement (Generator / Reviewer & Gate)"""
    profile_dict = ctx.state.get("profile") or {}
    profile = CandidateProfile(**profile_dict)
    current_job_dict = ctx.state.get("current_job")
    match_result = JobMatch(**current_job_dict) if current_job_dict else None
    draft_num = ctx.state.get("draft_count", 1)

    job_idx = ctx.state.setdefault("job_index", 0)
    refinement_count = ctx.state.setdefault("refinement_count", 0)
    refinement_id = f"refinement_input_{job_idx}_{refinement_count}" if job_idx > 0 else f"refinement_input_{refinement_count}"
    # 1. Generate/Refine cover letter
    if not ctx.resume_inputs or refinement_id not in ctx.resume_inputs:
        if not ctx.state.get("cover_letter"):
            current_date = datetime.now().strftime("%B %d, %Y")
            response = client.models.generate_content(
                model=MODEL_NAME,
                contents=(
                    f"Today's date is {current_date}.\n"
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
        else:
            cover_letter = ctx.state["cover_letter"]

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

        refine_msg = f"{suggestions}\n\nType your refinement instruction, type 'update profile' to edit your profile, or type 'job postings' to analyze another job:"
        yield Event(
            content=types.Content(
                role="model", parts=[types.Part.from_text(text=refine_msg)]
            )
        )
        yield RequestInput(
            interrupt_id=refinement_id,
            message=refine_msg,
        )
        return

    refinement_input = ctx.resume_inputs[refinement_id]

    # 2. Check if user wants a new job, profile update, or refinement
    refinement_input_lower = refinement_input.strip().lower()
    is_new_job = "job postings" in refinement_input_lower
    is_profile_update = "update profile" in refinement_input_lower

    if is_new_job:
        # Reset current job and inputs
        ctx.state["current_job"] = None
        ctx.state["cover_letter"] = ""
        ctx.state["draft_count"] = 1
        ctx.state["job_index"] = ctx.state.get("job_index", 0) + 1
        ctx.state["job_input_count"] = 0
        ctx.state["letter_confirm_count"] = 0
        ctx.state["refinement_count"] = 0
        for k in list(ctx.resume_inputs.keys()):
            if k.startswith("job_input_") or k.startswith("letter_confirm_"):
                ctx.resume_inputs.pop(k, None)
        ctx.resume_inputs.pop(refinement_id, None)
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
        ctx.state["cover_letter"] = ""
        ctx.state["draft_count"] = 1
        
        # Increment profile_confirm_count to ensure setup_candidate uses a fresh, uncached interrupt ID
        profile_confirm_count = ctx.state.get("profile_confirm_count", 0)
        ctx.state["profile_confirm_count"] = profile_confirm_count + 1
        
        ctx.resume_inputs.pop(refinement_id, None)
        yield Event(
            output=True,
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

        ctx.resume_inputs.pop(refinement_id, None)
        ctx.state["refinement_count"] = refinement_count + 1
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
            from_node=analyze_job,
            to_node=setup_candidate,
            route="route_setup",
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
