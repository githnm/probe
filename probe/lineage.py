"""dbt manifest parser and downstream model discovery."""

from __future__ import annotations

import json
from dataclasses import dataclass, field


@dataclass
class Model:
    unique_id: str
    name: str
    columns: list[str]
    depends_on: list[str]


@dataclass
class LineageGraph:
    models: dict[str, Model] = field(default_factory=dict)
    child_map: dict[str, list[str]] = field(default_factory=dict)

    def downstream(self, model_id: str) -> list[str]:
        visited: list[str] = []
        queue = list(self.child_map.get(model_id, []))
        seen = set(queue)
        while queue:
            nid = queue.pop(0)
            visited.append(nid)
            for child in self.child_map.get(nid, []):
                if child not in seen:
                    seen.add(child)
                    queue.append(child)
        return visited

    def impacted_columns(
        self, model_id: str, changed_columns: list[str] | None = None
    ) -> list[str]:
        source = self.models.get(model_id)
        if source is None:
            return []
        if changed_columns is None:
            changed_columns = source.columns

        hit: set[str] = set()
        frontier = set(changed_columns)

        for downstream_id in self.downstream(model_id):
            dm = self.models.get(downstream_id)
            if dm is None:
                continue
            matched = [c for c in dm.columns if c in frontier]
            for c in matched:
                hit.add(c)
                frontier.add(c)

        return sorted(hit)

    def nodes(self) -> list[str]:
        return [m.name for m in self.models.values()]

    def edges(self) -> list[tuple[str, str]]:
        result = []
        for parent_id, children in self.child_map.items():
            parent = self.models[parent_id].name
            for child_id in children:
                child = self.models[child_id].name
                result.append((parent, child))
        return result

    def resolve(self, name: str) -> str | None:
        for uid, m in self.models.items():
            if m.name == name or uid == name:
                return uid
        return None


def load_manifest(manifest_path: str) -> LineageGraph:
    with open(manifest_path) as f:
        raw = json.load(f)

    graph = LineageGraph()
    nodes = raw.get("nodes", {})

    for uid, node in nodes.items():
        if node.get("resource_type") != "model":
            continue
        cols = list(node.get("columns", {}).keys())
        deps = [
            d for d in node.get("depends_on", {}).get("nodes", [])
            if d.startswith("model.")
        ]
        graph.models[uid] = Model(
            unique_id=uid,
            name=node.get("name", uid),
            columns=cols,
            depends_on=deps,
        )

    if "child_map" in raw:
        for uid in graph.models:
            graph.child_map[uid] = [
                c for c in raw["child_map"].get(uid, [])
                if c in graph.models
            ]
    else:
        for uid in graph.models:
            graph.child_map[uid] = []
        for uid, model in graph.models.items():
            for parent in model.depends_on:
                if parent in graph.child_map:
                    graph.child_map[parent].append(uid)

    return graph
