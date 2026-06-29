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
os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "False"

import app.agent
app.agent.MODEL_NAME = "gemini-2.5-flash"

from google.adk.agents.run_config import RunConfig, StreamingMode
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from app.agent import root_agent



def test_agent_stream() -> None:
    """
    Integration test for the agent stream functionality.
    Tests that the agent returns valid streaming responses.
    """

    session_service = InMemorySessionService()

    session = session_service.create_session_sync(user_id="test_user", app_name="test")
    runner = Runner(agent=root_agent, session_service=session_service, app_name="test")

    message = types.Content(
        role="user", parts=[types.Part.from_text(text="Why is the sky blue?")]
    )

    events = list(
        runner.run(
            new_message=message,
            user_id="test_user",
            session_id=session.id,
            run_config=RunConfig(streaming_mode=StreamingMode.SSE),
        )
    )
    assert len(events) > 0, "Expected at least one message"

    has_text_content = False
    for event in events:
        if (
            event.content
            and event.content.parts
            and any(part.text for part in event.content.parts)
        ):
            has_text_content = True
            break
    assert has_text_content, "Expected at least one message with text content"


def is_request_input(event, interrupt_id: str) -> bool:
    if event.content and event.content.parts:
        for part in event.content.parts:
            if part.function_call and part.function_call.name == "adk_request_input":
                fc = part.function_call
                fc_id = fc.id or (fc.args.get("interruptId") if fc.args else None)
                if fc_id == interrupt_id:
                    return True
    return False


def test_agent_flow() -> None:
    """
    Integration test simulating the multi-turn candidate profile setup
    and transition to the job analysis phase.
    """
    session_service = InMemorySessionService()
    session = session_service.create_session_sync(user_id="test_user_flow", app_name="test")
    runner = Runner(agent=root_agent, session_service=session_service, app_name="test")

    # Step 1: Initial message to start setup
    events = list(
        runner.run(
            new_message=types.Content(
                role="user", parts=[types.Part.from_text(text="Hi")]
            ),
            user_id="test_user_flow",
            session_id=session.id,
        )
    )
    # The agent should ask for resume input
    assert any(
        is_request_input(event, "resume_input_0") for event in events
    )

    # Step 2: Provide a simple resume text
    resume_text = (
        "Name: Jane Doe\n"
        "Title: Senior Backend Engineer\n"
        "Experience: 8 years\n"
        "Skills: Python, Go, Docker\n"
    )
    response_part = types.Part(
        function_response=types.FunctionResponse(
            id="resume_input_0",
            name="adk_request_input",
            response={"result": resume_text}
        )
    )
    events2 = list(
        runner.run(
            new_message=types.Content(
                role="user", parts=[response_part]
            ),
            user_id="test_user_flow",
            session_id=session.id,
        )
    )
    # The agent should now ask for confirmation of the extracted profile
    assert any(
        is_request_input(event, "profile_confirm_0") for event in events2
    )

    # Step 3: Provide corrections
    correct_part = types.Part(
        function_response=types.FunctionResponse(
            id="profile_confirm_0",
            name="adk_request_input",
            response={"result": "Actually, please add Go and Spring Boot to my skills."}
        )
    )
    events3 = list(
        runner.run(
            new_message=types.Content(
                role="user", parts=[correct_part]
            ),
            user_id="test_user_flow",
            session_id=session.id,
        )
    )
    # The agent should loop back and ask for profile confirmation again
    assert any(
        is_request_input(event, "profile_confirm_1") for event in events3
    )

    # Step 4: Confirm the profile
    confirm_part = types.Part(
        function_response=types.FunctionResponse(
            id="profile_confirm_1",
            name="adk_request_input",
            response={"result": "job postings"}
        )
    )
    events4 = list(
        runner.run(
            new_message=types.Content(
                role="user", parts=[confirm_part]
            ),
            user_id="test_user_flow",
            session_id=session.id,
        )
    )
    # The agent should transition to job analysis and ask for a job posting
    assert any(
        is_request_input(event, "job_input_0") for event in events4
    )

    # Step 5: Provide a job description
    job_desc = (
        "Company: Block (Cash App)\n"
        "Role: Senior Software Engineer, Backend\n"
        "We are looking for a Senior Software Engineer to join our Payments team. Required skills: Java, Spring Boot, Kafka, Kubernetes. Preferred: Go, gRPC, Terraform."
    )
    job_part = types.Part(
        function_response=types.FunctionResponse(
            id="job_input_0",
            name="adk_request_input",
            response={"result": job_desc}
        )
    )
    events5 = list(
        runner.run(
            new_message=types.Content(
                role="user", parts=[job_part]
            ),
            user_id="test_user_flow",
            session_id=session.id,
        )
    )
    # The agent should present the dashboard and ask for cover letter approval
    assert any(
        is_request_input(event, "letter_confirm_0") for event in events5
    )

    # Step 6: Answer yes to ready to generate cover letter
    yes_part = types.Part(
        function_response=types.FunctionResponse(
            id="letter_confirm_0",
            name="adk_request_input",
            response={"result": "cover letter"}
        )
    )
    events6 = list(
        runner.run(
            new_message=types.Content(
                role="user", parts=[yes_part]
            ),
            user_id="test_user_flow",
            session_id=session.id,
        )
    )
    # The agent should generate the cover letter and ask for refinement
    assert any(
        is_request_input(event, "refinement_input_0") for event in events6
    )

    # Step 7: Request a profile update from the cover letter node
    update_profile_part = types.Part(
        function_response=types.FunctionResponse(
            id="refinement_input_0",
            name="adk_request_input",
            response={"result": "update profile"}
        )
    )
    events7 = list(
        runner.run(
            new_message=types.Content(
                role="user", parts=[update_profile_part]
            ),
            user_id="test_user_flow",
            session_id=session.id,
        )
    )
    # The agent should transition to setup candidate and ask for confirmation again
    assert any(
        is_request_input(event, "profile_confirm_2") for event in events7
    )


def test_empty_resume_input() -> None:
    session_service = InMemorySessionService()
    session = session_service.create_session_sync(
        user_id="test_user_empty_resume",
        app_name="test",
    )
    runner = Runner(agent=root_agent, session_service=session_service, app_name="test")

    # Step 1: Initial greeting
    events1 = list(
        runner.run(
            new_message=types.Content(
                role="user", parts=[types.Part.from_text(text="Hi")]
            ),
            user_id="test_user_empty_resume",
            session_id=session.id,
        )
    )
    # The agent should ask for resume input
    assert any(
        is_request_input(event, "resume_input_0") for event in events1
    )

    # Step 2: Provide an empty/too short resume text (e.g. "Too short")
    short_resume_part = types.Part(
        function_response=types.FunctionResponse(
            id="resume_input_0",
            name="adk_request_input",
            response={"result": "Too short"}
        )
    )
    events2 = list(
        runner.run(
            new_message=types.Content(
                role="user", parts=[short_resume_part]
            ),
            user_id="test_user_empty_resume",
            session_id=session.id,
        )
    )
    # The agent should reject and prompt again with resume_input_1
    assert any(
        is_request_input(event, "resume_input_1") for event in events2
    )
    # Ensure it yielded an error message event
    assert any(
        "I couldn't extract any readable text" in event.content.parts[0].text
        for event in events2 if hasattr(event, "content") and event.content and event.content.parts
    )



