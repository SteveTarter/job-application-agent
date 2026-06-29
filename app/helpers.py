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

# Load local skills dynamically
WORKSPACE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILLS_DIR = os.path.join(WORKSPACE_DIR, ".agents", "skills")


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
