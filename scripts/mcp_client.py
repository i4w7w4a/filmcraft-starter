#!/usr/bin/env python3
"""Small, dependency-free MCP stdio client for FilmCraft and smoke tests."""
from __future__ import annotations

import argparse
import base64
import json
import os
import queue
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any


class McpError(RuntimeError):
    pass


class McpSession:
    def __init__(self, command: list[str], *, cwd: Path | None = None,
                 env: dict[str, str] | None = None, timeout: float = 60.0):
        self.command = command
        self.timeout = timeout
        self._next_id = 0
        self.notifications: list[dict[str, Any]] = []
        self.stderr_lines: list[str] = []
        self._messages: queue.Queue[Any] = queue.Queue()
        self.process = subprocess.Popen(
            command, cwd=cwd, env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, text=True, encoding="utf-8", bufsize=1,
        )
        self._stdout_thread = threading.Thread(target=self._read_stdout, daemon=True)
        self._stderr_thread = threading.Thread(target=self._read_stderr, daemon=True)
        self._stdout_thread.start()
        self._stderr_thread.start()

    def _read_stdout(self) -> None:
        assert self.process.stdout is not None
        try:
            for line in self.process.stdout:
                try:
                    self._messages.put(json.loads(line))
                except json.JSONDecodeError as exc:
                    self._messages.put(McpError(f"Non-JSON MCP output: {line[:300]!r}"))
        except Exception as exc:
            self._messages.put(exc)
        finally:
            self._messages.put(None)

    def _read_stderr(self) -> None:
        assert self.process.stderr is not None
        for line in self.process.stderr:
            self.stderr_lines.append(line.rstrip())

    def __enter__(self) -> "McpSession":
        try:
            self.initialize()
            return self
        except Exception:
            self.close()
            raise

    def __exit__(self, *_: object) -> None:
        self.close()

    def close(self) -> None:
        if self.process.poll() is None:
            try:
                if self.process.stdin:
                    self.process.stdin.close()
                self.process.wait(timeout=5)
            except (OSError, subprocess.TimeoutExpired):
                self.process.terminate()
                try:
                    self.process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    self.process.kill()
                    self.process.wait(timeout=3)

    def _send(self, message: dict[str, Any]) -> None:
        if self.process.poll() is not None:
            detail = "\n".join(self.stderr_lines[-20:])
            raise McpError(f"MCP server exited ({self.process.returncode}): {detail}")
        assert self.process.stdin is not None
        self.process.stdin.write(json.dumps(message, separators=(",", ":")) + "\n")
        self.process.stdin.flush()

    def notify(self, method: str, params: dict[str, Any] | None = None) -> None:
        message: dict[str, Any] = {"jsonrpc": "2.0", "method": method}
        if params is not None:
            message["params"] = params
        self._send(message)

    def _read_message(self, timeout: float) -> dict[str, Any]:
        try:
            message = self._messages.get(timeout=timeout)
        except queue.Empty as exc:
            raise McpError(f"MCP response timeout after {timeout:g}s") from exc
        if message is None:
            detail = "\n".join(self.stderr_lines[-20:])
            raise McpError(f"MCP stdout closed: {detail}")
        if isinstance(message, Exception):
            raise McpError(str(message)) from message
        return message

    def request(self, method: str, params: dict[str, Any] | None = None,
                *, timeout: float | None = None) -> Any:
        self._next_id += 1
        request_id = self._next_id
        message: dict[str, Any] = {"jsonrpc": "2.0", "id": request_id, "method": method}
        if params is not None:
            message["params"] = params
        self._send(message)
        deadline = time.monotonic() + (self.timeout if timeout is None else timeout)
        while True:
            response = self._read_message(max(0.001, deadline - time.monotonic()))
            if response.get("id") != request_id:
                if "method" in response:
                    self.notifications.append(response)
                continue
            if "error" in response:
                error = response["error"]
                raise McpError(f"{method}: JSON-RPC {error.get('code')}: {error.get('message')}")
            return response.get("result", {})

    def initialize(self) -> dict[str, Any]:
        result = self.request("initialize", {
            "protocolVersion": "2025-06-18",
            "capabilities": {},
            "clientInfo": {"name": "filmcraft-agent-smoke", "version": "1.0"},
        })
        self.notify("notifications/initialized")
        self.server_info = result
        return result

    def tools(self) -> list[dict[str, Any]]:
        return list(self.request("tools/list", {}).get("tools", []))

    def call(self, name: str, arguments: dict[str, Any] | None = None,
             *, timeout: float | None = None) -> dict[str, Any]:
        result = self.request("tools/call", {
            "name": name, "arguments": arguments or {},
        }, timeout=timeout)
        if result.get("isError"):
            raise McpError(f"{name}: {text_content(result)}")
        return result


def text_content(result: dict[str, Any]) -> str:
    return "\n".join(str(item.get("text", "")) for item in result.get("content", [])
                     if item.get("type") == "text")


def json_content(result: dict[str, Any]) -> Any:
    structured = result.get("structuredContent")
    if structured is not None:
        return structured
    text = text_content(result)
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise McpError(f"Tool did not return JSON: {text[:500]}") from exc


def save_images(result: dict[str, Any], directory: Path, stem: str) -> list[Path]:
    directory.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    for index, item in enumerate(result.get("content", [])):
        if item.get("type") != "image":
            continue
        extension = {"image/png": ".png", "image/jpeg": ".jpg"}.get(item.get("mimeType"), ".bin")
        path = directory / f"{stem}-{index}{extension}"
        path.write_bytes(base64.b64decode(item["data"], validate=True))
        paths.append(path)
    if not paths:
        raise McpError("Tool returned no image content")
    return paths


def cli() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cli", default=os.environ.get("FILMCRAFT_CLI", "filmcraft-cli"))
    parser.add_argument("--mode", choices=["demo", "empty", "bridge"], default="demo")
    parser.add_argument("--project", type=Path)
    parser.add_argument("--address", default="127.0.0.1:9876")
    parser.add_argument("--timeout", type=float, default=60)
    sub = parser.add_subparsers(dest="action", required=True)
    sub.add_parser("probe")
    call = sub.add_parser("call")
    call.add_argument("tool")
    call.add_argument("arguments", nargs="?", default="{}")
    call.add_argument("--images", type=Path)
    args = parser.parse_args()
    command = [args.cli, "mcp"]
    if args.mode == "demo":
        command.append("--demo")
    elif args.mode == "bridge":
        command += ["--bridge", args.address]
    elif args.project:
        command += ["--project", str(args.project.resolve())]
    with McpSession(command, timeout=args.timeout) as session:
        if args.action == "probe":
            payload = {"initialize": session.server_info, "tools": session.tools(),
                       "resources": session.request("resources/list", {})}
        else:
            result = session.call(args.tool, json.loads(args.arguments))
            payload = result
            if args.images:
                paths = save_images(result, args.images, args.tool)
                payload = {"result": result, "images": [str(p) for p in paths]}
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(cli())
    except (McpError, OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1)
