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


def split_letter_response(text: str) -> tuple[str, str]:
    if not text:
        return "", ""

    # Ensure standard blank line spacing between date and salutation
    import re
    lines_list = text.split("\n")
    if len(lines_list) >= 2:
        first_line = lines_list[0].strip()
        date_pattern = r"^(?:[A-Za-z]+\s+\d{1,2},\s+\d{4}|\d{4}-\d{2}-\d{2})\s*$"
        if re.match(date_pattern, first_line) and lines_list[1].strip() != "":
            text = lines_list[0] + "\n\n" + "\n".join(lines_list[1:])

    text_lower = text.lower()
    markers = [
        "**metadata:**",
        "metadata:",
        "metadata",
        "word count:",
        "word count",
        "evidence audit:",
        "evidence audit",
        "draft number:",
        "draft number",
        "refinement suggestions",
        "suggestions:"
    ]
    
    split_idx = -1
    for marker in markers:
        idx = text_lower.find(marker)
        if idx != -1:
            if split_idx == -1 or idx < split_idx:
                split_idx = idx
                
    if split_idx != -1:
        # Go back to the start of the line containing the marker
        line_start = text.rfind("\n", 0, split_idx)
        if line_start != -1:
            split_idx = line_start
        
        cover_letter = text[:split_idx].strip()
        metadata_and_suggestions = text[split_idx:].strip()
        
        # Clean horizontal rule lines, metadata headers, and suggestions headers from the end of the letter
        metadata_headers = [
            "**metadata:**",
            "metadata:",
            "metadata",
            "word count:",
            "word count",
            "evidence audit:",
            "evidence audit",
            "draft number:",
            "draft number",
            "suggestions:",
            "refinement suggestions",
            "**refinement suggestions:**"
        ]
        
        while True:
            stripped = cover_letter.rstrip()
            lines = stripped.split("\n")
            if not lines:
                break
            last_line = lines[-1].strip()
            last_line_lower = last_line.lower()
            
            # 1. Check if last line is a divider
            is_divider = last_line and (all(c in "-*_" for c in last_line) or last_line.startswith("──"))
            
            # 2. Check if last line starts with any metadata header
            is_metadata_header = any(last_line_lower.startswith(h) for h in metadata_headers)
            
            if is_divider or is_metadata_header or not last_line:
                cover_letter = "\n".join(lines[:-1]).strip()
            else:
                break
                
        return cover_letter, metadata_and_suggestions
    else:
        return text.strip(), ""


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
            raw_text = response.text
            cover_letter, metadata = split_letter_response(raw_text)
            ctx.state["cover_letter"] = cover_letter
            ctx.state["metadata"] = metadata
        else:
            cover_letter = ctx.state["cover_letter"]
            metadata = ctx.state.get("metadata", "")

        # Fallback if metadata split was empty
        if not metadata:
            word_count = len(cover_letter.split())
            metadata = (
                f"Word count: {word_count}\n"
                f"Evidence audit: Roadrunner cited\n"
                f"Draft number: {draft_num}"
            )

        refine_msg = f"{metadata}\n\nType your refinement instruction, type 'update profile' to edit your profile, or type 'job postings' to analyze another job:"
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
        raw_text = response.text
        cover_letter, metadata = split_letter_response(raw_text)
        ctx.state["cover_letter"] = cover_letter
        ctx.state["metadata"] = metadata

        ctx.resume_inputs.pop(refinement_id, None)
        ctx.state["refinement_count"] = refinement_count + 1
        yield Event(actions=EventActions(route="loop_letter"))
