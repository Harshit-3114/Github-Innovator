import json
import logging
from pathlib import Path
from core.llm_client import nim
from core.models import RepoInfo, QualifiedRepo
from core.config import settings
from db.repository import mark_repo_processed

logger = logging.getLogger(__name__)

PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "innovation_analysis.txt"
PROMPT_TEMPLATE = PROMPT_PATH.read_text(encoding="utf-8")


def analyze_innovation_opportunity(repo: RepoInfo) -> QualifiedRepo | None:
    topics_str = ", ".join(repo.topics[:10])
    prompt = PROMPT_TEMPLATE.format(
        full_name=repo.full_name,
        description=repo.description,
        language=repo.language,
        stars=repo.stars,
        topics=topics_str,
    )

    try:
        result = nim.chat_json(
            system="You are a technical product analyst. Return only valid JSON.",
            user=prompt,
        )
        data = json.loads(result)
    except Exception as e:
        logger.warning(f"Failed to analyze {repo.full_name}: {e}")
        return None

    overall_score = data.get("overall_score", 0)
    if overall_score < settings.INNOVATION_SCORE_THRESHOLD:
        return None

    qualified = QualifiedRepo(
        repo=repo,
        score=overall_score,
        rationale=data.get("rationale", ""),
        best_innovation=data.get("best_innovation", ""),
        difficulty=data.get("difficulty", 5),
        estimated_effort_hours=data.get("estimated_effort_hours", 8),
    )

    return qualified


def run_analysis(repos: list[RepoInfo]) -> list[QualifiedRepo]:
    qualified = []
    for i, repo in enumerate(repos, 1):
        logger.info("  [%s/%s] Analyzing %s (%s★)...", i, len(repos), repo.full_name, repo.stars)
        result = analyze_innovation_opportunity(repo)
        if result:
            qualified.append(result)
            mark_repo_processed(
                repo.full_name, repo.stars, repo.language, repo.license_key,
                result.score, result.best_innovation, status="qualified",
            )
    qualified.sort(key=lambda q: q.score, reverse=True)
    return qualified
