from typing import Annotated
from pydantic import Field
from app.agents.contracts import Contract, Identifier


class SearchArgs(Contract):
    query: Annotated[str, Field(min_length=1, max_length=500)]
    limit: int = Field(default=5, ge=1, le=10)


class ChunkArgs(Contract):
    chunk_id: Identifier


class ReadArgs(ChunkArgs):
    offset: int = Field(default=0, ge=0, le=20000)
    lines: int = Field(default=80, ge=1, le=120)


class HistoryArgs(ChunkArgs):
    limit: int = Field(default=3, ge=1, le=5)
