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

import json
from typing import Any
from pydantic import BaseModel, Field
from google.genai import types
from google.adk.workflow import node
from google.adk.agents.context import Context
from google.adk.events.event import Event
from google.adk.events.event_actions import EventActions
from google.adk.events.request_input import RequestInput
from google.adk.tools.load_web_page import load_web_page

from app.config import client, MODEL_NAME, match_skill
from app.models import CandidateProfile, JobMatch, ExtractedJobMatch
from app.helpers import run_search_company


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

        yield Event(
            content=types.Content(
                role="model",
                parts=[types.Part.from_text(text="Calculating Fit Score...\n")]
            )
        )

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

        confirm_letter_msg = (
            "Ready to generate your cover letter? Type 'cover letter' to proceed, "
            "type 'update profile' to update your profile, type 'job postings' to analyze a new job, "
            "or describe any adjustments you'd like to make to this fit report:"
        )
        yield Event(
            content=types.Content(
                role="model",
                parts=[
                    types.Part.from_text(text=f"{dashboard}\n\n{confirm_letter_msg}")
                ],
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
                parts=[types.Part.from_text(text="Generating cover letter...\n")]
            )
        )
    elif "update profile" in letter_confirm:
        profile.confirmed = False
        ctx.state["profile"] = profile.model_dump()
        ctx.state["cover_letter"] = ""
        ctx.state["current_job"] = None
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
    elif "job postings" in letter_confirm:
        # Reset current job and inputs for a new job posting analysis
        ctx.state["current_job"] = None
        ctx.state["cover_letter"] = ""
        ctx.state["draft_count"] = 1
        ctx.state["job_index"] = ctx.state.get("job_index", 0) + 1
        ctx.state["job_input_count"] = 0
        ctx.state["letter_confirm_count"] = 0
        ctx.state["refinement_count"] = 0
        
        # Clear inputs related to job/letter confirmation
        for k in list(ctx.resume_inputs.keys()):
            if k.startswith("job_input_") or k.startswith("letter_confirm_"):
                ctx.resume_inputs.pop(k, None)
        ctx.resume_inputs.pop(letter_confirm_id, None)
        
        yield Event(
            output=True,
            actions=EventActions(route="loop_analyze"),
            content=types.Content(
                role="model",
                parts=[
                    types.Part.from_text(
                        text="Let's analyze your new job posting."
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
