from unittest.mock import Mock
from core.models import RepoInfo
from agents.discovery import filter_repos


def make_repo(
    full_name="owner/repo",
    stars=50,
    language="Python",
    license_key="mit",
    description="A useful CLI tool",
    topics=None,
) -> RepoInfo:
    return RepoInfo(
        full_name=full_name,
        owner=full_name.split("/")[0],
        name=full_name.split("/")[1],
        description=description,
        language=language,
        stars=stars,
        topics=topics or [],
        license_key=license_key,
        pushed_at="2024-01-01T00:00:00",
        clone_url=f"https://github.com/{full_name}.git",
        size_bytes=1024,
    )


class TestFilterRepos:
    def test_passes_valid_repo(self):
        repos = [make_repo()]
        gh = Mock()
        result = filter_repos(repos, gh)
        assert len(result) == 1

    def test_rejects_low_stars(self):
        repos = [make_repo(stars=1)]
        gh = Mock()
        result = filter_repos(repos, gh)
        assert len(result) == 0

    def test_rejects_high_stars(self):
        repos = [make_repo(stars=1000)]
        gh = Mock()
        result = filter_repos(repos, gh)
        assert len(result) == 0

    def test_rejects_unsupported_language(self):
        repos = [make_repo(language="Ruby")]
        gh = Mock()
        result = filter_repos(repos, gh)
        assert len(result) == 0

    def test_rejects_restrictive_license(self):
        repos = [make_repo(license_key="gpl-3.0")]
        gh = Mock()
        result = filter_repos(repos, gh)
        assert len(result) == 0

    def test_rejects_empty_description(self):
        repos = [make_repo(description="")]
        gh = Mock()
        result = filter_repos(repos, gh)
        assert len(result) == 0

    def test_rejects_short_description(self):
        repos = [make_repo(description="Hi")]
        gh = Mock()
        result = filter_repos(repos, gh)
        assert len(result) == 0

    def test_mixed_repos(self):
        repos = [
            make_repo(full_name="a/valid", stars=50),
            make_repo(full_name="b/low_stars", stars=1),
            make_repo(full_name="c/bad_license", license_key="gpl-3.0"),
            make_repo(full_name="d/ruby", language="Ruby"),
        ]
        gh = Mock()
        result = filter_repos(repos, gh)
        assert len(result) == 1
        assert result[0].full_name == "a/valid"

    def test_empty_list(self):
        gh = Mock()
        result = filter_repos([], gh)
        assert result == []
