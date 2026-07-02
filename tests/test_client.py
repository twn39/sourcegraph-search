import pytest
from unittest.mock import MagicMock
from sourcegraph_search.client import (
    SourcegraphClient,
    AsyncSourcegraphClient,
    APIError,
)
from sourcegraph_search.models import (
    SearchResults,
    FileMatchResult,
    CommitResult,
    RepositoryResult,
    TreeEntry,
    CodeIntelResult,
)


def test_client_init():
    client = SourcegraphClient(
        endpoint="https://test.sourcegraph.com", token="my-token", timeout=10.0
    )
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

    with pytest.raises(APIError) as exc_info:
        client._post_graphql("query { foo }", {})
    assert "Request failed with status code 500" in str(exc_info.value)


def test_post_graphql_api_errors(mocker):
    client = SourcegraphClient()
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"errors": [{"message": "Some API error"}]}

    mocker.patch("httpx.Client.post", return_value=mock_response)

    with pytest.raises(APIError) as exc_info:
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
                            "file": {
                                "path": "main.py",
                                "url": "/url",
                                "content": "print('hello')",
                            },
                            "lineMatches": [
                                {"lineNumber": 1, "preview": "print('hello')"}
                            ],
                            "symbols": [
                                {
                                    "name": "hello",
                                    "kind": "FUNCTION",
                                    "containerName": "main",
                                    "url": "/sym_url",
                                }
                            ],
                        },
                        {
                            "__typename": "CommitSearchResult",
                            "commit": {
                                "oid": "1234567890abcdef",
                                "message": "commit msg\ndetails",
                                "author": {
                                    "person": {"name": "Alice"},
                                    "date": "2026-06-18",
                                },
                                "repository": {"name": "github.com/test/repo"},
                            },
                            "url": "/commit_url",
                        },
                        {
                            "__typename": "Repository",
                            "name": "github.com/test/repo",
                            "url": "/repo_url",
                        },
                    ],
                }
            }
        }
    }

    mock_post = mocker.patch.object(client, "_post_graphql", return_value=mock_data)

    res = client.search("test")
    from sourcegraph_search.queries import GRAPHQL_SEARCH_QUERY

    mock_post.assert_called_once_with(GRAPHQL_SEARCH_QUERY, {"query": "test"})
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
        "data": {"repository": {"commit": {"file": {"content": "file contents"}}}}
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
                            {
                                "name": "src",
                                "path": "src",
                                "isDirectory": True,
                                "url": "/src",
                            },
                            {
                                "name": "main.py",
                                "path": "main.py",
                                "isDirectory": False,
                                "url": "/main.py",
                            },
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
                                        "resource": {
                                            "path": "def.py",
                                            "repository": {"name": "repo"},
                                        },
                                        "range": {
                                            "start": {"line": 10, "character": 5}
                                        },
                                        "url": "/def",
                                    }
                                ]
                            },
                            "references": {
                                "nodes": [
                                    {
                                        "resource": {
                                            "path": "ref.py",
                                            "repository": {"name": "repo"},
                                        },
                                        "range": {
                                            "start": {"line": 20, "character": 8}
                                        },
                                        "url": "/ref",
                                    }
                                ]
                            },
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


def test_client_context_manager(mocker):
    mock_close = mocker.patch("httpx.Client.close")
    with SourcegraphClient():
        pass
    mock_close.assert_called_once()


# ==============================================================================
# AsyncSourcegraphClient Tests
# ==============================================================================


@pytest.mark.anyio
async def test_async_client_init():
    client = AsyncSourcegraphClient(
        endpoint="https://test.sourcegraph.com", token="my-token", timeout=10.0
    )
    assert client.endpoint == "https://test.sourcegraph.com"
    assert client.token == "my-token"
    assert client.timeout == 10.0


@pytest.mark.anyio
async def test_async_post_graphql_success(mocker):
    client = AsyncSourcegraphClient()
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"data": {"foo": "bar"}}

    mock_post = mocker.patch("httpx.AsyncClient.post", return_value=mock_response)

    res = await client._post_graphql("query { foo }", {})
    assert res == {"data": {"foo": "bar"}}
    mock_post.assert_called_once()


@pytest.mark.anyio
async def test_async_post_graphql_non_200(mocker):
    client = AsyncSourcegraphClient()
    mock_response = MagicMock()
    mock_response.status_code = 500
    mock_response.text = "Internal Server Error"

    mocker.patch("httpx.AsyncClient.post", return_value=mock_response)

    with pytest.raises(APIError) as exc_info:
        await client._post_graphql("query { foo }", {})
    assert "Request failed with status code 500" in str(exc_info.value)


@pytest.mark.anyio
async def test_async_post_graphql_api_errors(mocker):
    client = AsyncSourcegraphClient()
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"errors": [{"message": "Some API error"}]}

    mocker.patch("httpx.AsyncClient.post", return_value=mock_response)

    with pytest.raises(APIError) as exc_info:
        await client._post_graphql("query { foo }", {})
    assert "GraphQL Error: Some API error" in str(exc_info.value)


