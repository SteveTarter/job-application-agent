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

from google.adk.workflow import Workflow, START, Edge
from google.adk.apps import App

from app.models import AgentState
from app.nodes.setup import entry_node, setup_candidate
from app.nodes.analysis import analyze_job
from app.nodes.letter import generate_cover_letter

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
