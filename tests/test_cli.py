import pytest
from typer.testing import CliRunner
from sourcegraph_search.cli import app
import sourcegraph_search.cli as cli
from sourcegraph_search.models import (
    SearchResults,
    FileMatchResult,
    TreeEntry,
    CodeIntelResult,
    CodeIntelLocation,
)

runner = CliRunner()


class DummyClient:
    def __init__(self, endpoint, token, timeout):
        self.endpoint = endpoint
        self.token = token
        self.timeout = timeout

    def search(self, query, fetch_content=False):
        return SearchResults(
            match_count=1,
            result_count=1,
            limit_hit=False,
            items=[
                FileMatchResult(
                    repository="github.com/mock/repo",
                    path="test.py",
                    url="/url",
                    content="print('hello')" if fetch_content else "",
                    line_matches=[],
                    symbols=[],
                )
            ],
        )

    def get_file_content(self, repo, path, rev="HEAD"):
        return f"content of {path} in {repo} at {rev}"

    def get_file_tree(self, repo, path="", rev="HEAD"):
        return [
            TreeEntry(name="dummy.py", path="dummy.py", is_directory=False, url="/url")
        ]

    def get_code_intel(self, repo, path, line, character, rev="HEAD"):
        return CodeIntelResult(
            definitions=[
                CodeIntelLocation(
                    repository=repo,
                    path="def.py",
                    line=line + 1,
                    character=character + 1,
                    url="/def",
                )
            ],
            references=[],
        )

    def close(self):
        pass


@pytest.fixture
def mock_cli_client(monkeypatch):
    monkeypatch.setattr(cli, "CLIENT_FACTORY", DummyClient)


def test_cli_search(mock_cli_client):
    result = runner.invoke(app, ["search", "query-test"])
    assert result.exit_code == 0
    assert "github.com/mock/repo/test.py" in result.stdout


def test_cli_fetch(mock_cli_client):
    result = runner.invoke(app, ["fetch", "my-repo", "file.py"])
    assert result.exit_code == 0
    assert "content of file.py in my-repo at HEAD" in result.stdout


def test_cli_tree(mock_cli_client):
    result = runner.invoke(app, ["tree", "my-repo"])
    assert result.exit_code == 0
    assert "📄 dummy.py" in result.stdout


def test_cli_define(mock_cli_client):
    result = runner.invoke(app, ["define", "my-repo", "main.py", "10", "5"])
    assert result.exit_code == 0
    # Line and character should be correctly formatted
    assert "my-repo/def.py#L10:5" in result.stdout


def test_cli_refs(mock_cli_client):
    result = runner.invoke(app, ["refs", "my-repo", "main.py", "10", "5"])
    assert result.exit_code == 0
    assert "No references found." in result.stdout
