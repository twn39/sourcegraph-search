from dataclasses import dataclass, asdict
from typing import List, Union


@dataclass
class SymbolMatch:
    name: str
    kind: str
    container_name: str
    url: str


@dataclass
class LineMatch:
    line_number: int
    preview: str


@dataclass
class FileMatchResult:
    repository: str
    path: str
    url: str
    content: str
    line_matches: List[LineMatch]
    symbols: List[SymbolMatch]


@dataclass
class CommitResult:
    repository: str
    oid: str
    message: str
    author_name: str
    author_date: str
    url: str


@dataclass
class RepositoryResult:
    name: str
    url: str


SearchResultItem = Union[FileMatchResult, CommitResult, RepositoryResult]


@dataclass
class SearchResults:
    match_count: int
    result_count: int
    limit_hit: bool
    items: List[SearchResultItem]


@dataclass
class TreeEntry:
    name: str
    path: str
    is_directory: bool
    url: str


@dataclass
class CodeIntelLocation:
    repository: str
    path: str
    line: int
    character: int
    url: str


@dataclass
class CodeIntelResult:
    definitions: List[CodeIntelLocation]
    references: List[CodeIntelLocation]
