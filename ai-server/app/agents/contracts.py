from typing import Annotated, Literal
from pydantic import BaseModel, ConfigDict, Field

Text = Annotated[str, Field(max_length=2000)]
Identifier = Annotated[str, Field(min_length=1, max_length=160)]
Role = Literal["code", "git", "dependency"]


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid")


class BugSignals(Contract):
    summary: Text
    search_terms: list[Annotated[str, Field(min_length=1, max_length=200)]] = Field(max_length=6)
    missing_information: list[Text] = Field(default_factory=list, max_length=5)


class Finding(Contract):
    summary: Text
    evidence_ids: list[Identifier] = Field(default_factory=list, max_length=12)
    missing_information: list[Text] = Field(default_factory=list, max_length=5)


class ToolAction(Contract):
    action: Literal["tool"]
    tool: Annotated[str, Field(max_length=80)]
    arguments: dict


class FinishAction(Contract):
    action: Literal["finish"]
    result: Finding


class AgentAction(Contract):
    # A nested discriminated union makes the two valid actions unambiguous.
    response: Annotated[ToolAction | FinishAction, Field(discriminator="action")]


class Hypothesis(Contract):
    candidate_id: Identifier
    mechanism: Text
    evidence_ids: list[Identifier] = Field(min_length=1, max_length=8)
    counterevidence_ids: list[Identifier] = Field(default_factory=list, max_length=8)
    assumptions: list[Text] = Field(default_factory=list, max_length=5)
    suggested_fix: Text


class Hypotheses(Contract):
    hypotheses: list[Hypothesis] = Field(max_length=3)
    missing_information: list[Text] = Field(default_factory=list, max_length=5)


class FollowUp(Contract):
    role: Role
    question: Text


class Verification(Contract):
    verdict: Literal["supported", "insufficient_evidence", "contradicted"]
    primary_candidate_id: Identifier | None
    evidence_ids: list[Identifier] = Field(default_factory=list, max_length=12)
    explanation: Text
    follow_up: list[FollowUp] = Field(default_factory=list, max_length=2)
    limitations: list[Text] = Field(default_factory=list, max_length=8)
