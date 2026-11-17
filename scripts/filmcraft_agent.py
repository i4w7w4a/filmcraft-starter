#!/usr/bin/env python3
"""Setup, diagnostics, documentation and verification for FilmCraft Agent."""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import platform
import re
import secrets
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import time
import tomllib
import urllib.request
from pathlib import Path
from typing import Any

from mcp_client import McpSession, json_content, save_images

ROOT = Path(__file__).resolve().parent.parent
RUNTIME = ROOT / "workspace" / "runtime"
PROBE_PATH = RUNTIME / "probe.json"
MANIFEST_PATH = ROOT / "references" / "upstream-manifest.json"
CORE_TOOLS = {
    "command_list", "command_run", "command_batch", "doc_inspect", "render_preview",
    "project_inspect", "sequence_inspect", "media_import", "render_frame",
}
BRIDGE_TOOLS = {
    "ui_inspect", "ui_elements", "ui_click", "ui_drag", "ui_key", "ui_type",
    "ui_screenshot", "ui_control",
}
JSON_CONFIGS = {
    "kimi": (".kimi-code/mcp.json", "mcpServers"),
    "claude": (".mcp.json", "mcpServers"),
    "cursor": (".cursor/mcp.json", "mcpServers"),
    "gemini": (".gemini/settings.json", "mcpServers"),
    "copilot": (".mcp.json", "mcpServers"),
    "vscode": (".vscode/mcp.json", "servers"),
    "opencode": ("opencode.json", "mcp.servers"),
    "opencode-legacy": ("opencode.json", "mcp"),
    "generic": ("config/mcp.json", "mcpServers"),
}
DEFAULT_CLIENTS = ["kimi", "claude", "copilot", "cursor", "gemini", "opencode", "generic", "codex"]
BEGIN = "# BEGIN FILMCRAFT-AGENT MANAGED"
END = "# END FILMCRAFT-AGENT MANAGED"


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def atomic_write(path: Path, data: str | bytes, mode: int = 0o644) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = data.encode() if isinstance(data, str) else data
    fd, tmp = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(tmp, mode)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def dump_json(path: Path, value: Any, mode: int = 0o644) -> None:
    atomic_write(path, json.dumps(value, indent=2, ensure_ascii=False) + "\n", mode)


def run(command: list[str], *, timeout: float = 30, cwd: Path | None = None,
        env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=cwd, env=env, text=True, encoding="utf-8",
                          errors="replace", capture_output=True, timeout=timeout)


def resolve_executable(explicit: str | None, name: str) -> str | None:
    if explicit:
        path = Path(explicit).expanduser()
        if path.is_file():
            return str(path.resolve())
        found = shutil.which(explicit)
        return str(Path(found).resolve()) if found else None
    found = shutil.which(name)
    if found:
        return str(Path(found).resolve())
    candidates = [Path("/usr/bin") / name, Path("/usr/local/bin") / name,
                  Path("/opt/ArtCraft/FilmCraft") / name]
    for path in candidates:
        if path.is_file():
            return str(path.resolve())
    return None


def version_of(executable: str | None) -> str | None:
    if not executable:
        return None
    try:
        result = run([executable, "--version"], timeout=20)
    except (OSError, subprocess.TimeoutExpired):
        return None
    output = (result.stdout or result.stderr).strip()
    return output if result.returncode == 0 else f"error({result.returncode}): {output}"


def package_owner(executable: str | None) -> dict[str, str] | None:
    if not executable:
        return None
    commands = [["dpkg-query", "-S", executable], ["rpm", "-qf", executable]]
    for command in commands:
        if not shutil.which(command[0]):
            continue
        try:
            result = run(command, timeout=15)
        except (OSError, subprocess.TimeoutExpired):
            continue
        if result.returncode == 0:
            return {"manager": command[0], "record": result.stdout.strip()}
    return None


