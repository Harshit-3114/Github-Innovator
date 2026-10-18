# github innovator Readme

AI agent that discovers popular GitHub repos, analyzes them with LLM, plans innovations, rewrites code (80-90%+ different from original), runs tests, and publishes forks — fully autonomously.

## How it works

```
Discover repos → Filter by quality → LLM analyze → Fork & clone → Rewrite code → Run tests → Generate README → Push fork
```

Uses **MiniMax M2.7** via **NVIDIA NIM** for all LLM calls and **LangGraph** for the workflow pipeline.

## Commands

| Command | Description |
|---|---|
| `innovator run` | Run pipeline once (headless) |
| `innovator tui` | Launch interactive TUI dashboard |
| `innovator history` | Show recent runs as a table |
| `innovator retry` | Re-commit changes to previously forked repos |
| `innovator daemon` | Run pipeline in a loop every N hours |

## Setup

```bash
pip install -e .

# Windows PowerShell:
Copy-Item .env.example .env
# macOS/Linux:
cp .env.example .env
```

Edit `.env`:

```
NIM_API_KEY=your_nvidia_nim_key
GITHUB_TOKEN=your_github_pat
```

## TUI

If installed (`pip install -e .`), the `innovator` command is on your PATH:

```bash
innovator tui
```

Otherwise run it directly:

```powershell
# Windows PowerShell:
python -m cli.main tui

# macOS/Linux:
python -m cli.main tui
```

Keyboard shortcuts: `R` run, `H` history, `Q` quit. Live log streaming, stats panel, and run history in a scrollable table.

When you hit **Run Pipeline**, it asks **how many repos to fork** — enter a number to cap the run, or `0` to fork all qualified repos. Next it asks **which LLM model to use**, listing every model available on NVIDIA NIM (fetched live from the API) — pick any, or keep the default.

## Pipeline steps

1. **Discover** — Searches GitHub for small/niche repos (CLI tools, productivity, automation)
2. **Filter** — Stars 3–500, permissive license, supported language (Python/JS/TS/Go/Rust), has description
3. **Analyze** — LLM scores each repo on 6 dimensions (AI potential, modernization, platform extension, UI addition, performance, feature gap)
4. **Fork** — Creates `{repo}-ai` fork under your GitHub account
5. **Rewrite** — LLM rewrites most source files with substantial improvements (80-90%+ different from upstream)
   (fork count is capped by the number you enter at the start, `0` = all qualified)
6. **Test** — Runs `pytest` / `npm test` / `go test` / `cargo test` before committing
7. **Publish** — Commits to a branch and pushes the fork

## Project structure

```
github-innovator/
  cli/          # Typer CLI (run, tui, history, retry, daemon)
  tui/          # Textual TUI dashboard
  core/         # Config, GitHub client, LLM client, models, validator
  agents/       # LangGraph pipeline nodes
    graph.py      # Workflow definition and pipeline runner
    discovery.py  # GitHub search and quality filtering
    analyzer.py   # LLM-based repo scoring
    code_indexer.py  # Project structure analysis
    planner.py      # Innovation plan generation
    code_writer.py  # Code generation and file writing
    publisher.py    # Git fork, commit, push
    readme_gen.py   # README generation
  db/           # SQLite schema and repository
  prompts/      # LLM prompt templates
  tests/        # Pytest suite (34 tests)
```

## Configuration

All settings in `core/config.py`:

- `NIM_MODEL` — LLM model (default: `minimaxai/minimax-m2.7`); can be overridden per-run from the TUI model picker
- `MIN_STARS` / `MAX_STARS` — Star range for target repos
- `SUPPORTED_LANGUAGES` — Python, JavaScript, TypeScript, Go, Rust
- `LICENSES_ALLOWED` — Permissive open-source licenses
- `INNOVATION_SCORE_THRESHOLD` — Minimum LLM score to fork (default: 5)

## Tests

```bash
pytest tests/
```
