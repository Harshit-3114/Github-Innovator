import re
from pathlib import Path
from core.models import CodeGraph, FileInfo, FunctionDef, ClassDef

SKIP_DIRS = {".git", "__pycache__", "node_modules", "venv", ".venv", "target", "vendor", "dist", "build", ".eggs"}


def build_code_graph(repo_path: str, language: str) -> CodeGraph:
    graph = CodeGraph(repo_path=repo_path)
    repo = Path(repo_path)

    extensions = _extensions_for_language(language)

    for file_path in repo.rglob("*"):
        if not file_path.is_file():
            continue
        if file_path.suffix not in extensions:
            continue
        if any(part in SKIP_DIRS for part in file_path.parts):
            continue

        try:
            content = file_path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue

        rel_path = str(file_path.relative_to(repo))
        line_count = len(content.splitlines())

        graph.files.append(FileInfo(path=rel_path, language=language, line_count=line_count))
        graph.imports[rel_path] = _extract_imports(content, language)
        graph.functions[rel_path] = _extract_functions(content, language)
        graph.classes[rel_path] = _extract_classes(content, language)

        if file_path.name in ("__init__.py", "main.py", "index.js", "main.go", "main.rs", "cli.py", "cli.js"):
            graph.entry_points.append(rel_path)

        if file_path.name in ("pyproject.toml", "setup.py", "package.json", "Cargo.toml", "go.mod"):
            graph.config_files.append(rel_path)

        if "test" in file_path.name.lower() or file_path.name.startswith("test_"):
            graph.test_files.append(rel_path)

    return graph


def _extensions_for_language(language: str) -> set[str]:
    mapping = {
        "Python": {".py"},
        "JavaScript": {".js", ".jsx", ".mjs"},
        "TypeScript": {".ts", ".tsx"},
        "Go": {".go"},
        "Rust": {".rs"},
    }
    return mapping.get(language, {".py"})


def _extract_imports(content: str, language: str) -> set[str]:
    imports = set()
    if language == "Python":
        for m in re.finditer(r"^(?:import|from)\s+(\S+)", content, re.MULTILINE):
            imports.add(m.group(1).split(".")[0])
    elif language in ("JavaScript", "TypeScript"):
        for m in re.finditer(r"(?:import|require)\s*\(?['\"]([^'\"\/]+)", content):
            imports.add(m.group(1))
    elif language == "Go":
        for m in re.finditer(r'\"([\w\/]+)\"', content):
            imports.add(m.group(1).split("/")[0])
    return imports


def _extract_functions(content: str, language: str) -> list[FunctionDef]:
    functions = []
    if language == "Python":
        for m in re.finditer(r"^def\s+(\w+)\s*\(", content, re.MULTILINE):
            start = content[:m.start()].count("\n") + 1
            functions.append(FunctionDef(name=m.group(1), start_line=start, end_line=start))
    elif language in ("JavaScript", "TypeScript"):
        for m in re.finditer(r"(?:function\s+(\w+)|(\w+)\s*=\s*(?:async\s*)?\(|(\w+)\s*\([^)]*\)\s*{)", content):
            name = m.group(1) or m.group(2) or m.group(3) or "anon"
            start = content[:m.start()].count("\n") + 1
            functions.append(FunctionDef(name=name, start_line=start, end_line=start))
    return functions


def _extract_classes(content: str, language: str) -> list[ClassDef]:
    classes = []
    if language == "Python":
        for m in re.finditer(r"^class\s+(\w+)", content, re.MULTILINE):
            start = content[:m.start()].count("\n") + 1
            classes.append(ClassDef(name=m.group(1), start_line=start, end_line=start))
    return classes
