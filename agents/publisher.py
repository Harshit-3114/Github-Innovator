import logging
import os
import stat
import shutil
import subprocess
from pathlib import Path
from core.config import settings
from core.github_client import GitHubClient
from core.models import InnovationPlan

logger = logging.getLogger(__name__)


def _auth_remote_url(username: str, repo_name: str) -> str:
    return f"https://{username}:{settings.GITHUB_TOKEN}@github.com/{username}/{repo_name}.git"


def _git_run(args: list[str], cwd: str | None = None, timeout: int = 120) -> subprocess.CompletedProcess:
    result = subprocess.run(
        args, cwd=cwd, capture_output=True, text=True, timeout=timeout,
    )
    return result


def fork_and_clone(gh: GitHubClient, full_name: str) -> tuple[str, str] | None:
    repo_name = full_name.split("/")[1]
    fork_name = f"{repo_name}-ai"
    fork_url = gh.fork_repo(full_name, new_name=fork_name)
    if not fork_url:
        logger.warning("  Fork creation failed for %s", full_name)
        return None

    clone_dir = settings.TEMP_CLONE_DIR / f"{full_name.replace('/', '_')}_fork"
    if clone_dir.exists():
        cleanup(str(clone_dir))
    clone_dir.parent.mkdir(parents=True, exist_ok=True)

    auth_url = _auth_remote_url(gh.user.login, fork_name)
    result = _git_run(
        ["git", "clone", "--depth=1", auth_url, str(clone_dir)],
        timeout=120,
    )
    if result.returncode != 0:
        logger.warning("  Clone of fork failed: %s", result.stderr[:200])
        return None

    _git_run(["git", "config", "user.name", "github-innovator"], cwd=str(clone_dir), timeout=10)
    _git_run(["git", "config", "user.email", "innovator@github.local"], cwd=str(clone_dir), timeout=10)

    return str(clone_dir), fork_url


def commit_and_push(repo_path: str, plan: InnovationPlan, fork_url: str,
                    readme_content: str = "") -> str:
    branch = f"innovation/{_slugify(plan.description[:40])}"

    _git_run(["git", "checkout", "-B", branch], cwd=repo_path, timeout=30)

    if readme_content:
        readme_path = Path(repo_path) / "README.md"
        readme_path.write_text(readme_content, encoding="utf-8")

    _git_run(["git", "add", "."], cwd=repo_path, timeout=30)

    diff_result = _git_run(["git", "diff", "--staged", "--quiet"], cwd=repo_path, timeout=30)
    if diff_result.returncode == 0:
        logger.info("  No changes to commit")
        return fork_url

    commit_msg = f"feat: {plan.description[:100]}"
    _git_run(
        ["git", "commit", "-m", commit_msg,
         "-m", f"AI-generated innovation fork\n\n{plan.rationale[:200]}"],
        cwd=repo_path, timeout=30,
    )

    result = _git_run(
        ["git", "push", "-u", "origin", branch],
        cwd=repo_path, timeout=120,
    )
    logger.info("  Push: exit=%s", result.returncode)
    if result.stderr:
        logger.info("  Push stderr: %s", result.stderr[:300])
    if result.returncode == 0:
        return f"{fork_url}/tree/{branch}"
    return fork_url


def _remove_readonly(func, path, _):
    os.chmod(path, stat.S_IWRITE)
    func(path)


def cleanup(repo_path: str):
    if not Path(repo_path).exists():
        return
    for _ in range(3):
        try:
            shutil.rmtree(repo_path, onerror=_remove_readonly)
            return
        except Exception:
            import time
            time.sleep(0.5)


def _slugify(text: str) -> str:
    return "".join(c if c.isalnum() or c in "-_" else "-" for c in text.lower()).strip("-")[:30]
