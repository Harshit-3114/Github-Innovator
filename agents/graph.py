import logging
from datetime import datetime
from typing import Literal
from langgraph.graph import StateGraph, END
from core.models import InnovationState
from core.github_client import GitHubClient
from core.llm_client import nim
from agents.discovery import discover_repos, filter_repos
from agents.analyzer import run_analysis
from agents.code_indexer import build_code_graph
from agents.planner import generate_innovation_plan
from agents.code_writer import execute_plan
from agents.publisher import fork_and_clone, commit_and_push, cleanup
from agents.readme_gen import generate_readme
from core.validator import run_tests
from db.schema import init_db
from db.repository import create_run_log, complete_run_log, mark_repo_processed

logger = logging.getLogger(__name__)

_cloned_path: str = ""


def _log(msg: str) -> None:
    logger.info(msg)


def _heading(label: str) -> None:
    logger.info("━━━ %s ━━━", label)


def node_discover(state: InnovationState) -> dict:
    _heading("Discovering repos")
    gh = GitHubClient()
    repos = discover_repos(gh)
    processed = state["processed_full_names"]
    filtered = [r for r in repos if r.full_name not in processed]
    _log(f"Found {len(repos)} repos from search, {len(filtered)} not previously forked")
    qualified_list = filter_repos(filtered, gh)
    _log(f"After quality filters: {len(qualified_list)} candidates")

    max_repos = state.get("max_repos", 0) or 0
    candidates = qualified_list
    _log(f"Analyzing {len(candidates)} repos with LLM...")
    qualified = run_analysis(candidates)
    _log(f"LLM qualified {len(qualified)} repos")
    if max_repos > 0:
        qualified = qualified[:max_repos]
        _log(f"Forking top {len(qualified)} repos (user limit: {max_repos})")
    return {
        "candidate_repos": candidates,
        "innovation_opportunities": qualified,
        "run_metadata": {"discovered": len(candidates), "qualified": len(qualified), "started_at": datetime.now().isoformat()},
    }


def node_code_index(state: InnovationState) -> dict:
    global _cloned_path
    _heading("Indexing codebase")
    qualified = state["innovation_opportunities"]
    if not qualified:
        _log("No qualified repos to index")
        return {}

    idx = state.get("current_index", 0)
    if idx >= len(qualified):
        _log("All repos processed")
        return {}
    repo = qualified[idx]
    _log(f"Processing repo {idx + 1}/{len(qualified)}: {repo.repo.full_name} (score: {repo.score})")
    gh = GitHubClient()
    _log(f"Forking and cloning {repo.repo.full_name}...")
    result = fork_and_clone(gh, repo.repo.full_name)
    if not result:
        _log(f"Failed to fork/clone {repo.repo.full_name}, skipping")
        return {}

    repo_path, fork_url = result
    _cloned_path = repo_path
    _log(f"Forked and cloned to {repo_path}")
    _log("Building code graph (extracting imports, classes, functions)...")
    code_graph = build_code_graph(repo_path, repo.repo.language)
    _log(f"Code graph built: {len(code_graph.files)} files indexed")
    return {
        "current_repo": repo,
        "code_graph": code_graph,
        "fork_url": fork_url,
        "retry_count": 0,
        "run_metadata": {**state["run_metadata"], "cloned_path": repo_path, "cloned_repo": repo.repo.full_name},
    }


def node_plan(state: InnovationState) -> dict:
    _heading("Planning innovation")
    repo = state["current_repo"]
    code_graph = state["code_graph"]
    if not repo or not code_graph:
        _log("No repo or code graph available for planning")
        return {}
    _log(f"Generating innovation plan for {repo.repo.full_name}...")
    plan = generate_innovation_plan(repo, code_graph)
    retry = state.get("retry_count", 0) + 1
    if retry > 1:
        _log(f"Retry attempt {retry}/3")
    changes_count = len(plan.changes) if plan else 0
    _log(f"Plan generated: {changes_count} file changes proposed")
    return {"innovation_plan": plan, "retry_count": retry}


def node_implement(state: InnovationState) -> dict:
    _heading("Writing code changes")
    repo = state["current_repo"]
    plan = state["innovation_plan"]
    code_graph = state["code_graph"]
    if not repo or not plan or not code_graph:
        _log("Missing repo, plan, or code graph — skipping implementation")
        return {}

    repo_path = state["run_metadata"].get("cloned_path", "")
    if not repo_path:
        _log("No repo path available for implementation")
        return {}

    _log("Executing code changes via MiniMax M2.7...")
    changes = execute_plan(repo, plan, code_graph, repo_path)
    _log(f"Generated {len(changes)} changed file(s)")
    for c in changes:
        _log(f"  {c.file} ({c.language}, {len(c.new_content)} chars)")
    return {"changed_files": changes}


