import hashlib
import json
import logging

from langchain_core.tools import StructuredTool

from app.tools.schemas import SearchArgs, ReadArgs, HistoryArgs, ChunkArgs

logger = logging.getLogger(__name__)

ALLOWLISTS = {
    "code": {"keyword_search", "semantic_search", "read_code"},
    "git": {"git_history", "read_code"},
    "dependency": {"dependency_neighbors", "read_code"},
}


class ToolExecutor:
    def __init__(self, repository, budget, guard=lambda: None):
        self.repository, self.budget, self.guard = repository, budget, guard
        self.evidence, self.candidates, self.cache, self.events = {}, {}, {}, []
        self.registry = {}
        definitions = [
            ("keyword_search", SearchArgs, "Find code by a literal term; results are candidates, not evidence of behavior."),
            ("semantic_search", SearchArgs, "Find relevant code by meaning using this index's embedding provider."),
            ("read_code", ReadArgs, "Read a bounded source range from a candidate; offsets are relative to chunk start."),
            ("git_history", HistoryArgs, "Inspect stored historical diffs affecting a candidate's file."),
            ("dependency_neighbors", ChunkArgs, "Inspect approximate direct callers/callees; read returned chunks to verify."),
        ]
        for name, schema, description in definitions:
            self.registry[name] = StructuredTool.from_function(
                func=getattr(repository, name), name=name, description=description, args_schema=schema,
            )

    def catalog(self, role):
        return [{"name": name, "description": self.registry[name].description,
                 "arguments": self.registry[name].args_schema.model_json_schema()}
                for name in sorted(ALLOWLISTS[role])]

    def add_evidence(self, kind, data):
        content = json.dumps(data, sort_keys=True, default=str)
        digest = hashlib.sha256((self.repository.index["generation"] + kind + content).encode()).hexdigest()
        eid = "ev_" + digest[:16]
        self.evidence[eid] = {"id": eid, "kind": kind, "generation": self.repository.index["generation"],
                              "revision": self.repository.index["revision"], "source_hash": digest, **data}
        return eid

    def execute(self, role, name, arguments):
        self.guard()
        self.budget.take("tool")
        if name not in ALLOWLISTS.get(role, set()):
            return {"status": "error", "error": "Tool is not allowed for this role"}
        tool = self.registry[name]
        try:
            validated = tool.args_schema.model_validate(arguments).model_dump()
        except ValueError:
            return {"status": "error", "error": "Tool arguments do not match the supplied schema"}
        key = name + json.dumps(validated, sort_keys=True)
        if key in self.cache:
            return {**self.cache[key], "cached": True}
        try:
            data = tool.invoke(validated)
            ids = []
            if name in {"semantic_search", "keyword_search"}:
                for c in data:
                    if len(self.candidates) < 20 or c["chunk_id"] in self.candidates:
                        self.candidates[c["chunk_id"]] = {**self.candidates.get(c["chunk_id"], {}), **c}
                # Do not pretend a truncated search snippet is inspected source.
                data = [{k: v for k, v in c.items() if k != "code_content"} for c in data]
            elif name == "read_code":
                if len(self.candidates) < 20 or data["chunk_id"] in self.candidates:
                    full = self.repository.chunk(data["chunk_id"])
                    self.candidates[data["chunk_id"]] = {**self.candidates.get(data["chunk_id"], {}), **full}
                ids = [self.add_evidence("code", data)]
            elif name == "git_history":
                for row in data:
                    row["diff"] = (row.get("diff") or "")[:3000]
                    row["message"] = row["message"][:500]
                    row["coordinate_note"] = "Historical diff; stored patch may be truncated. Current line alignment is unverified."
                    ids.append(self.add_evidence("git", row))
            else:
                for row in data:
                    ids.append(self.add_evidence("dependency", row))
            observation = {"status": "ok" if data else "empty", "data": data, "evidence_ids": ids}
        except LookupError as exc:
            observation = {"status": "unavailable", "error": str(exc)}
        except ValueError as exc:
            observation = {"status": "error", "error": str(exc)[:200]}
        except Exception:
            logger.exception("repository_tool_failed tool=%s", name)
            observation = {"status": "error", "error": f"{name} failed; source service unavailable. No evidence was collected."}
        self.guard()
        self.budget.check()
        # Failed requests are not cached, so a later targeted retry remains possible.
        if observation["status"] in {"ok", "empty", "unavailable"}:
            self.cache[key] = observation
        self.events.append({"tool": name, "status": observation["status"], "evidence_ids": observation.get("evidence_ids", [])})
        return observation

    def validate_refs(self, ids):
        if any(eid not in self.evidence for eid in ids):
            raise ValueError("Model cited an unknown evidence ID")

    def has_code(self, candidate_id, ids):
        return any(self.evidence.get(eid, {}).get("kind") == "code"
                   and self.evidence[eid].get("chunk_id") == candidate_id for eid in ids)

    def packet(self, required_ids=()):
        # Keep cited observations visible to the critic; prioritize source over graph metadata.
        evidence, used = [], 0
        required = set(required_ids)
        records = sorted(self.evidence.values(), key=lambda e: (e["id"] not in required, e["kind"] != "code"))
        for record in records:
            size = len(json.dumps(record, default=str))
            if used + size <= 8500:
                evidence.append(record)
                used += size
            elif record["id"] in required:
                raise ValueError("Required evidence exceeds the review context budget")
        return {"candidates": [{k: c.get(k) for k in ("chunk_id", "file_path", "function_name")}
                                for c in list(self.candidates.values())[:12]], "evidence": evidence}
