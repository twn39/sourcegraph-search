import httpx
from typing import Any, Dict, List, Optional

from sourcegraph_search.models import (
    SymbolMatch,
    LineMatch,
    FileMatchResult,
    CommitResult,
    RepositoryResult,
    SearchResults,
    TreeEntry,
    CodeIntelLocation,
    CodeIntelResult,
)

# Lightweight Search Query (Blazing fast, removes 'content' field to prevent memory & network bloat)
GRAPHQL_SEARCH_QUERY = """
query Search($query: String!) {
  search(query: $query, version: V2, patternType: keyword ) {
    results {
      matchCount
      limitHit
      resultCount
      approximateResultCount
      missing { name }
      timedout { name }
      indexUnavailable
      results {
        __typename
        ... on FileMatch {
          repository { name }
          file { path, url }
          lineMatches {
            preview
            lineNumber
            offsetAndLengths
          }
          symbols {
            name
            kind
            containerName
            url
          }
        }
        ... on CommitSearchResult {
          commit {
            oid
            message
            author {
              person {
                name
              }
              date
            }
            repository {
              name
            }
          }
          url
        }
        ... on Repository {
          name
          url
        }
      }
    }
  }
}
"""

# Context Preloading Query (Fetches 'content' only when full context window surrounding lines is requested)
GRAPHQL_SEARCH_WITH_CONTENT_QUERY = """
query Search($query: String!) {
  search(query: $query, version: V2, patternType: keyword ) {
    results {
      matchCount
      limitHit
      resultCount
      approximateResultCount
      missing { name }
      timedout { name }
      indexUnavailable
      results {
        __typename
        ... on FileMatch {
          repository { name }
          file { path, url, content }
          lineMatches {
            preview
            lineNumber
            offsetAndLengths
          }
          symbols {
            name
            kind
            containerName
            url
          }
        }
        ... on CommitSearchResult {
          commit {
            oid
            message
            author {
              person {
                name
              }
              date
            }
            repository {
              name
            }
          }
          url
        }
        ... on Repository {
          name
          url
        }
      }
    }
  }
}
"""

GRAPHQL_FILE_CONTENT_QUERY = """
query GetFileContent($repo: String!, $rev: String!, $path: String!) {
  repository(name: $repo) {
    commit(rev: $rev) {
      file(path: $path) {
        content
      }
    }
  }
}
"""

GRAPHQL_FILE_TREE_QUERY = """
query GetFileTree($repo: String!, $rev: String!, $path: String!) {
  repository(name: $repo) {
    commit(rev: $rev) {
      tree(path: $path) {
        entries {
          name
          path
          isDirectory
          url
        }
      }
    }
  }
}
"""

GRAPHQL_CODE_INTEL_QUERY = """
query CodeIntel($repo: String!, $rev: String!, $path: String!, $line: Int!, $character: Int!) {
  repository(name: $repo) {
    commit(rev: $rev) {
      blob(path: $path) {
        lsif {
          definitions(line: $line, character: $character) {
            nodes {
              resource {
                path
                repository {
                  name
                }
              }
              range {
                start {
                  line
                  character
                }
                end {
                  line
                  character
                }
              }
              url
            }
          }
          references(line: $line, character: $character) {
            nodes {
              resource {
                path
                repository {
                  name
                }
              }
              range {
                start {
                  line
                  character
                }
                end {
                  line
                  character
                }
              }
              url
            }
          }
        }
      }
    }
  }
}
"""


class SourcegraphError(Exception):
    """Base exception for Sourcegraph client errors."""

    pass


