#!/usr/bin/env python3
"""Validate the shipped project without contacting FilmCraft or the network."""
from __future__ import annotations

import hashlib
import json
import py_compile
import re
import subprocess
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    checks: list[str] = []
    for script in sorted((ROOT / "scripts").glob("*.py")):
        py_compile.compile(str(script), doraise=True)
        checks.append(f"python:{script.name}")
    for script in sorted((ROOT / "scripts").glob("*.sh")):
        result = subprocess.run(["bash", "-n", str(script)], capture_output=True, text=True)
        if result.returncode:
            raise RuntimeError(f"{script}: {result.stderr}")
        checks.append(f"bash:{script.name}")
    for test in sorted((ROOT / "tests").glob("test_*.py")):
        py_compile.compile(str(test), doraise=True)
        result = subprocess.run([sys.executable, str(test)], capture_output=True, text=True, timeout=60)
        if result.returncode:
            raise RuntimeError(f"{test}: {result.stdout}\n{result.stderr}")
        checks.append(f"unit:{test.name}")
    for path in sorted(ROOT.rglob("*.json")):
        if "workspace/runtime" in str(path) or "__pycache__" in str(path):
            continue
        json.loads(path.read_text())
        checks.append(f"json:{path.relative_to(ROOT)}")
    codex = ROOT / ".codex" / "config.toml"
    if codex.exists():
        tomllib.loads(codex.read_text())
        checks.append("toml:.codex/config.toml")
    manifest_path = ROOT / "references" / "upstream-manifest.json"
    manifest = json.loads(manifest_path.read_text())
    if not re.fullmatch(r"[0-9a-f]{40}", manifest["commit"]):
        raise RuntimeError("Invalid upstream commit")
    for record in manifest["files"]:
        path = ROOT / "references" / "upstream" / record["local_path"]
        data = path.read_bytes()
        if len(data) != record["bytes"] or hashlib.sha256(data).hexdigest() != record["sha256"]:
            raise RuntimeError(f"Upstream hash mismatch: {path}")
    checks.append(f"upstream:{len(manifest['files'])} files")
    skill = (ROOT / "SKILL.md").read_text()
    if "TODO" in skill or not skill.startswith("---\nname: filmcraft-agent\n"):
        raise RuntimeError("SKILL.md is incomplete")
    for name in ["AGENTS.md", "references/workflow.md", "references/safety.md",
                 "references/clients.md", "references/recipes.md"]:
        if not (ROOT / name).is_file():
            raise RuntimeError(f"Missing required file: {name}")
    for path in [ROOT / "AGENTS.md", ROOT / "SKILL.md"]:
        text = path.read_text()
        if re.search(r"FILMCRAFT_CONTROL_TOKEN[\"']?\s*[:=]\s*[\"'][0-9a-f]{64}[\"']", text):
            raise RuntimeError(f"Embedded control token: {path}")
    checks.append("rules:complete")
    report = {"status": "passed", "checks": checks, "check_count": len(checks)}
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1)