def probe(args: argparse.Namespace) -> dict[str, Any]:
    cli = resolve_executable(args.cli, "filmcraft-cli")
    app = resolve_executable(args.app, "filmcraft")
    agents = {name: shutil.which(name) for name in
              ["kimi", "codex", "claude", "cursor", "opencode", "gemini", "code"]}
    cli_version = version_of(cli)
    match = re.search(r"\d+\.\d+\.\d+", cli_version or "")
    manifest: dict[str, Any] = {}
    if MANIFEST_PATH.exists():
        manifest = json.loads(MANIFEST_PATH.read_text())
    expected_tag = f"v{match.group(0)}" if match else None
    report = {
        "created_at": utc_now(), "host": {
            "system": platform.system(), "release": platform.release(), "machine": platform.machine(),
            "python": platform.python_version(), "xdg_session_type": os.environ.get("XDG_SESSION_TYPE"),
            "display_present": bool(os.environ.get("DISPLAY")),
            "wayland_display_present": bool(os.environ.get("WAYLAND_DISPLAY")),
        },
        "filmcraft": {
            "cli": cli, "app": app, "cli_version": cli_version, "app_version": version_of(app),
            "package": package_owner(cli), "expected_doc_tag": expected_tag,
            "bundled_doc_tag": manifest.get("tag"), "bundled_doc_commit": manifest.get("commit"),
            "docs_match": expected_tag is not None and expected_tag == manifest.get("tag"),
        },
        "agents": agents,
        "validators": {"ffmpeg": shutil.which("ffmpeg"), "ffprobe": shutil.which("ffprobe"),
                       "git": shutil.which("git")},
        "notes": [
            "No environment values or control tokens are recorded.",
            "AppImage, Flatpak and custom installations may require --app/--cli or FILMCRAFT_APP/FILMCRAFT_CLI.",
            "A documentation mismatch is a warning, not proof that MCP is incompatible; run smoke tests.",
        ],
    }
    RUNTIME.mkdir(parents=True, exist_ok=True)
    os.chmod(RUNTIME, 0o700)
    dump_json(PROBE_PATH, report, 0o600)
    return report


def load_probe(args: argparse.Namespace) -> dict[str, Any]:
    if PROBE_PATH.exists() and not args.cli and not args.app:
        return json.loads(PROBE_PATH.read_text())
    return probe(args)


def backup_file(path: Path) -> str | None:
    if not path.exists():
        return None
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    destination = RUNTIME / "config-backup" / stamp / path.relative_to(ROOT)
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, destination)
    return str(destination)


def validate_address(address: str) -> str:
    try:
        host, port_text = address.rsplit(":", 1)
        port = int(port_text)
    except ValueError as exc:
        raise ValueError(f"Invalid control address: {address!r}") from exc
    if host not in {"127.0.0.1", "localhost"} or not 1 <= port <= 65535:
        raise ValueError("Control address must be 127.0.0.1:<1-65535> or localhost:<port>")
    return address


def server_entries(cli: str, address: str, project: Path | None) -> dict[str, Any]:
    headless_args = ["mcp"]
    if project:
        headless_args += ["--project", str(project.resolve())]
    return {
        "filmcraft": {"command": cli, "args": ["mcp", "--bridge", address]},
        "filmcraft-headless": {"command": cli, "args": headless_args},
    }


def config_section(data: dict[str, Any], key: str) -> dict[str, Any]:
    if key == "mcp.servers":
        parent = data.setdefault("mcp", {})
        if not isinstance(parent, dict):
            raise ValueError("mcp must be an object")
        section = parent.setdefault("servers", {})
    else:
        section = data.setdefault(key, {})
    if not isinstance(section, dict):
        raise ValueError(f"{key} must be an object")
    return section


def merge_json_config(path: Path, key: str, entries: dict[str, Any], client: str) -> None:
    data: dict[str, Any] = {}
    if path.exists():
        data = json.loads(path.read_text())
        if not isinstance(data, dict):
            raise ValueError(f"{path}: top level must be an object")
    config_section(data, key)  # validate before backup/write
    backup_file(path)
    section = config_section(data, key)
    if path.name == "opencode.json":
        parent = data.get("mcp", {})
        legacy = parent if key == "mcp.servers" else parent.get("servers", {})
        for name in entries:
            if isinstance(legacy, dict):
                legacy.pop(name, None)
    for name, entry in entries.items():
        if client == "copilot":
            entry = {"type": "stdio", **entry}
        elif key == "servers":
            entry = {"type": "stdio", **entry}
        elif key in {"mcp", "mcp.servers"} and path.name == "opencode.json":
            entry = {"type": "local", "command": [entry["command"], *entry["args"]]}
            if key == "mcp":
                entry["enabled"] = True
        if key == "mcpServers" and path.parts[-2:-1] == (".kimi-code",):
            entry = {**entry, "startupTimeoutMs": 30000, "toolTimeoutMs": 120000}
        section[name] = entry
    if path.name == "opencode.json":
        data.setdefault("$schema", "https://opencode.ai/config.json")
    dump_json(path, data)


