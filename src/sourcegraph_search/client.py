import httpx
from typing import Any, Dict, List, Optional, Protocol, Tuple

from sourcegraph_search.models import (
    SearchResults,
    TreeEntry,
    CodeIntelResult,
)
from sourcegraph_search.queries import (
    GRAPHQL_SEARCH_QUERY,
    GRAPHQL_SEARCH_WITH_CONTENT_QUERY,
    GRAPHQL_FILE_CONTENT_QUERY,
    GRAPHQL_FILE_TREE_QUERY,
    GRAPHQL_CODE_INTEL_QUERY,
)
from sourcegraph_search.parsers import (
    SourcegraphError,
    parse_search_response,
    parse_file_content_response,
    parse_file_tree_response,
    parse_code_intel_response,
)

# Re-exports for backward compatibility
__all__ = [
    "SourcegraphClient",
    "AsyncSourcegraphClient",
    "SourcegraphError",
    "SourcegraphClientProtocol",
    "GRAPHQL_SEARCH_QUERY",
    "GRAPHQL_SEARCH_WITH_CONTENT_QUERY",
    "GRAPHQL_FILE_CONTENT_QUERY",
    "GRAPHQL_FILE_TREE_QUERY",
    "GRAPHQL_CODE_INTEL_QUERY",
]


class SourcegraphClientProtocol(Protocol):
    """Sourcegraph 同步客户端接口协议，解耦具体实现"""

    def search(self, query: str, fetch_content: bool = False) -> SearchResults: ...

    def get_file_content(self, repo: str, path: str, rev: str = "HEAD") -> str: ...

    def get_file_tree(
        self, repo: str, path: str = "", rev: str = "HEAD"
    ) -> List[TreeEntry]: ...

    def get_code_intel(
        self, repo: str, path: str, line: int, character: int, rev: str = "HEAD"
    ) -> CodeIntelResult: ...

    def close(self) -> None: ...


class BaseSourcegraphClient:
    def __init__(
        self,
        endpoint: str = "https://sourcegraph.com",
        token: Optional[str] = None,
        timeout: float = 30.0,
    ):
        self.endpoint = endpoint.rstrip("/")
        self.token = token
        self.timeout = timeout

    def _get_url(self) -> str:
        return f"{self.endpoint}/.api/graphql"

    def _get_headers(self) -> Dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "crush/1.0",
        }
        if self.token:
            headers["Authorization"] = f"token {self.token}"
        return headers

    def _get_payload(self, query: str, variables: Dict[str, Any]) -> Dict[str, Any]:
        return {"query": query, "variables": variables}

    def _check_graphql_errors(self, data: Dict[str, Any]) -> None:
        if "errors" in data and data["errors"]:
            err_msg = "; ".join(e.get("message", str(e)) for e in data["errors"])
            raise SourcegraphError(f"GraphQL Error: {err_msg}")

    def _prepare_search(
        self, query: str, fetch_content: bool
    ) -> Tuple[str, Dict[str, Any]]:
        query_str = (
            GRAPHQL_SEARCH_WITH_CONTENT_QUERY if fetch_content else GRAPHQL_SEARCH_QUERY
        )
        return query_str, {"query": query}

    def _prepare_file_content(
        self, repo: str, path: str, rev: str
    ) -> Tuple[str, Dict[str, Any]]:
        return GRAPHQL_FILE_CONTENT_QUERY, {"repo": repo, "rev": rev, "path": path}

    def _prepare_file_tree(
        self, repo: str, path: str, rev: str
    ) -> Tuple[str, Dict[str, Any]]:
        return GRAPHQL_FILE_TREE_QUERY, {"repo": repo, "rev": rev, "path": path}

    def _prepare_code_intel(
        self, repo: str, path: str, line: int, character: int, rev: str
    ) -> Tuple[str, Dict[str, Any]]:
        return GRAPHQL_CODE_INTEL_QUERY, {
            "repo": repo,
            "rev": rev,
            "path": path,
            "line": line,
            "character": character,
        }

    def _process_response(
        self, status_code: int, text: str, json_func: Any
    ) -> Dict[str, Any]:
        if status_code != 200:
            raise SourcegraphError(
                f"Request failed with status code {status_code}: {text}"
            )
        try:
            data = json_func()
            self._check_graphql_errors(data)
            return data
        except ValueError as exc:
            raise SourcegraphError(f"Failed to parse JSON response: {exc}")


