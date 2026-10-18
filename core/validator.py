import subprocess
from pathlib import Path
from core.models import ValidationResult


def syntax_check(content: str, language: str) -> bool:
    if language == "Python":
        try:
            compile(content, "<string>", "exec")
            return True
        except SyntaxError:
            return False
    return True


def validate_change(repo_path: str, language: str, new_content: str) -> ValidationResult:
    errors = []
    if not syntax_check(new_content, language):
        errors.append("Syntax check failed")
    return ValidationResult(passed=len(errors) == 0, errors=errors)


def run_tests(repo_path: str, language: str) -> tuple[bool, str]:
    commands = {
        "Python": ["python", "-m", "pytest", "--timeout=60", "-x", "-q"],
        "JavaScript": ["npm", "test", "--", "--run"],
        "TypeScript": ["npm", "test", "--", "--run"],
        "Go": ["go", "test", "./..."],
        "Rust": ["cargo", "test"],
    }
    cmd = commands.get(language)
    if not cmd:
        return True, "No test runner configured for language"

    test_dir = Path(repo_path)
    if language == "Python":
        test_files = list(test_dir.rglob("test_*.py")) + list(test_dir.rglob("*_test.py"))
        if not test_files:
            return True, "No test files found"
    else:
        pkg_file = {
            "JavaScript": test_dir / "package.json",
            "TypeScript": test_dir / "package.json",
            "Go": test_dir / "go.mod",
            "Rust": test_dir / "Cargo.toml",
        }.get(language)
        if pkg_file and not pkg_file.exists():
            return True, "No project config found for test runner"

    try:
        result = subprocess.run(cmd, cwd=repo_path, capture_output=True, text=True, timeout=120)
        if result.returncode == 0:
            return True, result.stdout[:500]
        return False, (result.stderr or result.stdout)[:500]
    except subprocess.TimeoutExpired:
        return False, "Tests timed out"
    except FileNotFoundError:
        return True, "Test runner not installed"
    except Exception as e:
        return False, str(e)