def _parse_search_response(data: Dict[str, Any]) -> SearchResults:
    try:
        search_data = data["data"]["search"]["results"]
        match_count = int(search_data.get("matchCount", 0))
        result_count = int(search_data.get("resultCount", 0))
        limit_hit = bool(search_data.get("limitHit", False))

        items = []
        raw_results = search_data.get("results", [])
        for res in raw_results:
            if not isinstance(res, dict):
                continue
            typename = res.get("__typename")

            if typename == "FileMatch":
                repo = res.get("repository", {})
                file = res.get("file", {})
                line_matches_raw = res.get("lineMatches", [])
                symbols_raw = res.get("symbols", [])

                line_matches = [
                    LineMatch(
                        line_number=int(lm.get("lineNumber", 0)),
                        preview=lm.get("preview", ""),
                    )
                    for lm in line_matches_raw
                    if isinstance(lm, dict)
                ]

                symbols = [
                    SymbolMatch(
                        name=sym.get("name", ""),
                        kind=sym.get("kind", ""),
                        container_name=sym.get("containerName", ""),
                        url=sym.get("url", ""),
                    )
                    for sym in symbols_raw
                    if isinstance(sym, dict)
                ]

                items.append(
                    FileMatchResult(
                        repository=repo.get("name", ""),
                        path=file.get("path", ""),
                        url=file.get("url", ""),
                        content=file.get("content") or "",
                        line_matches=line_matches,
                        symbols=symbols,
                    )
                )

            elif typename == "CommitSearchResult":
                commit = res.get("commit", {})
                url = res.get("url", "")

                oid = commit.get("oid", "")
                message = commit.get("message", "")
                author = commit.get("author", {})
                person = author.get("person", {})
                author_name = person.get("name", "")
                author_date = author.get("date", "")

                repo = commit.get("repository", {})

                items.append(
                    CommitResult(
                        repository=repo.get("name", ""),
                        oid=oid,
                        message=message,
                        author_name=author_name,
                        author_date=author_date,
                        url=url,
                    )
                )

            elif typename == "Repository":
                items.append(
                    RepositoryResult(name=res.get("name", ""), url=res.get("url", ""))
                )

        return SearchResults(
            match_count=match_count,
            result_count=result_count,
            limit_hit=limit_hit,
            items=items,
        )
    except (KeyError, TypeError) as exc:
        raise SourcegraphError(f"Failed to parse search response: {exc}")


def _parse_file_content_response(
    data: Dict[str, Any], repo: str, rev: str, path: str
) -> str:
    try:
        repository = data["data"]["repository"]
        if not repository:
            raise SourcegraphError(f"Repository not found: {repo}")
        commit = repository["commit"]
        if not commit:
            raise SourcegraphError(f"Revision/Commit not found: {rev}")
        file_node = commit["file"]
        if not file_node:
            raise SourcegraphError(f"File not found in {repo}@{rev}: {path}")
        return file_node["content"]
    except (KeyError, TypeError) as exc:
        raise SourcegraphError(f"Failed to parse file content response: {exc}")


def _parse_file_tree_response(
    data: Dict[str, Any], repo: str, rev: str, path: str
) -> List[TreeEntry]:
    try:
        repository = data["data"]["repository"]
        if not repository:
            raise SourcegraphError(f"Repository not found: {repo}")
        commit = repository["commit"]
        if not commit:
            raise SourcegraphError(f"Revision/Commit not found: {rev}")
        tree = commit["tree"]
        if not tree:
            raise SourcegraphError(f"Path not found in {repo}@{rev}: {path}")

        raw_entries = tree.get("entries") or []
        return [
            TreeEntry(
                name=entry.get("name", ""),
                path=entry.get("path", ""),
                is_directory=bool(entry.get("isDirectory", False)),
                url=entry.get("url", ""),
            )
            for entry in raw_entries
            if isinstance(entry, dict)
        ]
    except (KeyError, TypeError) as exc:
        raise SourcegraphError(f"Failed to parse file tree response: {exc}")


