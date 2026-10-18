from core.models import (
    RepoInfo, QualifiedRepo, CodeGraph, FileInfo, FunctionDef,
    ClassDef, InnovationPlan, FileChange, ValidationResult, InnovationState,
)


class TestRepoInfo:
    def test_minimal_creation(self):
        r = RepoInfo(
            full_name="owner/repo",
            owner="owner",
            name="repo",
            description="A test repo",
            language="Python",
            stars=42,
            topics=["cli"],
            license_key="mit",
            pushed_at="2024-01-01T00:00:00",
            clone_url="https://github.com/owner/repo.git",
            size_bytes=1024,
        )
        assert r.full_name == "owner/repo"
        assert r.owner == "owner"
        assert r.stars == 42

    def test_empty_description(self):
        r = RepoInfo(
            full_name="o/r", owner="o", name="r", description="",
            language="Go", stars=0, topics=[], license_key="",
            pushed_at="", clone_url="", size_bytes=0,
        )
        assert r.description == ""


class TestQualifiedRepo:
    def test_creation(self):
        repo = RepoInfo(
            full_name="o/r", owner="o", name="r", description="d",
            language="Python", stars=10, topics=[], license_key="mit",
            pushed_at="", clone_url="", size_bytes=0,
        )
        q = QualifiedRepo(
            repo=repo, score=8, rationale="Good opportunity",
            best_innovation="Add CLI", difficulty=3, estimated_effort_hours=4,
        )
        assert q.score == 8
        assert q.best_innovation == "Add CLI"
        assert q.repo.full_name == "o/r"


class TestCodeGraph:
    def test_empty_graph(self):
        g = CodeGraph(repo_path="/tmp/test")
        assert g.files == []
        assert g.imports == {}
        assert g.functions == {}

    def test_with_file(self):
        g = CodeGraph(repo_path="/tmp/test")
        g.files.append(FileInfo(path="main.py", language="Python", line_count=10))
        assert len(g.files) == 1
        assert g.files[0].path == "main.py"


class TestFunctionDef:
    def test_with_docstring(self):
        f = FunctionDef(name="foo", start_line=1, end_line=10, docstring="Does foo")
        assert f.name == "foo"
        assert f.docstring == "Does foo"

    def test_without_docstring(self):
        f = FunctionDef(name="bar", start_line=5, end_line=15)
        assert f.docstring is None


class TestClassDef:
    def test_with_methods(self):
        c = ClassDef(name="Foo", start_line=1, end_line=20)
        c.methods.append(FunctionDef(name="bar", start_line=2, end_line=5))
        assert len(c.methods) == 1
        assert c.methods[0].name == "bar"


class TestInnovationPlan:
    def test_defaults(self):
        p = InnovationPlan(description="Add logging", rationale="Need logs")
        assert p.changes == []
        assert p.new_dependencies == []
        assert p.risk_assessment == "low"

    def test_with_changes(self):
        p = InnovationPlan(
            description="Major refactor",
            rationale="Outdated code",
            changes=[FileChange(file="main.py", change_type="modify", description="Rewrite", language="Python")],
            new_dependencies=["rich"],
            risk_assessment="medium",
        )
        assert len(p.changes) == 1
        assert "rich" in p.new_dependencies


class TestFileChange:
    def test_defaults(self):
        c = FileChange(file="foo.py", change_type="add", description="New", language="Python")
        assert c.old_content == ""
        assert c.new_content == ""
        assert c.context == ""

    def test_with_content(self):
        c = FileChange(
            file="bar.py", change_type="modify",
            description="Update", language="Python",
            old_content="old", new_content="new", context="after line 10",
        )
        assert c.new_content == "new"
        assert c.context == "after line 10"


class TestValidationResult:
    def test_passed(self):
        v = ValidationResult(passed=True)
        assert v.errors == []

    def test_failed(self):
        v = ValidationResult(passed=False, errors=["Syntax error"])
        assert v.passed is False
        assert len(v.errors) == 1


class TestInnovationState:
    def test_typed_dict_structure(self):
        state: InnovationState = {
            "candidate_repos": [],
            "qualified_repos": [],
            "innovation_opportunities": [],
            "current_repo": None,
            "code_graph": None,
            "innovation_plan": None,
            "changed_files": [],
            "validation_results": [],
            "retry_count": 0,
            "current_index": 0,
            "fork_url": "",
            "readme_content": "",
            "processed_full_names": set(),
            "run_metadata": {},
        }
        assert state["retry_count"] == 0
        assert state["fork_url"] == ""
        assert state["processed_full_names"] == set()