@pytest.mark.anyio
async def test_async_search_parsing(mocker):
    client = AsyncSourcegraphClient()
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
                            "file": {
                                "path": "main.py",
                                "url": "/url",
                                "content": "print('hello')",
                            },
                            "lineMatches": [
                                {"lineNumber": 1, "preview": "print('hello')"}
                            ],
                            "symbols": [
                                {
                                    "name": "hello",
                                    "kind": "FUNCTION",
                                    "containerName": "main",
                                    "url": "/sym_url",
                                }
                            ],
                        },
                        {
                            "__typename": "CommitSearchResult",
                            "commit": {
                                "oid": "1234567890abcdef",
                                "message": "commit msg\ndetails",
                                "author": {
                                    "person": {"name": "Alice"},
                                    "date": "2026-06-18",
                                },
                                "repository": {"name": "github.com/test/repo"},
                            },
                            "url": "/commit_url",
                        },
                        {
                            "__typename": "Repository",
                            "name": "github.com/test/repo",
                            "url": "/repo_url",
                        },
                    ],
                }
            }
        }
    }

    mock_post = mocker.patch.object(client, "_post_graphql", return_value=mock_data)

    res = await client.search("test")
    from sourcegraph_search.client import GRAPHQL_SEARCH_QUERY

    mock_post.assert_called_once_with(GRAPHQL_SEARCH_QUERY, {"query": "test"})
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


@pytest.mark.anyio
async def test_async_get_file_content(mocker):
    client = AsyncSourcegraphClient()
    mock_data = {
        "data": {"repository": {"commit": {"file": {"content": "file contents"}}}}
    }
    mocker.patch.object(client, "_post_graphql", return_value=mock_data)

    content = await client.get_file_content("repo", "path.txt")
    assert content == "file contents"


@pytest.mark.anyio
async def test_async_get_file_tree(mocker):
    client = AsyncSourcegraphClient()
    mock_data = {
        "data": {
            "repository": {
                "commit": {
                    "tree": {
                        "entries": [
                            {
                                "name": "src",
                                "path": "src",
                                "isDirectory": True,
                                "url": "/src",
                            },
                            {
                                "name": "main.py",
                                "path": "main.py",
                                "isDirectory": False,
                                "url": "/main.py",
                            },
                        ]
                    }
                }
            }
        }
    }
    mocker.patch.object(client, "_post_graphql", return_value=mock_data)

    entries = await client.get_file_tree("repo")
    assert len(entries) == 2
    assert isinstance(entries[0], TreeEntry)
    assert entries[0].name == "src"
    assert entries[0].is_directory is True
    assert entries[1].name == "main.py"
    assert entries[1].is_directory is False


@pytest.mark.anyio
async def test_async_get_code_intel(mocker):
    client = AsyncSourcegraphClient()
    mock_data = {
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
                                        "range": {
                                            "start": {"line": 10, "character": 5}
                                        },
                                        "url": "/def",
                                    }
                                ]
                            },
                            "references": {
                                "nodes": [
                                    {
                                        "resource": {
                                            "path": "ref.py",
                                            "repository": {"name": "repo"},
                                        },
                                        "range": {
                                            "start": {"line": 20, "character": 8}
                                        },
                                        "url": "/ref",
                                    }
                                ]
                            },
                        }
                    }
                }
            }
        }
    }
    mocker.patch.object(client, "_post_graphql", return_value=mock_data)

    res = await client.get_code_intel("repo", "main.py", 10, 5)
    assert isinstance(res, CodeIntelResult)
    assert len(res.definitions) == 1
    # Check 1-indexed conversion
    assert res.definitions[0].line == 11
    assert res.definitions[0].character == 6
    assert len(res.references) == 1
    assert res.references[0].line == 21


@pytest.mark.anyio
async def test_async_client_context_manager(mocker):
    mock_close = mocker.patch("httpx.AsyncClient.aclose")
    async with AsyncSourcegraphClient():
        pass
    mock_close.assert_called_once()


def test_search_parsing_with_content(mocker):
    client = SourcegraphClient()
    mock_data = {
        "data": {
            "search": {
                "results": {
                    "matchCount": 0,
                    "resultCount": 0,
                    "limitHit": False,
                    "results": [],
                }
            }
        }
    }
    mock_post = mocker.patch.object(client, "_post_graphql", return_value=mock_data)
    client.search("test", fetch_content=True)
    from sourcegraph_search.queries import GRAPHQL_SEARCH_WITH_CONTENT_QUERY

    mock_post.assert_called_once_with(
        GRAPHQL_SEARCH_WITH_CONTENT_QUERY, {"query": "test"}
    )


@pytest.mark.anyio
async def test_async_search_parsing_with_content(mocker):
    client = AsyncSourcegraphClient()
    mock_data = {
        "data": {
            "search": {
                "results": {
                    "matchCount": 0,
                    "resultCount": 0,
                    "limitHit": False,
                    "results": [],
                }
            }
        }
    }
    mock_post = mocker.patch.object(client, "_post_graphql", return_value=mock_data)
    await client.search("test", fetch_content=True)
    from sourcegraph_search.queries import GRAPHQL_SEARCH_WITH_CONTENT_QUERY

    mock_post.assert_called_once_with(
        GRAPHQL_SEARCH_WITH_CONTENT_QUERY, {"query": "test"}
    )


def test_client_injection_sync(mocker):
    mock_httpx_client = mocker.MagicMock()
    client = SourcegraphClient(client=mock_httpx_client)
    assert client.client is mock_httpx_client
    assert client._external_client is True

    client.close()
    mock_httpx_client.close.assert_not_called()


@pytest.mark.anyio
async def test_client_injection_async(mocker):
    mock_httpx_client = mocker.MagicMock()
    client = AsyncSourcegraphClient(client=mock_httpx_client)
    assert client.client is mock_httpx_client
    assert client._external_client is True

    await client.close()
    mock_httpx_client.aclose.assert_not_called()


@pytest.mark.anyio
async def test_protocols_conformance():
    from sourcegraph_search.client import (
        SourcegraphClientProtocol,
        AsyncSourcegraphClientProtocol,
    )

    sync_client = SourcegraphClient()
    assert isinstance(sync_client, SourcegraphClientProtocol)
    sync_client.close()

    async_client = AsyncSourcegraphClient()
    assert isinstance(async_client, AsyncSourcegraphClientProtocol)
    await async_client.close()
