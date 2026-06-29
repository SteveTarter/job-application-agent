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

from datetime import datetime
from typing import Any
from google.genai import types
from google.adk.workflow import node
from google.adk.agents.context import Context
from google.adk.events.event import Event
from google.adk.events.event_actions import EventActions
from google.adk.events.request_input import RequestInput

from app.config import client, MODEL_NAME, letter_skill
from app.models import CandidateProfile, JobMatch


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
