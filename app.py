"""Ownly 本地服务：连接 Agent 内核、SQLite 记忆和多端 Web 界面。"""

from __future__ import annotations

import json
import mimetypes
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlparse

from agent_core import CATEGORY_RULES, OwnlyAgent
from storage import OwnlyStore, demo_item_records

HOST, PORT = "127.0.0.1", 8765
ROOT = Path(__file__).parent
STATIC_DIR = ROOT / "static"
STORE = OwnlyStore(ROOT / "ownly.db")
AGENT = OwnlyAgent(STORE)


class RequestHandler(BaseHTTPRequestHandler):
    """提供状态、收录、主动扫描、任务执行和静态页面。"""

    def do_GET(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path in {"/api/state", "/api/watch"}:
            self._send_json(AGENT.snapshot())
            return
        page_routes = {"/watch": "watch.html", "/shop": "shop.html", "/ambient": "ambient.html"}
        self._serve_static(page_routes.get(path, path))

    def do_POST(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        try:
            body = self._read_json()
            routes: dict[str, Callable[[], dict[str, Any] | list[dict[str, Any]]]] = {
                "/api/capture": lambda: self._capture(body),
                "/api/intent": lambda: self._intent(body),
                "/api/observe": lambda: self._observe(body),
                "/api/policy/mode": lambda: self._set_policy_mode(body),
                "/api/policy/toggle": lambda: self._toggle_policy(body),
                "/api/scan": AGENT.scan,
                "/api/discover": self._discover,
                "/api/context-event": self._context_event,
                "/api/execute": lambda: self._execute(body),
                "/api/resale/publish": lambda: self._publish_resale(body),
                "/api/resale/select-channel": lambda: self._select_resale_channel(body),
                "/api/resale/authorize": lambda: self._authorize_resale(body),
                "/api/resale/sold": lambda: self._mark_sold(body),
                "/api/reset": self._reset,
            }
            action = routes.get(path)
            if action is None:
                self._send_json({"error": "Not found"}, HTTPStatus.NOT_FOUND)
                return
            result = action()
            self._send_json(result if isinstance(result, dict) else {"tasks": result, "state": AGENT.snapshot()})
        except (ValueError, json.JSONDecodeError) as exc:
            self._send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)

    @staticmethod
    def _capture(body: dict[str, Any]) -> dict[str, Any]:
        name = str(body.get("name", ""))
        category = str(body.get("category", "其他"))
        return RequestHandler._add_structured(name, category, str(body.get("source", "相机识别")))

    @staticmethod
    def _add_structured(name: str, category: str, source: str) -> dict[str, Any]:
        """兼容结构化入口，同时把数据写入同一长期记忆。"""
        if not name.strip():
            raise ValueError("请告诉 Ownly 这是什么物品")
        utterance = f"这是{name}"
        item = AGENT.understand_item(utterance, source)
        if item["category"] == "其他" and category:
            # 原型阶段结构化入口的显式品类优先；自然语言入口仍由 Agent 推断。
            with STORE.connect() as database:
                rule = CATEGORY_RULES.get(category, CATEGORY_RULES["其他"])
                icon, action = rule["icon"], rule["action"]
                database.execute("UPDATE items SET category=?,icon=?,next_action=? WHERE item_id=?", (category, icon, action, item["item_id"]))
        return AGENT.snapshot()

    @staticmethod
    def _intent(body: dict[str, Any]) -> dict[str, Any]:
        routed = AGENT.handle_intent(str(body.get("text", "")), str(body.get("source", "自然语言")))
        snapshot = AGENT.snapshot()
        snapshot["intent_kind"] = routed["kind"]
        return snapshot

    @staticmethod
    def _observe(body: dict[str, Any]) -> dict[str, Any]:
        """接收已授权的结构化信号，返回证据驱动的意图假设与最新系统状态。"""
        inference = AGENT.observe_and_infer(
            str(body.get("signal_type", "")),
            body.get("payload", {}) if isinstance(body.get("payload", {}), dict) else {},
            str(body.get("source", "用户主动分享")),
            float(body.get("confidence", 1.0)),
        )
        return {"inference": inference, "state": AGENT.snapshot()}

    @staticmethod
    def _set_policy_mode(body: dict[str, Any]) -> dict[str, Any]:
        AGENT.set_autonomy_mode(str(body.get("mode", "")))
        return AGENT.snapshot()

    @staticmethod
    def _toggle_policy(body: dict[str, Any]) -> dict[str, Any]:
        AGENT.set_policy_enabled(str(body.get("policy_id", "")), bool(body.get("enabled")))
        return AGENT.snapshot()

    @staticmethod
    def _execute(body: dict[str, Any]) -> dict[str, Any]:
        AGENT.execute(str(body.get("task_id", "")), str(body.get("action_id", "")))
        return AGENT.snapshot()

    @staticmethod
    def _publish_resale(body: dict[str, Any]) -> dict[str, Any]:
        AGENT.publish_resale_draft(str(body.get("draft_id", "")))
        return AGENT.snapshot()

    @staticmethod
    def _select_resale_channel(body: dict[str, Any]) -> dict[str, Any]:
        AGENT.select_resale_channel(str(body.get("draft_id", "")), str(body.get("channel_id", "")))
        return AGENT.snapshot()

    @staticmethod
    def _authorize_resale(body: dict[str, Any]) -> dict[str, Any]:
        AGENT.authorize_resale_channel(str(body.get("draft_id", "")))
        return AGENT.snapshot()

    @staticmethod
    def _mark_sold(body: dict[str, Any]) -> dict[str, Any]:
        AGENT.mark_item_sold(str(body.get("draft_id", "")))
        return AGENT.snapshot()

    @staticmethod
    def _discover() -> dict[str, Any]:
        result = AGENT.discover_items()
        snapshot = AGENT.snapshot()
        snapshot["discovery_status"] = result.get("status", "review")
        return snapshot

    @staticmethod
    def _context_event() -> dict[str, Any]:
        AGENT.plan_departure_guard()
        return AGENT.snapshot()

    @staticmethod
    def _reset() -> dict[str, Any]:
        STORE.clear()
        STORE.seed_if_empty(demo_item_records())
        return AGENT.snapshot()

    def _read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        return json.loads(self.rfile.read(length).decode("utf-8")) if length else {}

    def _send_json(self, payload: dict[str, Any], status: HTTPStatus = HTTPStatus.OK) -> None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _serve_static(self, request_path: str) -> None:
        relative = "index.html" if request_path in {"", "/"} else request_path.lstrip("/")
        file_path = (STATIC_DIR / relative).resolve()
        if STATIC_DIR.resolve() not in file_path.parents:
            self.send_error(HTTPStatus.FORBIDDEN)
            return
        if not file_path.is_file():
            file_path = STATIC_DIR / "index.html"
        content = file_path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", f"{mimetypes.guess_type(file_path.name)[0] or 'application/octet-stream'}; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def log_message(self, format_string: str, *args: object) -> None:
        if self.path.startswith("/api/"):
            super().log_message(format_string, *args)


def run() -> None:
    server = ThreadingHTTPServer((HOST, PORT), RequestHandler)
    print(f"Ownly is running at http://{HOST}:{PORT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    run()