class SourcegraphClient(BaseSourcegraphClient):
    def __init__(
        self,
        endpoint: str = "https://sourcegraph.com",
        token: Optional[str] = None,
        timeout: float = 30.0,
        client: Optional[httpx.Client] = None,
    ):
        super().__init__(endpoint=endpoint, token=token, timeout=timeout)
        self.client = client or httpx.Client(timeout=timeout)
        self._external_client = client is not None

    def __enter__(self) -> "SourcegraphClient":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def close(self):
        if not self._external_client:
            self.client.close()

    def _post_graphql(self, query: str, variables: Dict[str, Any]) -> Dict[str, Any]:
        """Helper to send a GraphQL request to Sourcegraph."""
        url = self._get_url()
        headers = self._get_headers()
        payload = self._get_payload(query, variables)

        try:
            response = self.client.post(url, headers=headers, json=payload)
            return self._process_response(
                response.status_code, response.text, response.json
            )
        except httpx.RequestError as exc:
            raise SourcegraphError(f"HTTP request error: {exc}")

    def search(self, query: str, fetch_content: bool = False) -> SearchResults:
        """Performs a search query against Sourcegraph's GraphQL API and returns typed SearchResults.

        Set fetch_content=True to preload file contents for context windows (slower/more memory).
        """
        q, vars = self._prepare_search(query, fetch_content)
        data = self._post_graphql(q, vars)
        return parse_search_response(data)

    def get_file_content(self, repo: str, path: str, rev: str = "HEAD") -> str:
        """Retrieves raw content of a file directly."""
        q, vars = self._prepare_file_content(repo, path, rev)
        data = self._post_graphql(q, vars)
        return parse_file_content_response(data, repo, rev, path)

    def get_file_tree(
        self, repo: str, path: str = "", rev: str = "HEAD"
    ) -> List[TreeEntry]:
        """Retrieves tree/entries inside a path."""
        q, vars = self._prepare_file_tree(repo, path, rev)
        data = self._post_graphql(q, vars)
        return parse_file_tree_response(data, repo, rev, path)

    def get_code_intel(
        self, repo: str, path: str, line: int, character: int, rev: str = "HEAD"
    ) -> CodeIntelResult:
        """Retrieves definitions and references from SCIP/LSIF code navigation."""
        q, vars = self._prepare_code_intel(repo, path, line, character, rev)
        data = self._post_graphql(q, vars)
        return parse_code_intel_response(data, repo, rev, path)


class AsyncSourcegraphClient(BaseSourcegraphClient):
    def __init__(
        self,
        endpoint: str = "https://sourcegraph.com",
        token: Optional[str] = None,
        timeout: float = 30.0,
        client: Optional[httpx.AsyncClient] = None,
    ):
        super().__init__(endpoint=endpoint, token=token, timeout=timeout)
        self.client = client or httpx.AsyncClient(timeout=timeout)
        self._external_client = client is not None

    async def __aenter__(self) -> "AsyncSourcegraphClient":
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    async def close(self):
        if not self._external_client:
            await self.client.aclose()

    async def _post_graphql(
        self, query: str, variables: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Helper to send an asynchronous GraphQL request to Sourcegraph."""
        url = self._get_url()
        headers = self._get_headers()
        payload = self._get_payload(query, variables)

        try:
            response = await self.client.post(url, headers=headers, json=payload)
            return self._process_response(
                response.status_code, response.text, response.json
            )
        except httpx.RequestError as exc:
            raise SourcegraphError(f"HTTP request error: {exc}")

    async def search(self, query: str, fetch_content: bool = False) -> SearchResults:
        """Performs an asynchronous search query against Sourcegraph's GraphQL API.

        Set fetch_content=True to preload file contents for context windows (slower/more memory).
        """
        q, vars = self._prepare_search(query, fetch_content)
        data = await self._post_graphql(q, vars)
        return parse_search_response(data)

    async def get_file_content(self, repo: str, path: str, rev: str = "HEAD") -> str:
        """Retrieves raw content of a file asynchronously."""
        q, vars = self._prepare_file_content(repo, path, rev)
        data = await self._post_graphql(q, vars)
        return parse_file_content_response(data, repo, rev, path)

    async def get_file_tree(
        self, repo: str, path: str = "", rev: str = "HEAD"
    ) -> List[TreeEntry]:
        """Retrieves tree/entries inside a path asynchronously."""
        q, vars = self._prepare_file_tree(repo, path, rev)
        data = await self._post_graphql(q, vars)
        return parse_file_tree_response(data, repo, rev, path)

    async def get_code_intel(
        self, repo: str, path: str, line: int, character: int, rev: str = "HEAD"
    ) -> CodeIntelResult:
        """Retrieves definitions and references asynchronously."""
        q, vars = self._prepare_code_intel(repo, path, line, character, rev)
        data = await self._post_graphql(q, vars)
        return parse_code_intel_response(data, repo, rev, path)
