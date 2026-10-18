from __future__ import annotations
from typing import Optional, TypedDict
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class RepoInfo:
    full_name: str
    owner: str
    name: str
    description: str
    language: str
    stars: int
    topics: list[str]
    license_key: str
    pushed_at: str
    clone_url: str
    size_bytes: int


@dataclass
class QualifiedRepo:
    repo: RepoInfo
    score: int
    rationale: str
    best_innovation: str
    difficulty: int
    estimated_effort_hours: int


@dataclass
class CodeGraph:
    repo_path: str
    files: list[FileInfo] = field(default_factory=list)
    imports: dict[str, set[str]] = field(default_factory=dict)
    functions: dict[str, list[FunctionDef]] = field(default_factory=dict)
    classes: dict[str, list[ClassDef]] = field(default_factory=dict)
    entry_points: list[str] = field(default_factory=list)
    config_files: list[str] = field(default_factory=list)
    test_files: list[str] = field(default_factory=list)


@dataclass
class FileInfo:
    path: str
    language: str
    line_count: int


@dataclass
class FunctionDef:
    name: str
    start_line: int
    end_line: int
    docstring: Optional[str] = None


@dataclass
class ClassDef:
    name: str
    start_line: int
    end_line: int
    methods: list[FunctionDef] = field(default_factory=list)


@dataclass
class InnovationPlan:
    description: str
    rationale: str
    changes: list[FileChange] = field(default_factory=list)
    new_dependencies: list[str] = field(default_factory=list)
    risk_assessment: str = "low"


@dataclass
class FileChange:
    file: str
    change_type: str
    description: str
    language: str
    old_content: str = ""
    new_content: str = ""
    context: str = ""


@dataclass
class ValidationResult:
    passed: bool
    errors: list[str] = field(default_factory=list)
    test_output: Optional[str] = None


class InnovationState(TypedDict):
    candidate_repos: list[RepoInfo]
    qualified_repos: list[QualifiedRepo]
    innovation_opportunities: list[QualifiedRepo]
    current_repo: Optional[QualifiedRepo]
    code_graph: Optional[CodeGraph]
    innovation_plan: Optional[InnovationPlan]
    changed_files: list[FileChange]
    validation_results: list[ValidationResult]
    retry_count: int
    current_index: int
    fork_url: str
    readme_content: str
    processed_full_names: set[str]
    run_metadata: dict
    max_repos: int


@dataclass
class RunLog:
    id: Optional[int] = None
    started_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
    repos_discovered: int = 0
    repos_qualified: int = 0
    forks_created: int = 0
    forks_succeeded: int = 0
    total_api_calls: int = 0
    status: str = "running"
    error: Optional[str] = None