def codex_block(cli: str, address: str, project: Path | None) -> str:
    headless_args = ["mcp"] + (["--project", str(project.resolve())] if project else [])
    def toml_array(values: list[str]) -> str:
        return "[" + ", ".join(json.dumps(v) for v in values) + "]"
    return f"""{BEGIN}
# Generated locally. No credentials are stored here.
[mcp_servers.filmcraft]
command = {json.dumps(cli)}
args = {toml_array(['mcp', '--bridge', address])}
cwd = {json.dumps(str(ROOT))}
env_vars = ["FILMCRAFT_CONTROL_TOKEN"]
startup_timeout_sec = 30
tool_timeout_sec = 120
default_tools_approval_mode = "writes"

[mcp_servers.filmcraft-headless]
command = {json.dumps(cli)}
args = {toml_array(headless_args)}
cwd = {json.dumps(str(ROOT))}
startup_timeout_sec = 30
tool_timeout_sec = 120
default_tools_approval_mode = "writes"
{END}
"""


def merge_codex_config(path: Path, block: str) -> None:
    old = path.read_text() if path.exists() else ""
    start = old.find(BEGIN)
    end = old.find(END)
    if (start == -1) != (end == -1):
        raise ValueError(f"{path}: incomplete managed block; repair it before continuing")
    if start >= 0:
        end += len(END)
        new = old[:start] + block.rstrip("\n") + old[end:]
    else:
        if old:
            existing = tomllib.loads(old)
            servers = existing.get("mcp_servers", {})
            conflicts = {"filmcraft", "filmcraft-headless"}.intersection(servers)
            if conflicts:
                raise ValueError(f"{path}: existing unmanaged FilmCraft servers: {sorted(conflicts)}")
        new = old.rstrip() + ("\n\n" if old.strip() else "") + block
    tomllib.loads(new)
    backup_file(path)
    atomic_write(path, new if new.endswith("\n") else new + "\n")


def configure(args: argparse.Namespace) -> dict[str, Any]:
    report = load_probe(args)
    cli = report["filmcraft"]["cli"]
    if not cli:
        raise RuntimeError("filmcraft-cli not found; pass --cli /absolute/path/filmcraft-cli")
    validate_address(args.address)
    if args.project and (not args.project.is_file() or args.project.suffix.lower() != ".fcproj"):
        raise ValueError("--project must name an existing .fcproj working copy")
    entries = server_entries(cli, args.address, args.project)
    selected = args.clients or list(DEFAULT_CLIENTS)
    # Preflight every target before the first write, so a bad existing config cannot leave a partial rollout.
    for client in selected:
        if client == "codex":
            path = ROOT / ".codex" / "config.toml"
            old = path.read_text() if path.exists() else ""
            start, end = old.find(BEGIN), old.find(END)
            if (start == -1) != (end == -1):
                raise ValueError(f"{path}: incomplete managed block")
            if old and start == -1:
                servers = tomllib.loads(old).get("mcp_servers", {})
                conflicts = {"filmcraft", "filmcraft-headless"}.intersection(servers)
                if conflicts:
                    raise ValueError(f"{path}: existing unmanaged FilmCraft servers: {sorted(conflicts)}")
        else:
            relative, key = JSON_CONFIGS[client]
            path = ROOT / relative
            if path.exists():
                data = json.loads(path.read_text())
                if not isinstance(data, dict):
                    raise ValueError(f"{path}: top level must be an object")
                try:
                    config_section(data, key)
                except ValueError as exc:
                    raise ValueError(f"{path}: {exc}") from exc
    written: list[str] = []
    for client in selected:
        if client == "codex":
            path = ROOT / ".codex" / "config.toml"
            merge_codex_config(path, codex_block(cli, args.address, args.project))
        elif client in JSON_CONFIGS:
            relative, key = JSON_CONFIGS[client]
            path = ROOT / relative
            merge_json_config(path, key, entries, client)
        else:
            raise ValueError(f"Unknown client: {client}")
        written.append(str(path.relative_to(ROOT)))
    result = {"created_at": utc_now(), "cli": cli, "address": args.address,
              "project": str(args.project) if args.project else None,
              "clients": selected, "written": written, "token_stored": False}
    dump_json(RUNTIME / "configuration.json", result, 0o600)
    return result