def node_validate(state: InnovationState) -> dict:
    _heading("Validating changes")
    from core.validator import validate_change
    changes = state["changed_files"]
    repo_path = state["run_metadata"].get("cloned_path", "")

    if not changes:
        _log("No changes to validate")
        return {"validation_results": []}

    _log(f"Validating {len(changes)} change(s) (syntax only)...")
    results = []
    for i, change in enumerate(changes):
        result = validate_change(repo_path, change.language, change.new_content)
        if result.passed:
            _log(f"  [{i+1}/{len(changes)}] {change.file} — OK")
        else:
            detail = f" — {'; '.join(result.errors)}" if result.errors else ""
            _log(f"  [{i+1}/{len(changes)}] {change.file} — SYNTAX ERROR{detail}")
        results.append(result)

    passed = sum(1 for r in results if r.passed)
    _log(f"Validation: {passed}/{len(results)} passed")
    return {"validation_results": results}


def node_test(state: InnovationState) -> dict:
    _heading("Running tests")
    repo = state["current_repo"]
    repo_path = state["run_metadata"].get("cloned_path", "")
    if not repo or not repo_path:
        _log("No repo or path for testing")
        return {"tests_passed": True}
    _log(f"Running tests for {repo.repo.language} project...")
    passed, output = run_tests(repo_path, repo.repo.language)
    if passed:
        _log("All tests passed")
    else:
        _log(f"Tests failed: {output[:200]}")
    return {"tests_passed": passed, "test_output": output}


def decide_retry_or_publish(state: InnovationState) -> Literal["retry", "publish", "abandon"]:
    results = state["validation_results"]
    retry_count = state.get("retry_count", 0)
    changes = state["changed_files"]

    all_passed = all(r.passed for r in results) if results else False
    no_changes = not changes

    if all_passed:
        _log("All validations passed — proceeding to test")
        return "publish"
    if no_changes:
        _log("No changes generated — abandoning")
        return "abandon"
    if retry_count < 3:
        _log(f"Some validations failed — retrying (attempt {retry_count + 1}/3)")
        return "retry"
    _log("Max retries reached — abandoning")
    return "abandon"


def decide_test_or_abandon(state: InnovationState) -> Literal["readme_gen", "abandon"]:
    tests_passed = state.get("tests_passed", True)
    if tests_passed:
        _log("Tests passed — proceeding to publish")
        return "readme_gen"
    _log("Tests failed — abandoning repo")
    return "abandon"


def node_readme_gen(state: InnovationState) -> dict:
    _heading("Generating README")
    repo = state["current_repo"]
    plan = state["innovation_plan"]
    if not repo or not plan:
        _log("No repo or plan for README generation")
        return {}

    fork_name = f"{repo.repo.name}-ai"
    _log(f"Generating README for fork '{fork_name}'...")
    readme = generate_readme(repo, plan, fork_name)
    _log(f"README generated ({len(readme)} chars)")
    return {"readme_content": readme}


def node_publish(state: InnovationState) -> dict:
    _heading("Publishing fork")
    repo = state["current_repo"]
    plan = state["innovation_plan"]
    readme = state.get("readme_content", "")
    repo_path = state["run_metadata"].get("cloned_path", "")
    fork_url = state.get("fork_url", "")
    if not repo or not plan or not repo_path:
        _log("No repo or plan to publish")
        return {}

    _log("Committing and pushing changes to fork...")
    result_url = commit_and_push(repo_path, plan, fork_url, readme_content=readme)
    if result_url and "/tree/" in result_url:
        _log(f"Changes pushed: {result_url}")
    elif result_url:
        _log(f"Fork exists at {result_url} (no new changes)")
    else:
        _log("Publish failed")
    return {"fork_url": result_url}


def node_record(state: InnovationState) -> dict:
    _heading("Recording results")
    repo = state["current_repo"]
    fork_url = state.get("fork_url", "")

    if repo and fork_url:
        mark_repo_processed(
            repo.repo.full_name, repo.repo.stars, repo.repo.language,
            repo.repo.license_key, repo.score, repo.best_innovation,
            fork_url=fork_url, status="forked",
        )
        _log(f"Recorded {repo.repo.full_name} → {fork_url}")
    elif repo:
        _log(f"No fork created for {repo.repo.full_name} — recording as skipped")

    meta = dict(state["run_metadata"])
    meta["fork_url"] = fork_url
    meta["retries"] = state.get("retry_count", 0)
    return {"run_metadata": meta}


