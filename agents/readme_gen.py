from pathlib import Path
from core.llm_client import nim
from core.models import QualifiedRepo, InnovationPlan

PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "readme_generation.txt"
PROMPT_TEMPLATE = PROMPT_PATH.read_text(encoding="utf-8")


def generate_readme(repo: QualifiedRepo, plan: InnovationPlan, fork_name: str) -> str:
    prompt = PROMPT_TEMPLATE.format(
        original_full_name=repo.repo.full_name,
        original_author=repo.repo.owner,
        license_key=repo.repo.license_key,
        fork_name=fork_name,
        original_url=f"https://github.com/{repo.repo.full_name}",
        innovation_description=plan.description,
        short_tagline=plan.description[:60],
    )

    try:
        content = nim.chat(
            system="You are a technical writer. Generate a polished README.md.",
            user=prompt,
            temperature=0.5,
            max_tokens=2048,
        )
    except Exception:
        content = f"# {fork_name}\n\nAI-enhanced fork of {repo.repo.full_name}."

    return content
