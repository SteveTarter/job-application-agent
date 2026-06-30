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

from typing import Any, Optional
from pydantic import BaseModel, Field

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
    metadata: str = ""
    draft_count: int = 1
    job_input_raw: str = ""
    profile_confirm_count: int = 0
    job_input_count: int = 0
    letter_confirm_count: int = 0
    refinement_count: int = 0
    resume_input_count: int = 0
    job_index: int = 0
