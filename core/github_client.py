import time
import logging
from typing import Optional
from github import Github, GithubException, RateLimitExceededException
from core.config import settings
from core.models import RepoInfo

logger = logging.getLogger(__name__)


class GitHubClient:
    def __init__(self):
        self._gh = Github(settings.GITHUB_TOKEN, timeout=15)
        self._user = None

    @property
    def user(self):
        if self._user is None:
            self._user = self._gh.get_user()
        return self._user

    def search_repos(self, query: str, max_results: int = 50) -> list[RepoInfo]:
        repos = []
        try:
            results = self._gh.search_repositories(query, sort="stars", order="desc")
            page = results.get_page(0)
            for repo in page[:max_results]:
                try:
                    license_key = repo.license.key if repo.license else ""
                except Exception:
                    license_key = ""

                repos.append(RepoInfo(
                    full_name=repo.full_name,
                    owner=repo.owner.login,
                    name=repo.name,
                    description=repo.description or "",
                    language=repo.language or "",
                    stars=repo.stargazers_count,
                    topics=repo.get_topics(),
                    license_key=license_key,
                    pushed_at=repo.pushed_at.isoformat() if repo.pushed_at else "",
                    clone_url=repo.clone_url,
                    size_bytes=repo.size,
                ))
                self._respect_rate_limit()
        except RateLimitExceededException:
            self._wait_for_rate_limit()
            return self.search_repos(query, max_results)
        return repos

    def get_repo_size_lines(self, full_name: str) -> Optional[int]:
        try:
            repo = self._gh.get_repo(full_name)
            total = 0
            contents = repo.get_contents("")
            while contents:
                content = contents.pop(0)
                if content.type == "dir":
                    contents.extend(repo.get_contents(content.path))
                elif content.type == "file" and content.name.endswith((".py", ".js", ".ts", ".go", ".rs")):
                    try:
                        decoded = content.decoded_content.decode("utf-8")
                        total += len(decoded.splitlines())
                    except Exception:
                        pass
            return total
        except Exception:
            return None

    def fork_repo(self, full_name: str, new_name: Optional[str] = None) -> Optional[str]:
        try:
            fork_name = new_name or full_name.split("/")[1]
            existing = self._gh.get_repo(f"{self.user.login}/{fork_name}")
            return existing.html_url
        except GithubException:
            pass

        try:
            repo = self._gh.get_repo(full_name)
            fork = self._user.create_fork(repo, name=new_name)
            self._respect_rate_limit()
            return fork.html_url
        except GithubException as e:
            logger.warning(f"Failed to fork {full_name}: {e}")
            return None

    def _respect_rate_limit(self):
        remaining, _ = self._gh.rate_limiting
        if remaining and remaining < 10:
            self._wait_for_rate_limit()
        time.sleep(0.5)

    def _wait_for_rate_limit(self):
        reset = self._gh.rate_limiting_resettime
        wait = max(reset - time.time() + 5, 0)
        if wait > 0:
            time.sleep(wait)
