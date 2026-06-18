import pytest
from unittest.mock import MagicMock
from sourcegraph_search.client import SourcegraphClient, SourcegraphError
from sourcegraph_search.models import (
    SearchResults, FileMatchResult, CommitResult, RepositoryResult, TreeEntry, CodeIntelResult
)

def test_client_init():
    client = SourcegraphClient(endpoint="https://test.sourcegraph.com", token="my-token", timeout=10.0)
    assert client.endpoint == "https://test.sourcegraph.com"
    assert client.token == "my-token"
    assert client.timeout == 10.0

def test_post_graphql_success(mocker):
    client = SourcegraphClient()
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"data": {"foo": "bar"}}
    
    mock_post = mocker.patch("httpx.Client.post", return_value=mock_response)
    
    res = client._post_graphql("query { foo }", {})
    assert res == {"data": {"foo": "bar"}}
    mock_post.assert_called_once()

def test_post_graphql_non_200(mocker):
    client = SourcegraphClient()
    mock_response = MagicMock()
    mock_response.status_code = 500
    mock_response.text = "Internal Server Error"
    
    mocker.patch("httpx.Client.post", return_value=mock_response)
    
    with pytest.raises(SourcegraphError) as exc_info:
        client._post_graphql("query { foo }", {})
    assert "Request failed with status code 500" in str(exc_info.value)

def test_post_graphql_api_errors(mocker):
    client = SourcegraphClient()
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"errors": [{"message": "Some API error"}]}
    
    mocker.patch("httpx.Client.post", return_value=mock_response)
    
    with pytest.raises(SourcegraphError) as exc_info:
        client._post_graphql("query { foo }", {})
    assert "GraphQL Error: Some API error" in str(exc_info.value)

def test_search_parsing(mocker):
    client = SourcegraphClient()
    mock_data = {
        "data": {
            "search": {
                "results": {
                    "matchCount": 3,
                    "resultCount": 3,
                    "limitHit": False,
                    "results": [
                        {
                            "__typename": "FileMatch",
                            "repository": {"name": "github.com/test/repo"},
                            "file": {"path": "main.py", "url": "/url", "content": "print('hello')"},
                            "lineMatches": [{"lineNumber": 1, "preview": "print('hello')"}],
                            "symbols": [{"name": "hello", "kind": "FUNCTION", "containerName": "main", "url": "/sym_url"}]
                        },
                        {
                            "__typename": "CommitSearchResult",
                            "commit": {
                                "oid": "1234567890abcdef",
                                "message": "commit msg\ndetails",
                                "author": {"person": {"name": "Alice"}, "date": "2026-06-18"},
                                "repository": {"name": "github.com/test/repo"}
                            },
                            "url": "/commit_url"
                        },
                        {
                            "__typename": "Repository",
                            "name": "github.com/test/repo",
                            "url": "/repo_url"
                        }
                    ]
                }
            }
        }
    }
    
    mocker.patch.object(client, "_post_graphql", return_value=mock_data)
    
    res = client.search("test")
    assert isinstance(res, SearchResults)
    assert res.match_count == 3
    assert len(res.items) == 3
    
    # Assert FileMatchResult
    assert isinstance(res.items[0], FileMatchResult)
    assert res.items[0].repository == "github.com/test/repo"
    assert res.items[0].path == "main.py"
    assert len(res.items[0].line_matches) == 1
    assert len(res.items[0].symbols) == 1
    
    # Assert CommitResult
    assert isinstance(res.items[1], CommitResult)
    assert res.items[1].oid == "1234567890abcdef"
    assert res.items[1].message == "commit msg\ndetails"
    assert res.items[1].author_name == "Alice"
    
    # Assert RepositoryResult
    assert isinstance(res.items[2], RepositoryResult)
    assert res.items[2].name == "github.com/test/repo"

def test_get_file_content(mocker):
    client = SourcegraphClient()
    mock_data = {
        "data": {
            "repository": {
                "commit": {
                    "file": {
                        "content": "file contents"
                    }
                }
            }
        }
    }
    mocker.patch.object(client, "_post_graphql", return_value=mock_data)
    
    content = client.get_file_content("repo", "path.txt")
    assert content == "file contents"

def test_get_file_tree(mocker):
    client = SourcegraphClient()
    mock_data = {
        "data": {
            "repository": {
                "commit": {
                    "tree": {
                        "entries": [
                            {"name": "src", "path": "src", "isDirectory": True, "url": "/src"},
                            {"name": "main.py", "path": "main.py", "isDirectory": False, "url": "/main.py"}
                        ]
                    }
                }
            }
        }
    }
    mocker.patch.object(client, "_post_graphql", return_value=mock_data)
    
    entries = client.get_file_tree("repo")
    assert len(entries) == 2
    assert isinstance(entries[0], TreeEntry)
    assert entries[0].name == "src"
    assert entries[0].is_directory is True
    assert entries[1].name == "main.py"
    assert entries[1].is_directory is False

def test_get_code_intel(mocker):
    client = SourcegraphClient()
    mock_data = {
        "data": {
            "repository": {
                "commit": {
                    "blob": {
                        "lsif": {
                            "definitions": {
                                "nodes": [
                                    {
                                        "resource": {"path": "def.py", "repository": {"name": "repo"}},
                                        "range": {"start": {"line": 10, "character": 5}},
                                        "url": "/def"
                                    }
                                ]
                            },
                            "references": {
                                "nodes": [
                                    {
                                        "resource": {"path": "ref.py", "repository": {"name": "repo"}},
                                        "range": {"start": {"line": 20, "character": 8}},
                                        "url": "/ref"
                                    }
                                ]
                            }
                        }
                    }
                }
            }
        }
    }
    mocker.patch.object(client, "_post_graphql", return_value=mock_data)
    
    res = client.get_code_intel("repo", "main.py", 10, 5)
    assert isinstance(res, CodeIntelResult)
    assert len(res.definitions) == 1
    # Check 1-indexed conversion (0-indexed 10 becomes 11)
    assert res.definitions[0].line == 11
    assert res.definitions[0].character == 6
    assert len(res.references) == 1
    assert res.references[0].line == 21
