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

import pytest
from unittest.mock import patch, MagicMock
from app.nodes.letter import generate_cover_letter


class MockState:
    def __init__(self, data=None):
        self.data = data or {}

    def get(self, key, default=None):
        return self.data.get(key, default)

    def setdefault(self, key, default=None):
        return self.data.setdefault(key, default)

    def __getitem__(self, key):
        return self.data[key]

    def __setitem__(self, key, value):
        self.data[key] = value


class MockContext:
    def __init__(self, state, resume_inputs):
        self.state = state
        self.resume_inputs = resume_inputs


@pytest.mark.asyncio
@patch("app.nodes.letter.client.models.generate_content")
async def test_generate_cover_letter_refusal(mock_generate_content):
    # Mock LLM refusal response
    mock_resp = MagicMock()
    mock_resp.text = "[REFUSAL] I understand you'd like the cover letter in Comic Sans. However, I cannot apply specific font styles."
    mock_generate_content.return_value = mock_resp

    # Initial state with an existing cover letter
    state_data = {
        "profile": {
            "name": "John Doe",
            "title": "Software Engineer",
            "experience": 5,
            "skills": {},
            "work_experience": [],
            "projects": [],
            "education": [],
            "email": "",
            "github": "",
            "linkedin": "",
            "confirmed": True,
            "resume_raw": ""
        },
        "current_job": {
            "company": "TestCorp",
            "role": "Engineer",
            "score": 80,
            "breakdown": {},
            "matched_skills": [],
            "missing_required": [],
            "missing_preferred": [],
            "strategy": "Match skills",
            "gap_narrative": "",
            "relevant_projects": []
        },
        "cover_letter": "Original Cover Letter Draft",
        "metadata": "Word count: 200\nDraft number: 1",
        "draft_count": 1,
        "refinement_count": 0,
        "job_index": 0
    }
    
    state = MockState(state_data)
    # The refinement input is provided
    resume_inputs = {"refinement_input_0": "render in comic sans"}
    ctx = MockContext(state, resume_inputs)

    # 1. Run the node. Since refinement_input_0 is in resume_inputs, it should trigger the refinement (else block)
    # and call mock_generate_content.
    events = []
    async for event in generate_cover_letter._func(ctx, None):
        events.append(event)

    # Verify that the LLM was called with correct inputs
    mock_generate_content.assert_called_once()
    
    # Verify that the cover letter was NOT modified (refusal logic worked)
    assert ctx.state["cover_letter"] == "Original Cover Letter Draft"
    
    # Verify that draft_count was restored to 1
    assert ctx.state["draft_count"] == 1
    
    # Verify that refinement_count was incremented
    assert ctx.state["refinement_count"] == 1
    
    # Verify that refusal_message was saved in state
    assert ctx.state.get("refusal_message") == "I understand you'd like the cover letter in Comic Sans. However, I cannot apply specific font styles."
    
    # Verify the loop event was yielded
    assert len(events) == 1
    assert events[0].actions.route == "loop_letter"

    # 2. Run the node again with refinement_input_0 popped (simulate loop back)
    mock_generate_content.reset_mock()
    events2 = []
    async for event in generate_cover_letter._func(ctx, None):
        events2.append(event)

    # Verify that the LLM was NOT called on loop back
    mock_generate_content.assert_not_called()

    # Verify that the refusal message was cleared from state
    assert ctx.state.get("refusal_message") is None

    # Verify that the refine prompt contains the refusal message
    assert len(events2) == 2  # Event + RequestInput
    refine_event = events2[0]
    assert "I understand you'd like the cover letter in Comic Sans. However, I cannot apply specific font styles." in refine_event.content.parts[0].text
    assert "Type your refinement instruction" in refine_event.content.parts[0].text