def _parse_locations(nodes: List[Dict[str, Any]]) -> List[CodeIntelLocation]:
    locations = []
    for node in nodes:
        if not isinstance(node, dict):
            continue
        res = node.get("resource", {})
        repo_info = res.get("repository", {})
        rng = node.get("range", {})
        start = rng.get("start", {})

        line_num = int(start.get("line", 0)) + 1
        char_num = int(start.get("character", 0)) + 1

        locations.append(
            CodeIntelLocation(
                repository=repo_info.get("name", ""),
                path=res.get("path", ""),
                line=line_num,
                character=char_num,
                url=node.get("url", ""),
            )
        )
    return locations


def _parse_code_intel_response(
    data: Dict[str, Any], repo: str, rev: str, path: str
) -> CodeIntelResult:
    try:
        repository = data["data"]["repository"]
        if not repository:
            raise SourcegraphError(f"Repository not found: {repo}")
        commit = repository["commit"]
        if not commit:
            raise SourcegraphError(f"Revision/Commit not found: {rev}")
        blob = commit["blob"]
        if not blob:
            raise SourcegraphError(f"File not found in {repo}@{rev}: {path}")

        lsif = blob.get("lsif")
        if not lsif:
            raise SourcegraphError(
                f"Precise code intelligence (LSIF/SCIP) is not indexed/enabled for {repo}@{rev}"
            )

        definitions_raw = lsif.get("definitions", {}).get("nodes", []) or []
        references_raw = lsif.get("references", {}).get("nodes", []) or []

        return CodeIntelResult(
            definitions=_parse_locations(definitions_raw),
            references=_parse_locations(references_raw),
        )
    except (KeyError, TypeError) as exc:
        raise SourcegraphError(f"Failed to parse code intelligence response: {exc}")


class SourcegraphClient:
    def __init__(
        self,
        endpoint: str = "https://sourcegraph.com",
        token: Optional[str] = None,
        timeout: float = 30.0,
    ):
        self.endpoint = endpoint.rstrip("/")
        self.token = token
        self.timeout = timeout
        self.client = httpx.Client(timeout=timeout)

    def __enter__(self) -> "SourcegraphClient":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def close(self):
        self.client.close()

    def _post_graphql(self, query: str, variables: Dict[str, Any]) -> Dict[str, Any]:
        """Helper to send a GraphQL request to Sourcegraph."""
        url = f"{self.endpoint}/.api/graphql"
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "crush/1.0",
        }
        if self.token:
            headers["Authorization"] = f"token {self.token}"

        payload = {"query": query, "variables": variables}

        try:
            response = self.client.post(url, headers=headers, json=payload)
            if response.status_code != 200:
                raise SourcegraphError(
                    f"Request failed with status code {response.status_code}: {response.text}"
                )

            data = response.json()
            if "errors" in data and data["errors"]:
                err_msg = "; ".join(e.get("message", str(e)) for e in data["errors"])
                raise SourcegraphError(f"GraphQL Error: {err_msg}")

            return data
        except httpx.RequestError as exc:
            raise SourcegraphError(f"HTTP request error: {exc}")
        except ValueError as exc:
            raise SourcegraphError(f"Failed to parse JSON response: {exc}")

    def search(self, query: str, fetch_content: bool = False) -> SearchResults:
        """Performs a search query against Sourcegraph's GraphQL API and returns typed SearchResults.

        Set fetch_content=True to preload file contents for context windows (slower/more memory).
        """
        query_str = (
            GRAPHQL_SEARCH_WITH_CONTENT_QUERY if fetch_content else GRAPHQL_SEARCH_QUERY
        )
        data = self._post_graphql(query_str, {"query": query})
        return _parse_search_response(data)

    def get_file_content(self, repo: str, path: str, rev: str = "HEAD") -> str:
        """Retrieves raw content of a file directly."""
        data = self._post_graphql(
            GRAPHQL_FILE_CONTENT_QUERY, {"repo": repo, "rev": rev, "path": path}
        )
        return _parse_file_content_response(data, repo, rev, path)

    def get_file_tree(
        self, repo: str, path: str = "", rev: str = "HEAD"
    ) -> List[TreeEntry]:
        """Retrieves tree/entries inside a path."""
        data = self._post_graphql(
            GRAPHQL_FILE_TREE_QUERY, {"repo": repo, "rev": rev, "path": path}
        )
        return _parse_file_tree_response(data, repo, rev, path)

    def get_code_intel(
        self, repo: str, path: str, line: int, character: int, rev: str = "HEAD"
    ) -> CodeIntelResult:
        """Retrieves definitions and references from SCIP/LSIF code navigation."""
        data = self._post_graphql(
            GRAPHQL_CODE_INTEL_QUERY,
            {
                "repo": repo,
                "rev": rev,
                "path": path,
                "line": line,
                "character": character,
            },
        )
        return _parse_code_intel_response(data, repo, rev, path)