def node_cleanup(state: InnovationState) -> dict:
    repo_path = state["run_metadata"].get("cloned_path", "")
    if repo_path:
        try:
            cleanup(repo_path)
            _log(f"Cleaned up {repo_path}")
        except Exception as e:
            logger.warning(f"Cleanup failed: {e}")
    idx = state.get("current_index", 0) + 1
    return {"current_index": idx}


def decide_next(state: InnovationState) -> Literal["code_index", "record_done"]:
    idx = state.get("current_index", 0)
    qualified = state.get("innovation_opportunities", [])
    if idx < len(qualified):
        _log(f"\n=== Next repo: {idx + 1}/{len(qualified)} ===")
        return "code_index"
    _log("All qualified repos processed")
    return "record_done"


def node_record_done(state: InnovationState) -> dict:
    _heading("Run complete")
    return {}


def build_workflow() -> StateGraph:
    workflow = StateGraph(InnovationState)

    workflow.add_node("discover", node_discover)
    workflow.add_node("code_index", node_code_index)
    workflow.add_node("plan", node_plan)
    workflow.add_node("implement", node_implement)
    workflow.add_node("validate", node_validate)
    workflow.add_node("test", node_test)
    workflow.add_node("readme_gen", node_readme_gen)
    workflow.add_node("publish", node_publish)
    workflow.add_node("record", node_record)
    workflow.add_node("cleanup", node_cleanup)
    workflow.add_node("record_done", node_record_done)

    workflow.set_entry_point("discover")
    workflow.add_conditional_edges(
        "discover",
        lambda s: "code_index" if s.get("innovation_opportunities") else "record_done",
        {"code_index": "code_index", "record_done": "record_done"},
    )
    workflow.add_edge("code_index", "plan")
    workflow.add_edge("plan", "implement")
    workflow.add_edge("implement", "validate")
    workflow.add_conditional_edges(
        "validate",
        decide_retry_or_publish,
        {"retry": "plan", "publish": "test", "abandon": "record"},
    )
    workflow.add_conditional_edges(
        "test",
        decide_test_or_abandon,
        {"readme_gen": "readme_gen", "abandon": "record"},
    )
    workflow.add_edge("readme_gen", "publish")
    workflow.add_edge("publish", "record")
    workflow.add_edge("record", "cleanup")
    workflow.add_conditional_edges(
        "cleanup",
        decide_next,
        {"code_index": "code_index", "record_done": "record_done"},
    )
    workflow.add_edge("record_done", END)

    return workflow.compile()


def run_pipeline(max_repos: int = 0, model: str | None = None) -> dict:
    global _cloned_path
    _cloned_path = ""
    init_db()
    run_id = create_run_log()
    _log("=" * 60)
    _log(f"Innovation Fork Agent — Run #{run_id}")
    _log(f"Started at {datetime.now():%Y-%m-%d %H:%M:%S}")
    if model:
        nim.set_model(model)
        _log(f"Using model: {model}")
    else:
        _log(f"Using model: {nim.model}")
    if max_repos > 0:
        _log(f"User requested {max_repos} repo(s)")
    _log("=" * 60)

    graph = build_workflow()
    initial_state: InnovationState = {
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
        "run_metadata": {"run_id": run_id},
        "max_repos": max_repos,
    }

    try:
        final = graph.invoke(initial_state, {"recursion_limit": 100})
    except Exception as e:
        logger.exception("Pipeline failed")
        _log(f"Pipeline failed: {e}")
        complete_run_log(
            run_id=run_id, repos_discovered=0, repos_qualified=0,
            forks_created=0, forks_succeeded=0, total_api_calls=0,
            status="failed", error=str(e),
        )
        return {"run_id": run_id, "status": "failed", "error": str(e)}
    finally:
        if _cloned_path:
            try:
                cleanup(_cloned_path)
            except Exception:
                pass

    meta = final.get("run_metadata", {})
    fork_url = final.get("fork_url", "")
    complete_run_log(
        run_id=run_id,
        repos_discovered=meta.get("discovered", 0),
        repos_qualified=meta.get("qualified", 0),
        forks_created=1 if fork_url else 0,
        forks_succeeded=1 if fork_url else 0,
        total_api_calls=meta.get("discovered", 0) + meta.get("qualified", 0) + 10,
    )

    _log("=" * 60)
    _log(f"Run #{run_id} complete")
    _log(f"  Discovered: {meta.get('discovered', 0)} repos")
    _log(f"  Qualified:  {meta.get('qualified', 0)} repos")
    if fork_url:
        _log(f"  Latest fork: {fork_url}")
    else:
        _log("  Fork URL: (none)")
    return {
        "run_id": run_id,
        "status": "completed",
        "fork_url": fork_url,
        "repos_discovered": meta.get("discovered", 0),
        "repos_qualified": meta.get("qualified", 0),
        "retries": meta.get("retries", 0),
    }
