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
import google.auth
from dotenv import load_dotenv
from google.adk.skills import load_skill_from_dir
from google import genai

load_dotenv()

# Authentication Configuration
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
