import pytest
from sourcegraph_search.parsers import (
    parse_search_response,
    parse_file_content_response,
    parse_file_tree_response,
    parse_code_intel_response,
)
from sourcegraph_search.exceptions import (
    APIError,
    ResponseParseError,
)
from sourcegraph_search.models import (
    SearchResults,
    FileMatchResult,
    TreeEntry,
    CodeIntelResult,
)


def test_parse_search_response_success():
    data = {
        "data": {
            "search": {
                "results": {
                    "matchCount": 1,
                    "resultCount": 1,
                    "limitHit": False,
                    "results": [
                        {
                            "__typename": "FileMatch",
                            "repository": {"name": "github.com/test/repo"},
                            "file": {"path": "main.py", "url": "/url"},
                            "lineMatches": [
                                {"lineNumber": 10, "preview": "def foo():"}
                            ],
                            "symbols": [
                                {"name": "foo", "kind": "FUNCTION", "url": "/url/foo"}
                            ],
                        }
                    ],
                }
            }
        }
    }
    results = parse_search_response(data)
    assert isinstance(results, SearchResults)
    assert results.match_count == 1
    assert len(results.items) == 1
    assert isinstance(results.items[0], FileMatchResult)
    assert results.items[0].repository == "github.com/test/repo"
    assert results.items[0].path == "main.py"


def test_parse_search_response_malformed():
    data = {"data": {"search": None}}
    with pytest.raises(ResponseParseError):
        parse_search_response(data)


def test_parse_file_content_success():
    data = {"data": {"repository": {"commit": {"file": {"content": "hello world"}}}}}
    content = parse_file_content_response(data, "repo", "main", "file.py")
    assert content == "hello world"


def test_parse_file_content_missing_repo():
    data = {"data": {"repository": None}}
    with pytest.raises(APIError) as exc:
        parse_file_content_response(data, "repo", "main", "file.py")
    assert "Repository not found" in str(exc.value)


def test_parse_file_tree_success():
    data = {
        "data": {
            "repository": {
                "commit": {
                    "tree": {
                        "entries": [
                            {
                                "name": "a.py",
                                "path": "a.py",
                                "isDirectory": False,
                                "url": "/url",
                            }
                        ]
                    }
                }
            }
        }
    }
    entries = parse_file_tree_response(data, "repo", "main", "path")
    assert len(entries) == 1
    assert isinstance(entries[0], TreeEntry)
    assert entries[0].name == "a.py"


def test_parse_code_intel_success():
    data = {
        "data": {
            "repository": {
                "commit": {
                    "blob": {
                        "lsif": {
                            "definitions": {
                                "nodes": [
                                    {
                                        "resource": {
                                            "path": "def.py",
                                            "repository": {"name": "repo"},
                                        },
                                        "range": {"start": {"line": 1, "character": 2}},
                                        "url": "/url",
                                    }
                                ]
                            },
                            "references": {"nodes": []},
                        }
                    }
                }
            }
        }
    }
    result = parse_code_intel_response(data, "repo", "main", "path.py")
    assert isinstance(result, CodeIntelResult)
    assert len(result.definitions) == 1
    assert result.definitions[0].line == 2  # 1-indexed
    assert result.definitions[0].character == 3  # 1-indexed
