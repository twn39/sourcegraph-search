from abc import ABC, abstractmethod
import json
from dataclasses import asdict
from functools import singledispatchmethod
from typing import List

from sourcegraph_search.models import (
    SearchResults,
    FileMatchResult,
    CommitResult,
    RepositoryResult,
    CodeIntelLocation,
)


class BaseFormatter(ABC):
    @abstractmethod
    def format_search(self, results: SearchResults, context_window: int = 10) -> str:
        """Format search results."""
        pass

    @abstractmethod
    def format_definitions(self, locations: List[CodeIntelLocation]) -> str:
        """Format symbol definition locations."""
        pass

    @abstractmethod
    def format_references(self, locations: List[CodeIntelLocation]) -> str:
        """Format symbol reference locations."""
        pass


class MarkdownFormatter(BaseFormatter):
    def format_search(self, results: SearchResults, context_window: int = 10) -> str:
        output = []
        output.append("# Sourcegraph Search Results\n")
        output.append(
            f"Found {results.match_count} matches across {results.result_count} results\n"
        )

        if results.limit_hit:
            output.append("(Result limit reached, try a more specific query)\n")

        output.append("")

        if not results.items:
            output.append("No results found. Try a different query.\n")
            return "\n".join(output)

        for i, item in enumerate(results.items):
            formatted_item = self._format_item(item, i + 1, context_window)
            output.append(formatted_item)

        return "\n".join(output)

    @singledispatchmethod
    def _format_item(self, item, index: int, context_window: int) -> str:
        """Fallback method for unsupported types."""
        raise NotImplementedError(
            f"Unsupported item type for markdown formatting: {type(item)}"
        )

    @_format_item.register
    def _(self, item: FileMatchResult, index: int, context_window: int) -> str:
        output = []
        output.append(f"## Result {index}: {item.repository}/{item.path} (File)\n")
        if item.url:
            output.append(f"URL: {item.url}\n")

        if item.symbols:
            output.append("### Symbols:")
            for sym in item.symbols:
                container_str = (
                    f" in {sym.container_name}" if sym.container_name else ""
                )
                output.append(
                    f"- **{sym.name}** ({sym.kind}){container_str} -> {sym.url}"
                )
            output.append("")

        if item.line_matches:
            for lm in item.line_matches:
                if item.content:
                    lines = item.content.split("\n")
                    output.append("```")

                    start_line = max(1, lm.line_number - context_window)
                    for j in range(start_line - 1, lm.line_number - 1):
                        if 0 <= j < len(lines):
                            output.append(f"{j + 1}| {lines[j]}")

                    output.append(f"{lm.line_number}|  {lm.preview}")

                    end_line = lm.line_number + context_window
                    for j in range(lm.line_number, end_line):
                        if 0 <= j < len(lines):
                            output.append(f"{j + 1}| {lines[j]}")

                    output.append("```\n")
                else:
                    output.append("```")
                    output.append(f"{lm.line_number}| {lm.preview}")
                    output.append("```\n")

        return "\n".join(output)

    @_format_item.register
    def _(self, item: CommitResult, index: int, context_window: int) -> str:
        output = []
        output.append(f"## Result {index}: {item.repository} (Commit {item.oid[:8]})\n")
        output.append(f"Author: {item.author_name} ({item.author_date})")
        if item.url:
            output.append(f"URL: {item.url}")
        first_line_msg = item.message.split("\n")[0] if item.message else ""
        output.append(f"Message: {first_line_msg}\n")
        return "\n".join(output)

    @_format_item.register
    def _(self, item: RepositoryResult, index: int, context_window: int) -> str:
        output = []
        output.append(f"## Result {index}: {item.name} (Repository)\n")
        if item.url:
            output.append(f"URL: {item.url}\n")
        return "\n".join(output)

    def _format_locations(self, title: str, locations: List[CodeIntelLocation]) -> str:
        if not locations:
            return f"No {title.lower()} found."

        output = [f"# {title}\n"]
        for loc in locations:
            output.append(
                f"- **{loc.repository}/{loc.path}#L{loc.line}:{loc.character}** -> {loc.url}"
            )
        return "\n".join(output)

    def format_definitions(self, locations: List[CodeIntelLocation]) -> str:
        return self._format_locations("Definitions", locations)

    def format_references(self, locations: List[CodeIntelLocation]) -> str:
        return self._format_locations("References", locations)


class JSONFormatter(BaseFormatter):
    def format_search(self, results: SearchResults, context_window: int = 10) -> str:
        return json.dumps(asdict(results), indent=2)

    def format_definitions(self, locations: List[CodeIntelLocation]) -> str:
        return json.dumps([asdict(loc) for loc in locations], indent=2)

    def format_references(self, locations: List[CodeIntelLocation]) -> str:
        return json.dumps([asdict(loc) for loc in locations], indent=2)
