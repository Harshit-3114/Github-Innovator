import json
import logging
from core.llm_client import nim
from core.models import CodeGraph, InnovationPlan, FileChange, QualifiedRepo

logger = logging.getLogger(__name__)


def generate_innovation_plan(repo: QualifiedRepo, code_graph: CodeGraph) -> InnovationPlan | None:
    project_structure = "\n".join(
        f"  {f.path} ({f.line_count} lines)" for f in code_graph.files[:30]
    )
    entry_points = "\n".join(f"  {e}" for e in code_graph.entry_points)

    prompt = f"""Analyze this codebase and plan a comprehensive rewrite that makes the fork 80-90%+ different from the original while preserving core functionality.

Repository: {repo.repo.full_name}
Language: {repo.repo.language}

Complete Project Structure:
{project_structure}

Entry Points:
{entry_points}

Configuration Files: {code_graph.config_files}
Test Files: {code_graph.test_files}

Classes found: { {k: [c.name for c in v] for k, v in code_graph.classes.items()} }
Functions found: { {k: [f.name for f in v[:5]] for k, v in code_graph.functions.items()} }

You MUST propose modifying MOST of the source files in this project (at least 70%+ of non-trivial files).
Each file should be substantially rewritten with improvements such as:
- Complete refactoring with better architecture
- Adding comprehensive error handling and validation
- Modern language features and patterns
- Improved performance
- Better documentation and type hints
- Additional features visible from the code structure
- Restructuring for better maintainability

Return a JSON plan with specific file changes:
{{
  "changes": [
    {{
      "file": "relative/file/path",
      "change_type": "add|modify|delete",
      "description": "what to change and why — be detailed about the substantial rewrite",
      "context": "where in the file to make the change (after which function, near which line)"
    }}
  ],
  "new_dependencies": ["dep1", "dep2"],
  "risk_assessment": "low|medium|high",
  "rationale": "why this set of changes makes the fork substantially different and better"
}}

Plan changes for the MAJORITY of source files. At least 5 changes required unless the project has fewer than 5 files. Make each change a complete rewrite of the file.
"""

    try:
        result = nim.chat_json(
            system="You are a senior software architect. Return only valid JSON. You MUST include at least one change in the changes array.",
            user=prompt,
        )
        data = json.loads(result)
        logger.info("  Planner response: changes=%s", len(data.get("changes", [])))
    except (json.JSONDecodeError, Exception) as e:
        logger.warning("  Planner error: %s", e)
        return None

    changes = []
    for c in data.get("changes", []):
        changes.append(FileChange(
            file=c.get("file", ""),
            change_type=c.get("change_type", "modify"),
            description=c.get("description", ""),
            language=repo.repo.language,
            context=c.get("context", ""),
        ))

    return InnovationPlan(
        description=data.get("rationale", repo.repo.description)[:120],
        rationale=data.get("rationale", ""),
        changes=changes,
        new_dependencies=data.get("new_dependencies", []),
        risk_assessment=data.get("risk_assessment", "low"),
    )
