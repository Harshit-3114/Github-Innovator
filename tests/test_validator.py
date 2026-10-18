from core.validator import syntax_check, validate_change


class TestSyntaxCheck:
    def test_valid_python(self):
        assert syntax_check("x = 1\ny = 2\nprint(x + y)", "Python") is True

    def test_invalid_python(self):
        assert syntax_check("x = ", "Python") is False

    def test_syntax_error(self):
        assert syntax_check("def foo(:", "Python") is False

    def test_empty_string(self):
        assert syntax_check("", "Python") is True

    def test_other_language_passthrough(self):
        assert syntax_check("some random javascript code;;;", "JavaScript") is True
        assert syntax_check("fn main() {", "Rust") is True
        assert syntax_check("package main", "Go") is True

    def test_class_definition(self):
        code = "class Foo:\n    def bar(self):\n        pass"
        assert syntax_check(code, "Python") is True

    def test_import_syntax(self):
        code = "import os\nfrom pathlib import Path"
        assert syntax_check(code, "Python") is True


class TestValidateChange:
    def test_valid_change(self):
        result = validate_change("/tmp", "Python", "x = 1")
        assert result.passed is True
        assert result.errors == []

    def test_invalid_change(self):
        result = validate_change("/tmp", "Python", "x = ")
        assert result.passed is False
        assert "Syntax check failed" in result.errors

    def test_non_python_passthrough(self):
        result = validate_change("/tmp", "Rust", "fn main() {")
        assert result.passed is True
        assert result.errors == []
