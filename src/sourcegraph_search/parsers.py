from typing import Any, Dict, List
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
from sourcegraph_search.exceptions import (
    APIError,
    ResponseParseError,
)


def _parse_file_match(res: Dict[str, Any]) -> FileMatchResult:
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

    return FileMatchResult(
        repository=repo.get("name", ""),
        path=file.get("path", ""),
        url=file.get("url", ""),
        content=file.get("content") or "",
        line_matches=line_matches,
        symbols=symbols,
    )


def _parse_commit(res: Dict[str, Any]) -> CommitResult:
    commit = res.get("commit", {})
    url = res.get("url", "")

    oid = commit.get("oid", "")
    message = commit.get("message", "")
    author = commit.get("author", {})
    person = author.get("person", {})
    author_name = person.get("name", "")
    author_date = author.get("date", "")

    repo = commit.get("repository", {})

    return CommitResult(
        repository=repo.get("name", ""),
        oid=oid,
        message=message,
        author_name=author_name,
        author_date=author_date,
        url=url,
    )


def _parse_repository(res: Dict[str, Any]) -> RepositoryResult:
    return RepositoryResult(name=res.get("name", ""), url=res.get("url", ""))


# Registry map for polymorphic item parsers based on __typename
ITEM_PARSER_REGISTRY = {
    "FileMatch": _parse_file_match,
    "CommitSearchResult": _parse_commit,
    "Repository": _parse_repository,
}


def parse_search_response(data: Dict[str, Any]) -> SearchResults:
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
            parser_fn = ITEM_PARSER_REGISTRY.get(typename)
            if parser_fn:
                items.append(parser_fn(res))

        return SearchResults(
            match_count=match_count,
            result_count=result_count,
            limit_hit=limit_hit,
            items=items,
        )
    except (KeyError, TypeError) as exc:
        raise ResponseParseError(f"Failed to parse search response: {exc}")


def parse_file_content_response(
    data: Dict[str, Any], repo: str, rev: str, path: str
) -> str:
    try:
        repository = data["data"]["repository"]
        if not repository:
            raise APIError(f"Repository not found: {repo}")
        commit = repository["commit"]
        if not commit:
            raise APIError(f"Revision/Commit not found: {rev}")
        file_node = commit["file"]
        if not file_node:
            raise APIError(f"File not found in {repo}@{rev}: {path}")
        return file_node["content"]
    except (KeyError, TypeError) as exc:
        raise ResponseParseError(f"Failed to parse file content response: {exc}")


def parse_file_tree_response(
    data: Dict[str, Any], repo: str, rev: str, path: str
) -> List[TreeEntry]:
    try:
        repository = data["data"]["repository"]
        if not repository:
            raise APIError(f"Repository not found: {repo}")
        commit = repository["commit"]
        if not commit:
            raise APIError(f"Revision/Commit not found: {rev}")
        tree = commit["tree"]
        if not tree:
            raise APIError(f"Path not found in {repo}@{rev}: {path}")

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
        raise ResponseParseError(f"Failed to parse file tree response: {exc}")


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


def parse_code_intel_response(
    data: Dict[str, Any], repo: str, rev: str, path: str
) -> CodeIntelResult:
    try:
        repository = data["data"]["repository"]
        if not repository:
            raise APIError(f"Repository not found: {repo}")
        commit = repository["commit"]
        if not commit:
            raise APIError(f"Revision/Commit not found: {rev}")
        blob = commit["blob"]
        if not blob:
            raise APIError(f"File not found in {repo}@{rev}: {path}")

        lsif = blob.get("lsif")
        if not lsif:
            raise APIError(
                f"Precise code intelligence (LSIF/SCIP) is not indexed/enabled for {repo}@{rev}"
            )

        definitions_raw = lsif.get("definitions", {}).get("nodes", []) or []
        references_raw = lsif.get("references", {}).get("nodes", []) or []

        return CodeIntelResult(
            definitions=_parse_locations(definitions_raw),
            references=_parse_locations(references_raw),
        )
    except (KeyError, TypeError) as exc:
        raise ResponseParseError(f"Failed to parse code intelligence response: {exc}")