class AsyncSourcegraphClient:
    def __init__(
        self,
        endpoint: str = "https://sourcegraph.com",
        token: Optional[str] = None,
        timeout: float = 30.0,
    ):
        self.endpoint = endpoint.rstrip("/")
        self.token = token
        self.timeout = timeout
        self.client = httpx.AsyncClient(timeout=timeout)

    async def __aenter__(self) -> "AsyncSourcegraphClient":
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    async def close(self):
        await self.client.aclose()

    async def _post_graphql(
        self, query: str, variables: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Helper to send an asynchronous GraphQL request to Sourcegraph."""
        url = f"{self.endpoint}/.api/graphql"
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "crush/1.0",
        }
        if self.token:
            headers["Authorization"] = f"token {self.token}"

        payload = {"query": query, "variables": variables}

        try:
            response = await self.client.post(url, headers=headers, json=payload)
            if response.status_code != 200:
                raise SourcegraphError(
                    f"Request failed with status code {response.status_code}: {response.text}"
                )

            data = response.json()
            if "errors" in data and data["errors"]:
                err_msg = "; ".join(e.get("message", str(e)) for e in data["errors"])
                raise SourcegraphError(f"GraphQL Error: {err_msg}")

            return data
        except httpx.RequestError as exc:
            raise SourcegraphError(f"HTTP request error: {exc}")
        except ValueError as exc:
            raise SourcegraphError(f"Failed to parse JSON response: {exc}")

    async def search(self, query: str, fetch_content: bool = False) -> SearchResults:
        """Performs an asynchronous search query against Sourcegraph's GraphQL API.

        Set fetch_content=True to preload file contents for context windows (slower/more memory).
        """
        query_str = (
            GRAPHQL_SEARCH_WITH_CONTENT_QUERY if fetch_content else GRAPHQL_SEARCH_QUERY
        )
        data = await self._post_graphql(query_str, {"query": query})
        return _parse_search_response(data)

    async def get_file_content(self, repo: str, path: str, rev: str = "HEAD") -> str:
        """Retrieves raw content of a file asynchronously."""
        data = await self._post_graphql(
            GRAPHQL_FILE_CONTENT_QUERY, {"repo": repo, "rev": rev, "path": path}
        )
        return _parse_file_content_response(data, repo, rev, path)

    async def get_file_tree(
        self, repo: str, path: str = "", rev: str = "HEAD"
    ) -> List[TreeEntry]:
        """Retrieves tree/entries inside a path asynchronously."""
        data = await self._post_graphql(
            GRAPHQL_FILE_TREE_QUERY, {"repo": repo, "rev": rev, "path": path}
        )
        return _parse_file_tree_response(data, repo, rev, path)

    async def get_code_intel(
        self, repo: str, path: str, line: int, character: int, rev: str = "HEAD"
    ) -> CodeIntelResult:
        """Retrieves definitions and references asynchronously."""
        data = await self._post_graphql(
            GRAPHQL_CODE_INTEL_QUERY,
            {
                "repo": repo,
                "rev": rev,
                "path": path,
                "line": line,
                "character": character,
            },
        )
        return _parse_code_intel_response(data, repo, rev, path)
