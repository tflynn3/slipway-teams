#!/usr/bin/env python3
"""Validate all YAML manifests, embedded JSON Schemas, recipes, and rendered overlays."""

import json
import pathlib
import subprocess

try:
    import yaml as _pyyaml
except ImportError:
    _pyyaml = None

ROOT = pathlib.Path(__file__).resolve().parent.parent


def load_yaml_docs(text: str) -> list:
    if _pyyaml is not None:
        return [doc for doc in _pyyaml.safe_load_all(text) if doc is not None]
    res = subprocess.run(
        ["ruby", "-ryaml", "-rjson", "-e", "puts JSON.generate(YAML.load_stream($stdin.read))"],
        input=text,
        capture_output=True,
        text=True,
        check=True,
    )
    return [doc for doc in json.loads(res.stdout) if doc is not None]


def validate_yaml_files() -> None:
    files = sorted(
        list(ROOT.glob("teams/**/*.yaml"))
        + list(ROOT.glob("bridges/**/*.yaml"))
        + list(ROOT.glob(".github/**/*.yaml"))
    )
    if not files:
        raise SystemExit("no yaml files found")

    doc_count = 0
    for path in files:
        docs = load_yaml_docs(path.read_text(encoding="utf-8"))
        if not docs:
            raise SystemExit(f"{path}: empty YAML file")
        for doc in docs:
            doc_count += 1
            kind = doc.get("kind")
            name = (doc.get("metadata") or {}).get("name", "")
            data = doc.get("data") or {}
            if kind == "ConfigMap" and name.endswith("-schemas"):
                if doc.get("immutable") is not True:
                    raise SystemExit(f"{path}: schema ConfigMap {name} must set immutable: true")
                for raw in data.values():
                    json.loads(raw)
            if kind == "ConfigMap" and "recipe.yaml" in data:
                if doc.get("immutable") is not True:
                    raise SystemExit(f"{path}: recipe ConfigMap {name} must set immutable: true")
                recipe_docs = load_yaml_docs(data["recipe.yaml"])
                if not recipe_docs or not isinstance(recipe_docs[0], dict) or not recipe_docs[0].get("steps"):
                    raise SystemExit(f"{path}: recipe {name} missing steps")
    print(f"Validated {len(files)} YAML files ({doc_count} documents).")


def validate_rendered_teams() -> None:
    script = ROOT / "scripts" / "render-team.sh"
    cases = [
        ("teams/software-factory", ["--overlay", "codex-dual-model"]),
        ("teams/software-factory", ["--overlay", "pr-agent-reviewer"]),
        ("teams/sre-rollout", []),
        ("teams/bug-hunter", []),
    ]
    for team, extra in cases:
        res = subprocess.run(
            [str(script), str(ROOT / team), *extra],
            capture_output=True,
            text=True,
            check=True,
        )
        if "__" in res.stdout:
            raise SystemExit(f"{team} {' '.join(extra)}: unreplaced placeholder token found")
        docs = load_yaml_docs(res.stdout)
        if not docs:
            raise SystemExit(f"{team}: rendered empty YAML")
        print(f"Rendered {team} {' '.join(extra)} -> {len(docs)} valid YAML documents.")


if __name__ == "__main__":
    validate_yaml_files()
    validate_rendered_teams()
