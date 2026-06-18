import httpx
from typing import Any, Dict, List, Optional

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

    def _post_graphql(self, query: str, variables: Dict[str, Any]) -> Dict[str, Any]:
        """Helper to send a GraphQL request to Sourcegraph."""
        url = f"{self.endpoint}/.api/graphql"
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "crush/1.0",
        }
        if self.token:
            headers["Authorization"] = f"token {self.token}"

        payload = {
            "query": query,
            "variables": variables
        }

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

    def search(self, query: str) -> Dict[str, Any]:
        """Performs a search query against Sourcegraph's GraphQL API."""
        return self._post_graphql(GRAPHQL_SEARCH_QUERY, {"query": query})

    def get_file_content(self, repo: str, path: str, rev: str = "HEAD") -> str:
        """Retrieves raw content of a file directly."""
        data = self._post_graphql(
            GRAPHQL_FILE_CONTENT_QUERY,
            {"repo": repo, "rev": rev, "path": path}
        )
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

    def get_file_tree(self, repo: str, path: str = "", rev: str = "HEAD") -> List[Dict[str, Any]]:
        """Retrieves tree/entries inside a path."""
        data = self._post_graphql(
            GRAPHQL_FILE_TREE_QUERY,
            {"repo": repo, "rev": rev, "path": path}
        )
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
            return tree.get("entries") or []
        except (KeyError, TypeError) as exc:
            raise SourcegraphError(f"Failed to parse file tree response: {exc}")

    def get_code_intel(
        self, repo: str, path: str, line: int, character: int, rev: str = "HEAD"
    ) -> Dict[str, Any]:
        """Retrieves definitions and references from SCIP/LSIF code navigation."""
        data = self._post_graphql(
            GRAPHQL_CODE_INTEL_QUERY,
            {"repo": repo, "rev": rev, "path": path, "line": line, "character": character}
        )
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
                raise SourcegraphError(f"Precise code intelligence (LSIF/SCIP) is not indexed/enabled for {repo}@{rev}")
            
            return lsif
        except (KeyError, TypeError) as exc:
            raise SourcegraphError(f"Failed to parse code intelligence response: {exc}")

    def format_results(
        self,
        result_data: Dict[str, Any],
        context_window: int = 10,
        max_results: int = 10,
    ) -> str:
        """Formats the search result JSON data into a Markdown string."""
        data = result_data.get("data", {})
        search = data.get("search", {})
        search_results = search.get("results", {})

        match_count = int(search_results.get("matchCount", 0))
        result_count = int(search_results.get("resultCount", 0))
        limit_hit = bool(search_results.get("limitHit", False))

        output = []
        output.append("# Sourcegraph Search Results\n")
        output.append(f"Found {match_count} matches across {result_count} results\n")
        
        if limit_hit:
            output.append("(Result limit reached, try a more specific query)\n")
        
        output.append("")

        results = search_results.get("results", [])
        if not results:
            output.append("No results found. Try a different query.\n")
            return "\n".join(output)

        results_to_process = results[:max_results]

        for i, res in enumerate(results_to_process):
            if not isinstance(res, dict):
                continue
            
            typename = res.get("__typename")
            
            if typename == "FileMatch":
                repo = res.get("repository", {})
                file = res.get("file", {})
                line_matches = res.get("lineMatches", [])
                symbols = res.get("symbols", [])

                repo_name = repo.get("name", "")
                file_path = file.get("path", "")
                file_url = file.get("url", "")
                file_content = file.get("content", "")

                output.append(f"## Result {i+1}: {repo_name}/{file_path} (File)\n")
                if file_url:
                    output.append(f"URL: {file_url}\n")

                # Format Symbols if any exist
                if symbols:
                    output.append("### Symbols:")
                    for sym in symbols:
                        sym_name = sym.get("name", "")
                        sym_kind = sym.get("kind", "")
                        sym_container = sym.get("containerName", "")
                        sym_url = sym.get("url", "")
                        container_str = f" in {sym_container}" if sym_container else ""
                        output.append(f"- **{sym_name}** ({sym_kind}){container_str} -> {sym_url}")
                    output.append("")

                # Format Line Matches
                if line_matches:
                    for lm in line_matches:
                        if not isinstance(lm, dict):
                            continue
                        
                        line_number = int(lm.get("lineNumber", 0))
                        preview = lm.get("preview", "")

                        if file_content:
                            lines = file_content.split("\n")
                            output.append("```")

                            start_line = max(1, line_number - context_window)
                            for j in range(start_line - 1, line_number - 1):
                                if 0 <= j < len(lines):
                                    output.append(f"{j+1}| {lines[j]}")

                            output.append(f"{line_number}|  {preview}")

                            end_line = line_number + context_window
                            for j in range(line_number, end_line):
                                if 0 <= j < len(lines):
                                    output.append(f"{j+1}| {lines[j]}")

                            output.append("```\n")
                        else:
                            output.append("```")
                            output.append(f"{line_number}| {preview}")
                            output.append("```\n")

            elif typename == "CommitSearchResult":
                commit = res.get("commit", {})
                url = res.get("url", "")
                
                oid = commit.get("oid", "")[:8]
                message = commit.get("message", "")
                author = commit.get("author", {})
                person = author.get("person", {})
                author_name = person.get("name", "")
                author_date = author.get("date", "")
                
                repo = commit.get("repository", {})
                repo_name = repo.get("name", "")

                first_line_msg = message.split("\n")[0] if message else ""

                output.append(f"## Result {i+1}: {repo_name} (Commit {oid})\n")
                output.append(f"Author: {author_name} ({author_date})")
                if url:
                    output.append(f"URL: {url}")
                output.append(f"Message: {first_line_msg}\n")

            elif typename == "Repository":
                repo_name = res.get("name", "")
                repo_url = res.get("url", "")

                output.append(f"## Result {i+1}: {repo_name} (Repository)\n")
                if repo_url:
                    output.append(f"URL: {repo_url}\n")

        return "\n".join(output)