def dump_commands(args: argparse.Namespace) -> dict[str, Any]:
    report = load_probe(args)
    cli = report["filmcraft"]["cli"]
    if not cli:
        raise RuntimeError("filmcraft-cli not found")
    result = run([cli, "commands", "--json"], timeout=90)
    if result.returncode != 0:
        raise RuntimeError(f"commands --json failed: {result.stderr.strip()}")
    commands = json.loads(result.stdout)
    if not isinstance(commands, list) or not all(isinstance(x, dict) for x in commands):
        raise RuntimeError("Unexpected command catalog shape")
    payload = {"created_at": utc_now(), "cli_version": report["filmcraft"]["cli_version"],
               "count": len(commands), "sha256": hashlib.sha256(result.stdout.encode()).hexdigest(),
               "commands": commands}
    dump_json(ROOT / "references" / "commands.local.json", payload)
    return {k: v for k, v in payload.items() if k != "commands"}


def verify_export_file(path: Path, *, decode: bool = False, visual: bool = False,
                       expected_duration: float | None = None) -> dict[str, Any]:
    path = path.resolve()
    if not path.is_file() or path.stat().st_size == 0:
        raise RuntimeError(f"Export missing or empty: {path}")
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    report: dict[str, Any] = {"path": str(path), "bytes": path.stat().st_size,
                              "sha256": digest.hexdigest()}
    ffprobe = shutil.which("ffprobe")
    if ffprobe:
        result = run([ffprobe, "-v", "error", "-show_format", "-show_streams", "-of", "json", str(path)], timeout=90)
        if result.returncode != 0:
            raise RuntimeError(f"ffprobe rejected {path}: {result.stderr.strip()}")
        metadata = json.loads(result.stdout)
        streams = metadata.get("streams", [])
        report["metadata"] = metadata
        report["stream_types"] = [s.get("codec_type") for s in streams]
        if not streams:
            raise RuntimeError("Export has no streams")
        duration = float(metadata.get("format", {}).get("duration", 0) or 0)
        report["duration_seconds"] = duration
        if expected_duration is not None and abs(duration - expected_duration) > 0.25:
            raise RuntimeError(f"Duration {duration:g}s differs from expected {expected_duration:g}s")
    else:
        report["warning"] = "ffprobe unavailable; only file existence, size and hash were checked"
    if visual:
        ffmpeg = shutil.which("ffmpeg")
        if not ffmpeg:
            raise RuntimeError("--visual requires ffmpeg")
        duration = report.get("duration_seconds", expected_duration)
        if not duration or duration <= 0:
            raise RuntimeError("Visual verification needs a known positive duration")
        midpoint = duration / 2
        extracted = subprocess.run([ffmpeg, "-v", "error", "-ss", f"{midpoint:.6f}", "-i", str(path),
                                    "-frames:v", "1", "-vf", "scale=32:32", "-f", "rawvideo",
                                    "-pix_fmt", "rgb24", "-"], capture_output=True, timeout=90)
        expected_bytes = 32 * 32 * 3
        if extracted.returncode != 0 or len(extracted.stdout) != expected_bytes:
            raise RuntimeError(f"Could not extract an RGB frame: {extracted.stderr.decode(errors='replace')}")
        pixels = extracted.stdout
        means = [sum(pixels[channel::3]) / (32 * 32) for channel in range(3)]
        deviations = [(sum((value - means[channel]) ** 2 for value in pixels[channel::3]) / (32 * 32)) ** 0.5
                      for channel in range(3)]
        report["visual_midpoint"] = {"seconds": midpoint, "rgb_mean": means, "rgb_stddev": deviations}
        if max(means) < 2 or max(deviations) < 5:
            raise RuntimeError(f"Midpoint frame is black or lacks visual content: {report['visual_midpoint']}")
    if decode:
        ffmpeg = shutil.which("ffmpeg")
        if not ffmpeg:
            raise RuntimeError("--decode requires ffmpeg")
        result = run([ffmpeg, "-v", "error", "-i", str(path), "-f", "null", "-"], timeout=180)
        if result.returncode != 0 or result.stderr.strip():
            raise RuntimeError(f"Full decode failed: {result.stderr.strip()}")
        report["full_decode"] = "passed"
    return report


