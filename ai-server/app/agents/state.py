from typing import TypedDict


class InvestigationState(TypedDict, total=False):
    bug: dict
    signals: dict
    round: int
    tasks: list[dict]
    findings: list[dict]
    hypotheses: list[dict]
    verification: dict
    evidence_count_before: int
    stop_reason: str
    report: dict
    phase_outputs: list[dict]
