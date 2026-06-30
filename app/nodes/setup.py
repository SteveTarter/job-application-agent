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
import json
from typing import Any, Optional
from google.genai import types
from google.adk.workflow import node
from google.adk.agents.context import Context
from google.adk.events.event import Event
from google.adk.events.event_actions import EventActions
from google.adk.events.request_input import RequestInput

from app.config import client, MODEL_NAME, extract_skill
from app.models import CandidateProfile, ExtractedProfile
from app.helpers import run_fetch_github_repos


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

        yield Event(
            content=types.Content(
                role="model",
                parts=[types.Part.from_text(text="Generating profile...\n")]
            )
        )

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
            try:
                updated = json.loads(response.text)
            except Exception as e:
                ctx.resume_inputs.pop(interrupt_id, None)
                yield Event(
                    output=True,
                    actions=EventActions(route="loop_setup"),
                    content=types.Content(
                        role="model",
                        parts=[
                            types.Part.from_text(
                                text="I encountered a temporary error while merging your corrections (JSON parsing failed). Please try describing the corrections again."
                            )
                        ]
                    )
                )
                return

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