def update_docs(args: argparse.Namespace) -> dict[str, Any]:
    if not args.yes:
        raise RuntimeError("Documentation replacement requires --yes; a backup will be created")
    tag = args.tag
    if not tag:
        report = load_probe(args)
        bundled_tag = json.loads(MANIFEST_PATH.read_text())["tag"] if MANIFEST_PATH.exists() else None
        tag = report["filmcraft"].get("expected_doc_tag") or bundled_tag
    if not tag:
        raise RuntimeError("Cannot choose a documentation tag; pass --tag vX.Y.Z")
    if not re.fullmatch(r"v\d+\.\d+\.\d+", tag):
        raise ValueError(f"Expected a release tag such as v0.20.1, got {tag!r}")
    repo = args.repo or "https://github.com/storytold/filmcraft"
    if args.commit:
        if not re.fullmatch(r"[0-9a-f]{40}", args.commit):
            raise ValueError("--commit must contain a full 40-character commit SHA")
        release = {"target_commitish": args.commit, "published_at": None}
    else:
        request = urllib.request.Request(f"https://api.github.com/repos/storytold/filmcraft/releases/tags/{tag}",
                                         headers={"User-Agent": "filmcraft-agent"})
        release = None
        for attempt in range(2):
            try:
                with urllib.request.urlopen(request, timeout=60) as response:
                    release = json.load(response)
                break
            except OSError:
                if attempt:
                    raise
                time.sleep(2)
    clone_source = repo if repo.endswith(".git") or Path(repo).exists() else f"{repo}.git"
    with tempfile.TemporaryDirectory(prefix="filmcraft-docs-") as temporary:
        checkout = Path(temporary) / "source"
        clone = None
        for attempt, transport in enumerate(["HTTP/1.1", "HTTP/2"]):
            if checkout.exists():
                shutil.rmtree(checkout)
            clone = run(["git", "-c", f"http.version={transport}", "clone", "--depth", "1", "--branch", tag,
                         "--filter=blob:none", "--sparse", clone_source, str(checkout)], timeout=300)
            if clone.returncode == 0:
                break
            if attempt == 0:
                time.sleep(2)
        if clone.returncode != 0:
            raise RuntimeError(f"git clone failed after two transports: {clone.stderr.strip()}")
        patterns = ["/docs/**", "/README.md", "/ROADMAP.md", "/SECURITY.md", "/LICENSE-APACHE",
                    "/LICENSE-MIT", "/NOTICE", "/.mcp.json"]
        sparse = None
        for attempt, transport in enumerate(["HTTP/1.1", "HTTP/2"]):
            sparse = run(["git", "-c", f"http.version={transport}", "sparse-checkout", "set",
                          "--no-cone", *patterns], cwd=checkout, timeout=300)
            if sparse.returncode == 0:
                break
            if attempt == 0:
                time.sleep(2)
        if sparse.returncode != 0:
            raise RuntimeError(f"sparse checkout failed after two transports: {sparse.stderr.strip()}")
        commit = run(["git", "rev-parse", "HEAD"], cwd=checkout).stdout.strip()
        if commit != release["target_commitish"]:
            raise RuntimeError(f"Tag commit {commit} differs from release {release['target_commitish']}")
        staged = Path(temporary) / "staged"
        staged.mkdir()
        records: list[dict[str, Any]] = []
        files = [p for p in (checkout / "docs").rglob("*") if p.is_file()]
        files += [checkout / name for name in
                  ["README.md", "ROADMAP.md", "SECURITY.md", "LICENSE-APACHE", "LICENSE-MIT", "NOTICE", ".mcp.json"]]
        for source in files:
            relative = source.relative_to(checkout)
            local = Path("mcp.source.json") if str(relative) == ".mcp.json" else relative
            destination = staged / local
            destination.parent.mkdir(parents=True, exist_ok=True)
            data = source.read_bytes()
            destination.write_bytes(data)
            records.append({"source_path": str(relative), "local_path": str(local),
                            "url": f"https://raw.githubusercontent.com/storytold/filmcraft/{tag}/{relative}",
                            "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)})
        manifest = {"upstream": repo, "tag": tag, "commit": commit,
                    "release_published_at": release["published_at"], "retrieved_at": utc_now(), "files": records}
        dump_json(staged / "upstream-manifest.json", manifest)
        destination = ROOT / "references" / "upstream"
        backup = RUNTIME / "docs-backup" / f"{int(time.time())}"
        if destination.exists():
            backup.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(destination, backup / "upstream")
            if MANIFEST_PATH.exists():
                shutil.copy2(MANIFEST_PATH, backup / "upstream-manifest.json")
        old = ROOT / "references" / ".upstream.old"
        if old.exists():
            shutil.rmtree(old)
        if destination.exists():
            destination.rename(old)
        staged.rename(destination)
        dump_json(MANIFEST_PATH, manifest)
        if old.exists():
            shutil.rmtree(old)
        lock_path = ROOT / "VERSION.lock.json"
        if lock_path.exists():
            lock = json.loads(lock_path.read_text())
            lock["upstream"] = {"tag": tag, "commit": commit,
                                "releasePublishedAt": release["published_at"]}
            dump_json(lock_path, lock)
    return {"tag": tag, "commit": commit, "files": len(records),
            "bytes": sum(x["bytes"] for x in records), "backup": str(backup)}


def control_request(address: str, token: str, method: str = "ui.inspect",
                    params: dict[str, Any] | None = None, timeout: float = 5) -> dict[str, Any]:
    validate_address(address)
    host, port_text = address.rsplit(":", 1)
    with socket.create_connection((host, int(port_text)), timeout=timeout) as connection:
        connection.settimeout(timeout)
        request = {"id": 1, "token": token, "method": method, "params": params or {}}
        connection.sendall(json.dumps(request).encode() + b"\n")
        file = connection.makefile("rb")
        line = file.readline(6 * 1024 * 1024)
    response = json.loads(line)
    if not response.get("ok"):
        raise RuntimeError(str(response.get("error", "control request failed")))
    return response


def start_desktop(app: str, address: str, data_dir: Path, *, graphics: str | None,
                  project: Path | None = None, demo: bool = True,
                  isolated_input: bool = True) -> tuple[subprocess.Popen[str], dict[str, str], str, Path]:
    validate_address(address)
    if project and (not project.is_file() or project.suffix.lower() != ".fcproj"):
        raise ValueError("project must name an existing .fcproj working copy")
    token = os.environ.get("FILMCRAFT_CONTROL_TOKEN") or secrets.token_hex(32)
    if not re.fullmatch(r"[0-9a-f]{64}", token):
        raise ValueError("FILMCRAFT_CONTROL_TOKEN must contain exactly 64 lowercase hex characters")
    env = os.environ.copy()
    env["FILMCRAFT_CONTROL_TOKEN"] = token
    log_dir = data_dir / "agent-logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    os.chmod(log_dir, 0o700)
    log_path = log_dir / f"desktop-{int(time.time())}.log"
    command = [app, "--control", address.rsplit(":", 1)[1], "--no-recover"]
    if isolated_input:
        command.append("--control-input-only")
    command += ["--data-dir", str(data_dir)]
    if demo:
        command.append("--demo")
    elif project:
        command.append(str(project.resolve()))
    else:
        command.append("--empty")
    if graphics:
        command += ["--graphics", graphics]
    with log_path.open("w") as log:
        process = subprocess.Popen(command, cwd=ROOT, env=env, stdout=log, stderr=log,
                                   text=True, start_new_session=True)
    return process, env, token, log_path


def wait_for_desktop(process: subprocess.Popen[str], address: str, token: str,
                     timeout: float = 90) -> None:
    deadline = time.monotonic() + timeout
    last_error = "not ready"
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"FilmCraft exited during startup with code {process.returncode}")
        try:
            control_request(address, token, timeout=3)
            return
        except (OSError, ValueError, RuntimeError, json.JSONDecodeError) as exc:
            last_error = str(exc)
            time.sleep(0.5)
    raise RuntimeError(f"FilmCraft control did not become ready: {last_error}")


def stop_started_desktop(process: subprocess.Popen[str]) -> None:
    if process.poll() is not None:
        return
    try:
        os.killpg(process.pid, signal.SIGTERM)
        process.wait(timeout=10)
    except (ProcessLookupError, subprocess.TimeoutExpired):
        if process.poll() is None:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait(timeout=5)


def smoke_headless(args: argparse.Namespace) -> dict[str, Any]:
    report = load_probe(args)
    cli = report["filmcraft"]["cli"]
    if not cli:
        raise RuntimeError("filmcraft-cli not found")
    output = RUNTIME / "smoke" / f"headless-{int(time.time())}"
    output.mkdir(parents=True, exist_ok=True)
    os.chmod(output, 0o700)
    with McpSession([cli, "mcp", "--demo"], timeout=180) as session:
        tools = session.tools()
        names = {tool["name"] for tool in tools}
        missing = (CORE_TOOLS | BRIDGE_TOOLS) - names
        if missing:
            raise RuntimeError(f"MCP tools missing: {sorted(missing)}")
        resources = session.request("resources/list", {}).get("resources", [])
        uris = {item.get("uri") for item in resources}
        if not {"filmcraft://document", "filmcraft://commands"}.issubset(uris):
            raise RuntimeError(f"MCP resources missing: {sorted(uris)}")
        document = json_content(session.call("doc_inspect"))
        if not document.get("project") or not document.get("sequence"):
            raise RuntimeError("Demo document did not contain a project and active sequence")
        catalog = json_content(session.call("command_list", {"filter": "timeline.razor"}))
        if not any(item.get("id") == "timeline.razor" for item in catalog):
            raise RuntimeError("timeline.razor not found in live catalog")
        cut = json_content(session.call("command_run", {
            "id": "sequence.addEditAllTracks", "params": {"seconds": 2.0}}))
        if int(cut.get("cuts", 0)) < 1:
            raise RuntimeError(f"Reversible edit made no cut: {cut}")
        session.call("command_run", {"id": "edit.undo", "params": {}})
        images = save_images(session.call("render_frame", {"seconds": 1.0, "max_side": 320}),
                             output, "frame")
        export_path = output / "smoke.mp4"
        exported = json_content(session.call("command_run", {
            "id": "file.exportMedia", "params": {
                "path": str(export_path), "format": "h264", "width": 640, "height": 360,
                "audio": False, "range": "custom", "startSeconds": 1.0, "endSeconds": 1.5,
                "wait": True,
            },
        }, timeout=240))
        if exported.get("offlineMedia"):
            raise RuntimeError(f"Export contains offline media: {exported['offlineMedia']}")
        actual_path = Path(exported.get("path", export_path))
        validation = verify_export_file(actual_path, decode=args.decode, visual=True, expected_duration=0.5)
        if "stream_types" in validation and "video" not in validation["stream_types"]:
            raise RuntimeError(f"Export has no video stream: {validation['stream_types']}")
        result = {
            "status": "passed", "created_at": utc_now(), "mode": "headless",
            "server": session.server_info.get("serverInfo"), "protocol": session.server_info.get("protocolVersion"),
            "tool_count": len(tools), "command_catalog_matches": len(catalog),
            "reversible_edit": cut, "undo": "called", "images": [str(p) for p in images],
            "export_result": exported, "export_validation": validation,
            "output_directory": str(output),
        }
    dump_json(output / "report.json", result, 0o600)
    dump_json(ROOT / "tests" / "results" / "headless.local.json", result, 0o600)
    return result


def smoke_bridge(args: argparse.Namespace) -> dict[str, Any]:
    report = load_probe(args)
    cli, app = report["filmcraft"]["cli"], report["filmcraft"]["app"]
    if not cli or not app:
        raise RuntimeError("Both filmcraft and filmcraft-cli are required")
    output = RUNTIME / "smoke" / f"bridge-{int(time.time())}"
    data_dir = output / "data"
    output.mkdir(parents=True, exist_ok=True)
    os.chmod(output, 0o700)
    process, env, token, log_path = start_desktop(app, args.address, data_dir,
                                                  graphics=args.graphics, demo=True)
    try:
        wait_for_desktop(process, args.address, token)
        with McpSession([cli, "mcp", "--bridge", args.address], env=env, timeout=90) as session:
            tools = session.tools()
            names = {tool["name"] for tool in tools}
            missing = (CORE_TOOLS | BRIDGE_TOOLS) - names
            if missing:
                raise RuntimeError(f"Bridge tools missing: {sorted(missing)}")
            ui = json_content(session.call("ui_inspect"))
            elements = json_content(session.call("ui_elements", {"prefix": "tools."}))
            images = save_images(session.call("ui_screenshot", {"max_side": 800}), output, "window")
            result = {
                "status": "passed", "created_at": utc_now(), "mode": "bridge",
                "server": session.server_info.get("serverInfo"), "tool_count": len(tools),
                "ui_inspect_received": bool(ui), "tool_element_count": len(elements) if isinstance(elements, list) else None,
                "images": [str(p) for p in images], "desktop_log": str(log_path),
                "isolated_demo": True, "user_project_touched": False, "output_directory": str(output),
            }
        dump_json(output / "report.json", result, 0o600)
        dump_json(ROOT / "tests" / "results" / "bridge.local.json", result, 0o600)
        return result
    finally:
        stop_started_desktop(process)


def start_bridge(args: argparse.Namespace) -> dict[str, Any]:
    report = load_probe(args)
    cli, app = report["filmcraft"]["cli"], report["filmcraft"]["app"]
    if not cli or not app:
        raise RuntimeError("Both filmcraft and filmcraft-cli are required")
    validate_address(args.address)
    if args.stop_app and args.project:
        raise ValueError("--stop-app is allowed only for an isolated demo, never for a real project")
    command = args.command
    if not command:
        if not args.agent:
            raise RuntimeError("Choose --agent or provide a command after --")
        executable = shutil.which(args.agent)
        if not executable:
            raise RuntimeError(f"Agent executable not found: {args.agent}")
        command = [executable]
    token = os.environ.get("FILMCRAFT_CONTROL_TOKEN")
    started = False
    process = None
    env = os.environ.copy()
    log_path = None
    if token:
        control_request(args.address, token)
    else:
        data_dir = args.data_dir or (RUNTIME / "bridge-data")
        process, env, token, log_path = start_desktop(app, args.address, data_dir,
                                                      graphics=args.graphics, project=args.project,
                                                      demo=not args.project)
        started = True
        wait_for_desktop(process, args.address, token)
    completed = subprocess.run(command, cwd=ROOT, env=env)
    if started and args.stop_app:
        stop_started_desktop(process)
    return {"agent_exit_code": completed.returncode, "app_started_by_wrapper": started,
            "app_left_running": bool(started and not args.stop_app and process.poll() is None),
            "desktop_log": str(log_path) if log_path else None,
            "note": "The token was inherited by the agent and was not written to disk."}


def make_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--cli", default=os.environ.get("FILMCRAFT_CLI"))
    common.add_argument("--app", default=os.environ.get("FILMCRAFT_APP"))
    sub = parser.add_subparsers(dest="action", required=True)
    p = sub.add_parser("probe", parents=[common]); p.set_defaults(function=lambda a: probe(a))
    p = sub.add_parser("configure", parents=[common])
    p.add_argument("--address", default="127.0.0.1:9876")
    p.add_argument("--project", type=Path)
    p.add_argument("--clients", nargs="+", choices=[*JSON_CONFIGS, "codex"])
    p.set_defaults(function=lambda a: configure(a))
    p = sub.add_parser("bootstrap", parents=[common])
    p.add_argument("--address", default="127.0.0.1:9876")
    p.add_argument("--project", type=Path)
    p.add_argument("--clients", nargs="+", choices=[*JSON_CONFIGS, "codex"])
    p.add_argument("--skip-commands", action="store_true")
    p.add_argument("--refresh", action="store_true", help="Redetect FilmCraft instead of reusing the previous local probe")
    def bootstrap(a: argparse.Namespace) -> dict[str, Any]:
        environment = probe(a) if a.refresh else load_probe(a)
        configuration = configure(a)
        commands = None if a.skip_commands else dump_commands(a)
        result = {"probe": environment, "configuration": configuration, "commands": commands}
        dump_json(RUNTIME / "bootstrap.json", result, 0o600)
        return result
    p.set_defaults(function=bootstrap)
    p = sub.add_parser("dump-commands", parents=[common]); p.set_defaults(function=lambda a: dump_commands(a))
    p = sub.add_parser("verify-export")
    p.add_argument("path", type=Path); p.add_argument("--decode", action="store_true")
    p.add_argument("--visual", action="store_true")
    p.add_argument("--expected-duration", type=float)
    p.set_defaults(function=lambda a: verify_export_file(a.path, decode=a.decode, visual=a.visual, expected_duration=a.expected_duration))
    p = sub.add_parser("update-docs", parents=[common])
    p.add_argument("--tag"); p.add_argument("--yes", action="store_true")
    p.add_argument("--repo", help="Official URL by default; an explicit trusted Git mirror is also accepted")
    p.add_argument("--commit", help="Expected full commit SHA; skips the release API lookup for offline mirrors")
    p.set_defaults(function=lambda a: update_docs(a))
    p = sub.add_parser("smoke-headless", parents=[common])
    p.add_argument("--decode", action="store_true"); p.set_defaults(function=lambda a: smoke_headless(a))
    p = sub.add_parser("smoke-bridge", parents=[common])
    p.add_argument("--address", default="127.0.0.1:9876")
    p.add_argument("--graphics", choices=["default", "low-power", "software"], default="software")
    p.set_defaults(function=lambda a: smoke_bridge(a))
    p = sub.add_parser("start-bridge", parents=[common])
    p.add_argument("--address", default="127.0.0.1:9876")
    p.add_argument("--graphics", choices=["default", "low-power", "software"])
    p.add_argument("--project", type=Path); p.add_argument("--data-dir", type=Path)
    p.add_argument("--agent", choices=["kimi", "codex", "claude", "opencode", "gemini", "code"])
    p.add_argument("--stop-app", action="store_true")
    p.add_argument("command", nargs=argparse.REMAINDER)
    p.set_defaults(function=lambda a: start_bridge(a))
    return parser


def main() -> int:
    args = make_parser().parse_args()
    if getattr(args, "command", None) and args.command[0] == "--":
        args.command = args.command[1:]
    result = args.function(args)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    if args.action == "start-bridge":
        return int(result["agent_exit_code"])
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (RuntimeError, ValueError, OSError, subprocess.TimeoutExpired, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1)
