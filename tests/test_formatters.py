import json
from sourcegraph_search.models import (
    SearchResults, FileMatchResult, LineMatch, SymbolMatch, CommitResult, RepositoryResult, CodeIntelLocation
)
from sourcegraph_search.formatters import MarkdownFormatter, JSONFormatter

def test_markdown_formatter_search():
    results = SearchResults(
        match_count=2,
        result_count=2,
        limit_hit=True,
        items=[
            FileMatchResult(
                repository="github.com/owner/repo",
                path="main.py",
                url="/main",
                content="line1\nline2\nline3\nline4",
                line_matches=[LineMatch(line_number=2, preview="line2")],
                symbols=[SymbolMatch(name="foo", kind="FUNCTION", container_name="main", url="/sym")]
            ),
            CommitResult(
                repository="github.com/owner/repo",
                oid="abcdef123456",
                message="My commit\n\nDetail description",
                author_name="Alice",
                author_date="2026-06-18",
                url="/commit"
            )
        ]
    )
    
    formatter = MarkdownFormatter()
    md_output = formatter.format_search(results, context_window=1)
    
    assert "# Sourcegraph Search Results" in md_output
    assert "Found 2 matches across 2 results" in md_output
    assert "(Result limit reached, try a more specific query)" in md_output
    assert "## Result 1: github.com/owner/repo/main.py (File)" in md_output
    assert "URL: /main" in md_output
    assert "- **foo** (FUNCTION) in main -> /sym" in md_output
    assert "1| line1" in md_output
    assert "2|  line2" in md_output  # Double space indentation check
    assert "3| line3" in md_output
    assert "## Result 2: github.com/owner/repo (Commit abcdef12)" in md_output
    assert "Author: Alice (2026-06-18)" in md_output
    assert "Message: My commit" in md_output

def test_markdown_formatter_code_intel():
    locations = [
        CodeIntelLocation(repository="repo", path="main.py", line=10, character=5, url="/url")
    ]
    
    formatter = MarkdownFormatter()
    md_def = formatter.format_definitions(locations)
    md_ref = formatter.format_references(locations)
    
    assert "# Definitions" in md_def
    assert "- **repo/main.py#L10:5** -> /url" in md_def
    
    assert "# References" in md_ref
    assert "- **repo/main.py#L10:5** -> /url" in md_ref

def test_json_formatter():
    results = SearchResults(
        match_count=1,
        result_count=1,
        limit_hit=False,
        items=[
            RepositoryResult(name="repo", url="/repo")
        ]
    )
    
    formatter = JSONFormatter()
    json_output = formatter.format_search(results)
    
    parsed = json.loads(json_output)
    assert parsed["match_count"] == 1
    assert parsed["items"][0]["name"] == "repo"
    assert parsed["items"][0]["url"] == "/repo"

    locations = [
        CodeIntelLocation(repository="repo", path="main.py", line=10, character=5, url="/url")
    ]
    json_def = formatter.format_definitions(locations)
    parsed_def = json.loads(json_def)
    assert len(parsed_def) == 1
    assert parsed_def[0]["repository"] == "repo"
    assert parsed_def[0]["line"] == 10
