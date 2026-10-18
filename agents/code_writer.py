import logging
from pathlib import Path
from core.llm_client import nim
from core.models import FileChange, CodeGraph, InnovationPlan, QualifiedRepo
from core.validator import syntax_check

logger = logging.getLogger(__name__)

PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "code_generation.txt"
GENERATION_PROMPT = PROMPT_PATH.read_text(encoding="utf-8")


def execute_plan(repo: QualifiedRepo, plan: InnovationPlan, code_graph: CodeGraph,
                 repo_path: str) -> list[FileChange]:
    completed_changes = []
    errors = []

    for change in plan.changes:
        file_path = Path(repo_path) / change.file
        logger.info("  Generating %s (%s)...", change.file, change.change_type)

        existing_content = ""
        if file_path.exists():
            existing_content = file_path.read_text(encoding="utf-8", errors="ignore")

        change.old_content = existing_content
        related_imports = code_graph.imports.get(change.file, set())
        project_structure = "\n".join(
            f"  {f.path} ({f.line_count} lines)" for f in code_graph.files[:20]
        )
        prompt = GENERATION_PROMPT.format(
            full_name=repo.repo.full_name,
            language=repo.repo.language,
            innovation_description=plan.description,
            file_path=change.file,
            existing_content=existing_content[:3000] if existing_content else "(new file)",
            related_imports=", ".join(related_imports),
            project_structure=project_structure,
            change_description=change.description,
        )

        try:
            new_content = nim.chat(
                system="You are an expert software engineer. Generate clean, production-ready code.",
                user=prompt,
                temperature=0.3,
            )
        except Exception as e:
            logger.error(f"Failed to generate code for {change.file}: {e}")
            errors.append({"file": change.file, "error": str(e)})
            continue

        new_content = _clean_code_output(new_content, repo.repo.language)

        if new_content and syntax_check(new_content, repo.repo.language):
            change.new_content = new_content
            completed_changes.append(change)
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(new_content, encoding="utf-8")
        else:
            logger.warning(f"Generated code for {change.file} failed syntax check or was empty")
            errors.append({"file": change.file, "error": "syntax check failed or empty"})

    if errors:
        logger.warning(f"Code generation completed with {len(errors)} error(s): {errors}")

    return completed_changes


def _clean_code_output(content: str, language: str) -> str:
    content = content.strip()
    if content.startswith("```"):
        lines = content.splitlines()
        if len(lines) >= 2:
            content = "\n".join(lines[1:-1]) if lines[-1].startswith("```") else "\n".join(lines[1:])
    return content.strip()
