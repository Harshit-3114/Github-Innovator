import logging
from core.config import settings
from core.github_client import GitHubClient
from core.models import RepoInfo
from db.repository import is_repo_processed

logger = logging.getLogger(__name__)

SEARCH_QUERIES = [
    "stars:5..300 language:python NOT ai NOT machine-learning NOT deep-learning topic:cli forks:>1",
    "stars:5..300 language:javascript topic:cli forks:>1",
    "stars:5..300 language:typescript topic:cli forks:>1",
    "stars:3..200 pushed:>2025-06-01 language:python -topic:awesome -topic:tutorial good-first-issues:>1",
    "stars:3..200 pushed:>2025-06-01 language:javascript -topic:awesome -topic:learning",
    "stars:5..300 language:go topic:cli -topic:awesome",
    "stars:5..300 language:rust topic:cli -topic:awesome",
    "topic:productivity-tool stars:5..300 language:python -topic:awesome -topic:learning",
    "topic:developer-tools stars:5..300 language:python -topic:awesome",
    "topic:automation stars:5..300 language:python -topic:awesome",
]


def discover_repos(gh: GitHubClient) -> list[RepoInfo]:
    candidates: dict[str, RepoInfo] = {}

    for i, query in enumerate(SEARCH_QUERIES, 1):
        logger.info("  Search [%s/%s]: %s", i, len(SEARCH_QUERIES), query)
        repos = gh.search_repos(query, max_results=20)
        for repo in repos:
            if repo.full_name in candidates:
                continue
            if is_repo_processed(repo.full_name):
                continue
            candidates[repo.full_name] = repo

    return list(candidates.values())


def filter_repos(repos: list[RepoInfo], gh: GitHubClient) -> list[RepoInfo]:
    filtered = []
    for repo in repos:
        if repo.stars < settings.MIN_STARS or repo.stars > settings.MAX_STARS:
            continue
        if repo.language not in settings.SUPPORTED_LANGUAGES:
            continue
        if repo.license_key and repo.license_key not in settings.LICENSES_ALLOWED:
            continue
        if not repo.description or len(repo.description) < 10:
            continue

        filtered.append(repo)
    return filtered
