"""Ownly 的 SQLite 持久化层。

目的：保存物品、生命周期事件和 Agent 任务，使服务重启后状态不会丢失。
输入输出：接收普通 Python 字典，返回可 JSON 序列化的字典和列表。
原理：所有数据库写入都在事务中完成；品类差异字段保存为 JSON，通用字段可检索。
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Iterator
from uuid import uuid4


RESALE_CHANNELS = [
    {"id": "xianyu", "name": "闲鱼", "price": 1450, "arrival": "预计 3–7 天成交", "fee": "个人发布 · 需用户确认", "fit": "收益最高", "recommended": True},
    {"id": "recycle", "name": "回收平台", "price": 1180, "arrival": "预计当天到账", "fee": "上门质检后定价", "fit": "最快省心", "recommended": False},
    {"id": "consignment", "name": "专业寄卖", "price": 1320, "arrival": "预计 7–14 天成交", "fee": "预估服务费 ¥130", "fit": "无需自己沟通", "recommended": False},
]


class OwnlyStore:
    """封装 Ownly 原型所需的最小 SQLite 操作。"""

    def __init__(self, path: str | Path) -> None:
        self.path = str(path)
        self._create_schema()

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        """创建并确保关闭连接，避免 Windows 持有数据库文件锁。"""
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def _create_schema(self) -> None:
        with self.connect() as database:
            database.executescript(
                """
                CREATE TABLE IF NOT EXISTS items (
                    item_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    category TEXT NOT NULL,
                    icon TEXT NOT NULL,
                    source TEXT NOT NULL,
                    brand TEXT NOT NULL DEFAULT '',
                    location TEXT NOT NULL DEFAULT '家中',
                    status TEXT NOT NULL DEFAULT '使用中',
                    acquired_at TEXT NOT NULL,
                    purchase_price REAL,
                    current_value REAL,
                    attributes_json TEXT NOT NULL DEFAULT '{}',
                    next_action TEXT NOT NULL DEFAULT '持续守护',
                    next_action_date TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS tasks (
                    task_id TEXT PRIMARY KEY,
                    item_id TEXT NOT NULL,
                    task_type TEXT NOT NULL,
                    title TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    priority TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending',
                    ui_schema_json TEXT NOT NULL,
                    result_json TEXT,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(item_id) REFERENCES items(item_id)
                );
                CREATE TABLE IF NOT EXISTS events (
                    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    kind TEXT NOT NULL,
                    title TEXT NOT NULL,
                    detail TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS plans (
                    plan_id TEXT PRIMARY KEY,
                    plan_type TEXT NOT NULL,
                    title TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending',
                    context_json TEXT NOT NULL,
                    ui_schema_json TEXT NOT NULL,
                    result_json TEXT,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS memories (
                    memory_key TEXT PRIMARY KEY,
                    value_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS value_events (
                    value_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source_key TEXT NOT NULL UNIQUE,
                    item_id TEXT,
                    value_kind TEXT NOT NULL CHECK(value_kind IN ('realized','avoided','pending','potential')),
                    amount REAL NOT NULL CHECK(amount >= 0),
                    title TEXT NOT NULL,
                    detail TEXT NOT NULL,
                    occurred_at TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS observations (
                    observation_id TEXT PRIMARY KEY,
                    signal_type TEXT NOT NULL,
                    source TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    confidence REAL NOT NULL CHECK(confidence >= 0 AND confidence <= 1),
                    observed_at TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS agent_runs (
                    run_id TEXT PRIMARY KEY,
                    goal TEXT NOT NULL,
                    status TEXT NOT NULL,
                    autonomy_level TEXT NOT NULL,
                    evidence_json TEXT NOT NULL,
                    counterevidence_json TEXT NOT NULL,
                    proposed_action_json TEXT NOT NULL,
                    steps_json TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS authorization_policies (
                    policy_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    capability_id TEXT NOT NULL,
                    behavior TEXT NOT NULL,
                    condition_json TEXT NOT NULL,
                    enabled INTEGER NOT NULL DEFAULT 1,
                    last_used_at TEXT,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS lifecycle_events (
                    lifecycle_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    item_id TEXT NOT NULL,
                    stage TEXT NOT NULL,
                    title TEXT NOT NULL,
                    detail TEXT NOT NULL,
                    occurred_at TEXT NOT NULL,
                    UNIQUE(item_id, stage),
                    FOREIGN KEY(item_id) REFERENCES items(item_id)
                );
                CREATE TABLE IF NOT EXISTS resale_drafts (
                    draft_id TEXT PRIMARY KEY,
                    item_id TEXT NOT NULL UNIQUE,
                    status TEXT NOT NULL DEFAULT 'draft',
                    title TEXT NOT NULL,
                    description TEXT NOT NULL,
                    condition_text TEXT NOT NULL,
                    price REAL NOT NULL,
                    photos_json TEXT NOT NULL,
                    channels_json TEXT NOT NULL DEFAULT '[]',
                    selected_channel TEXT NOT NULL DEFAULT '',
                    authorization_status TEXT NOT NULL DEFAULT 'not_requested',
                    connector_mode TEXT NOT NULL DEFAULT 'demo',
                    external_reference TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(item_id) REFERENCES items(item_id)
                );
                """
            )
            # 兼容旧版演示数据库：SQLite 不支持一次增加多列，因此逐列迁移。
            existing_columns = {
                row["name"] for row in database.execute("PRAGMA table_info(resale_drafts)").fetchall()
            }
            migrations = {
                "channels_json": "TEXT NOT NULL DEFAULT '[]'",
                "selected_channel": "TEXT NOT NULL DEFAULT ''",
                "authorization_status": "TEXT NOT NULL DEFAULT 'not_requested'",
                "connector_mode": "TEXT NOT NULL DEFAULT 'demo'",
                "external_reference": "TEXT NOT NULL DEFAULT ''",
            }
            for column, definition in migrations.items():
                if column not in existing_columns:
                    database.execute(f"ALTER TABLE resale_drafts ADD COLUMN {column} {definition}")
            # 旧版把“确认发布”误记为真实发布。升级后退回渠道选择，并补齐渠道方案。
            database.execute(
                "UPDATE resale_drafts SET status='draft' WHERE status='published' AND connector_mode='demo'"
            )
            database.execute(
                "UPDATE resale_drafts SET channels_json=? WHERE channels_json='[]'",
                (json.dumps(RESALE_CHANNELS, ensure_ascii=False),),
            )
            database.execute(
                """INSERT OR IGNORE INTO value_events
                   (source_key,item_id,value_kind,amount,title,detail,occurred_at)
                   SELECT 'resale:' || draft_id,item_id,
                          CASE WHEN status='sold' THEN 'realized' ELSE 'potential' END,
                          price,
                          CASE WHEN status='sold' THEN '闲置出售收入' ELSE '可释放闲置价值' END,
                          CASE WHEN status='sold' THEN '物品已经成交' ELSE '出售方案已生成，尚未成交' END,
                          substr(created_at,1,10)
                   FROM resale_drafts"""
            )
            default_policies = [
                ("policy-price-prepare", "小额保价自动准备", "prepare_price_claim", "prepare_only", {"max_amount": 500}),
                ("policy-public-listing", "公开发布始终询问", "external_listing", "always_confirm", {}),
                ("policy-payment", "支付与费用始终询问", "spend_money", "always_confirm", {}),
                ("policy-transfer", "所有权转移始终询问", "transfer_ownership", "always_confirm", {}),
            ]
            for policy_id, name, capability_id, behavior, condition in default_policies:
                database.execute(
                    """INSERT OR IGNORE INTO authorization_policies
                       (policy_id,name,capability_id,behavior,condition_json)
                       VALUES (?,?,?,?,?)""",
                    (policy_id, name, capability_id, behavior, json.dumps(condition, ensure_ascii=False)),
                )

    def seed_if_empty(self, items: list[dict[str, Any]]) -> None:
        with self.connect() as database:
            count = database.execute("SELECT COUNT(*) FROM items").fetchone()[0]
        if count == 0:
            for item in items:
                self.add_item(item)

    def seed_missing(self, items: list[dict[str, Any]]) -> None:
        """补入新版演示新增的固定物品，不覆盖现有数据或用户物品。"""
        with self.connect() as database:
            existing_ids = {row[0] for row in database.execute("SELECT item_id FROM items").fetchall()}
        for item in items:
            if item["item_id"] not in existing_ids:
                self.add_item(item)

    def add_item(self, item: dict[str, Any]) -> dict[str, Any]:
        payload = dict(item)
        payload.setdefault("item_id", f"item-{uuid4().hex[:8]}")
        payload.setdefault("acquired_at", date.today().isoformat())
        payload.setdefault("attributes", {})
        with self.connect() as database:
            database.execute(
                """INSERT INTO items
                (item_id,name,category,icon,source,brand,location,status,acquired_at,
                 purchase_price,current_value,attributes_json,next_action,next_action_date)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (payload["item_id"], payload["name"], payload["category"], payload["icon"],
                 payload["source"], payload.get("brand", ""), payload.get("location", "家中"),
                 payload.get("status", "使用中"), payload["acquired_at"], payload.get("purchase_price"),
                 payload.get("current_value"), json.dumps(payload["attributes"], ensure_ascii=False),
                 payload.get("next_action", "持续守护"), payload.get("next_action_date", "")),
            )
        self.add_event("memory", "写入个人物品仓", f"{payload['category']} · {payload['name']}")
        return payload

    def list_items(self) -> list[dict[str, Any]]:
        with self.connect() as database:
            rows = database.execute("SELECT * FROM items WHERE status!='已出售' ORDER BY created_at DESC, rowid DESC").fetchall()
        result = []
        for row in rows:
            item = dict(row)
            item["attributes"] = json.loads(item.pop("attributes_json"))
            item.pop("created_at")
            result.append(item)
        return result

    def update_item_value(self, item_id: str, value: float) -> None:
        with self.connect() as database:
            database.execute("UPDATE items SET current_value=? WHERE item_id=?", (value, item_id))

    def add_event(self, kind: str, title: str, detail: str) -> None:
        with self.connect() as database:
            database.execute("INSERT INTO events(kind,title,detail) VALUES (?,?,?)", (kind, title, detail))

    def recent_events(self, limit: int = 12) -> list[dict[str, Any]]:
        with self.connect() as database:
            rows = database.execute("SELECT kind,title,detail,created_at FROM events ORDER BY event_id DESC LIMIT ?", (limit,)).fetchall()
        return [dict(row) for row in reversed(rows)]

    def set_memory(self, key: str, value: dict[str, Any]) -> None:
        """保存会影响后续 Agent 判断的结构化长期记忆。"""
        with self.connect() as database:
            database.execute(
                """INSERT INTO memories(memory_key,value_json,updated_at)
                   VALUES (?,?,CURRENT_TIMESTAMP)
                   ON CONFLICT(memory_key) DO UPDATE SET
                   value_json=excluded.value_json,updated_at=CURRENT_TIMESTAMP""",
                (key, json.dumps(value, ensure_ascii=False)),
            )

    def get_memory(self, key: str) -> dict[str, Any] | None:
        """读取一条长期记忆；不存在时返回 None。"""
        with self.connect() as database:
            row = database.execute("SELECT value_json FROM memories WHERE memory_key=?", (key,)).fetchone()
        return json.loads(row["value_json"]) if row else None

    def value_created(self) -> float:
        """只汇总已经到账或明确避免的支出，不混入申请中和潜在金额。"""
        with self.connect() as database:
            row = database.execute(
                "SELECT COALESCE(SUM(amount),0) AS total FROM value_events WHERE value_kind IN ('realized','avoided')"
            ).fetchone()
        return float(row["total"])

    def record_value_event(self, event: dict[str, Any]) -> dict[str, Any]:
        """幂等记录价值流水；同一业务事件更新状态时不会重复累计金额。"""
        payload = dict(event)
        payload.setdefault("occurred_at", date.today().isoformat())
        with self.connect() as database:
            database.execute(
                """INSERT INTO value_events
                   (source_key,item_id,value_kind,amount,title,detail,occurred_at)
                   VALUES (?,?,?,?,?,?,?)
                   ON CONFLICT(source_key) DO UPDATE SET
                   value_kind=excluded.value_kind,amount=excluded.amount,title=excluded.title,
                   detail=excluded.detail,occurred_at=excluded.occurred_at""",
                (payload["source_key"], payload.get("item_id"), payload["value_kind"],
                 payload["amount"], payload["title"], payload["detail"], payload["occurred_at"]),
            )
            row = database.execute(
                "SELECT source_key,item_id,value_kind,amount,title,detail,occurred_at FROM value_events WHERE source_key=?",
                (payload["source_key"],),
            ).fetchone()
        return dict(row)

    def value_report(self, month: str | None = None) -> dict[str, Any]:
        """返回月度价值账单，并保持四类金额相互独立。"""
        month_key = month or date.today().strftime("%Y-%m")
        with self.connect() as database:
            rows = database.execute(
                """SELECT source_key,item_id,value_kind,amount,title,detail,occurred_at
                   FROM value_events WHERE occurred_at LIKE ? ORDER BY occurred_at DESC,value_id DESC""",
                (f"{month_key}%",),
            ).fetchall()
        events = [dict(row) for row in rows]
        totals = {kind: 0.0 for kind in ("realized", "avoided", "pending", "potential")}
        for event in events:
            totals[event["value_kind"]] += float(event["amount"])
        return {
            "month": month_key,
            "secured": totals["realized"] + totals["avoided"],
            "realized": totals["realized"],
            "avoided": totals["avoided"],
            "pending": totals["pending"],
            "potential": totals["potential"],
            "events": events,
        }

    def add_observation(self, observation: dict[str, Any]) -> dict[str, Any]:
        """保存一条经过来源标注的环境或行为信号，而不是直接把信号当成用户意图。"""
        payload = dict(observation)
        payload.setdefault("observation_id", f"obs-{uuid4().hex[:8]}")
        payload.setdefault("observed_at", date.today().isoformat())
        payload.setdefault("confidence", 1.0)
        with self.connect() as database:
            database.execute(
                """INSERT INTO observations
                   (observation_id,signal_type,source,payload_json,confidence,observed_at)
                   VALUES (?,?,?,?,?,?)""",
                (payload["observation_id"], payload["signal_type"], payload["source"],
                 json.dumps(payload["payload"], ensure_ascii=False), payload["confidence"], payload["observed_at"]),
            )
        return self.get_observation(payload["observation_id"])

    def get_observation(self, observation_id: str) -> dict[str, Any]:
        with self.connect() as database:
            row = database.execute(
                "SELECT * FROM observations WHERE observation_id=?", (observation_id,)
            ).fetchone()
        if row is None:
            raise ValueError("观察信号不存在")
        result = dict(row)
        result["payload"] = json.loads(result.pop("payload_json"))
        return result

    def observations(self, limit: int = 50) -> list[dict[str, Any]]:
        with self.connect() as database:
            rows = database.execute(
                "SELECT observation_id FROM observations ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
        return [self.get_observation(row["observation_id"]) for row in rows]

    def create_agent_run(self, run: dict[str, Any]) -> dict[str, Any]:
        """保存可恢复的 Agent 判断记录，包括证据、反证、权限等级与执行步骤。"""
        payload = dict(run)
        payload.setdefault("run_id", f"run-{uuid4().hex[:8]}")
        with self.connect() as database:
            database.execute(
                """INSERT INTO agent_runs
                   (run_id,goal,status,autonomy_level,evidence_json,counterevidence_json,proposed_action_json,steps_json)
                   VALUES (?,?,?,?,?,?,?,?)""",
                (payload["run_id"], payload["goal"], payload["status"], payload["autonomy_level"],
                 json.dumps(payload.get("evidence", []), ensure_ascii=False),
                 json.dumps(payload.get("counterevidence", []), ensure_ascii=False),
                 json.dumps(payload["proposed_action"], ensure_ascii=False),
                 json.dumps(payload["steps"], ensure_ascii=False)),
            )
        return self.get_agent_run(payload["run_id"])

    def get_agent_run(self, run_id: str) -> dict[str, Any]:
        with self.connect() as database:
            row = database.execute("SELECT * FROM agent_runs WHERE run_id=?", (run_id,)).fetchone()
        if row is None:
            raise ValueError("Agent 运行记录不存在")
        result = dict(row)
        for field in ("evidence", "counterevidence", "proposed_action", "steps"):
            result[field] = json.loads(result.pop(f"{field}_json"))
        return result

    def agent_runs(self, limit: int = 20) -> list[dict[str, Any]]:
        with self.connect() as database:
            rows = database.execute(
                "SELECT run_id FROM agent_runs ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
        return [self.get_agent_run(row["run_id"]) for row in rows]

    def authorization_policies(self) -> list[dict[str, Any]]:
        """返回用户可见的长期授权策略。"""
        with self.connect() as database:
            rows = database.execute(
                """SELECT policy_id,name,capability_id,behavior,condition_json,enabled,last_used_at
                   FROM authorization_policies ORDER BY rowid"""
            ).fetchall()
        policies = []
        for row in rows:
            policy = dict(row)
            policy["condition"] = json.loads(policy.pop("condition_json"))
            policy["enabled"] = bool(policy["enabled"])
            policies.append(policy)
        return policies

    def set_policy_enabled(self, policy_id: str, enabled: bool) -> dict[str, Any]:
        with self.connect() as database:
            result = database.execute(
                "UPDATE authorization_policies SET enabled=? WHERE policy_id=?",
                (int(enabled), policy_id),
            )
            if result.rowcount == 0:
                raise ValueError("授权策略不存在")
        return next(policy for policy in self.authorization_policies() if policy["policy_id"] == policy_id)

    def match_policy(self, capability_id: str, amount: float | None = None) -> dict[str, Any] | None:
        """匹配一条启用策略；金额上限不满足时返回 None。"""
        policies = [
            policy for policy in self.authorization_policies()
            if policy["enabled"] and policy["capability_id"] == capability_id
        ]
        for policy in policies:
            maximum = policy["condition"].get("max_amount")
            if maximum is not None and (amount is None or amount > maximum):
                continue
            with self.connect() as database:
                database.execute(
                    "UPDATE authorization_policies SET last_used_at=CURRENT_TIMESTAMP WHERE policy_id=?",
                    (policy["policy_id"],),
                )
            return policy
        return None

    def add_lifecycle_event(self, item_id: str, stage: str, title: str, detail: str, occurred_at: str) -> None:
        """幂等写入物品生命周期事件。"""
        with self.connect() as database:
            database.execute(
                """INSERT OR IGNORE INTO lifecycle_events(item_id,stage,title,detail,occurred_at)
                   VALUES (?,?,?,?,?)""",
                (item_id, stage, title, detail, occurred_at),
            )

    def lifecycle_events(self) -> list[dict[str, Any]]:
        with self.connect() as database:
            rows = database.execute(
                "SELECT item_id,stage,title,detail,occurred_at FROM lifecycle_events ORDER BY occurred_at"
            ).fetchall()
        return [dict(row) for row in rows]

    def create_resale_draft(self, draft: dict[str, Any]) -> dict[str, Any]:
        """为一件闲置物品生成或更新结构化转售草稿。"""
        payload = dict(draft)
        payload.setdefault("draft_id", f"draft-{uuid4().hex[:8]}")
        with self.connect() as database:
            existing = database.execute("SELECT draft_id FROM resale_drafts WHERE item_id=?", (payload["item_id"],)).fetchone()
            if existing:
                return self.get_resale_draft(existing["draft_id"])
            database.execute(
                """INSERT INTO resale_drafts
                   (draft_id,item_id,status,title,description,condition_text,price,photos_json,channels_json)
                   VALUES (?,?,'draft',?,?,?,?,?,?)""",
                (payload["draft_id"], payload["item_id"], payload["title"], payload["description"],
                 payload["condition"], payload["price"], json.dumps(payload["photos"], ensure_ascii=False),
                 json.dumps(payload.get("channels", RESALE_CHANNELS), ensure_ascii=False)),
            )
        return self.get_resale_draft(payload["draft_id"])

    def get_resale_draft(self, draft_id: str) -> dict[str, Any]:
        with self.connect() as database:
            row = database.execute("SELECT * FROM resale_drafts WHERE draft_id=?", (draft_id,)).fetchone()
        if row is None:
            raise ValueError("转售草稿不存在")
        draft = dict(row)
        draft["condition"] = draft.pop("condition_text")
        draft["photos"] = json.loads(draft.pop("photos_json"))
        draft["channels"] = json.loads(draft.pop("channels_json")) or RESALE_CHANNELS
        return draft

    def resale_drafts(self) -> list[dict[str, Any]]:
        with self.connect() as database:
            rows = database.execute("SELECT draft_id FROM resale_drafts ORDER BY created_at DESC").fetchall()
        return [self.get_resale_draft(row["draft_id"]) for row in rows]

    def update_resale_status(self, draft_id: str, status: str) -> dict[str, Any]:
        with self.connect() as database:
            database.execute("UPDATE resale_drafts SET status=? WHERE draft_id=?", (status, draft_id))
        return self.get_resale_draft(draft_id)

    def select_resale_channel(self, draft_id: str, channel_id: str) -> dict[str, Any]:
        """保存用户选择的出售渠道，授权仍需单独确认。"""
        draft = self.get_resale_draft(draft_id)
        if draft["status"] in {"published_demo", "sold"}:
            raise ValueError("已经提交的出售方案不能更换渠道")
        channel_ids = {channel["id"] for channel in draft["channels"]}
        if channel_id not in channel_ids:
            raise ValueError("出售渠道不存在")
        with self.connect() as database:
            database.execute(
                """UPDATE resale_drafts
                   SET selected_channel=?,status='channel_selected',authorization_status='not_requested'
                   WHERE draft_id=?""",
                (channel_id, draft_id),
            )
        return self.get_resale_draft(draft_id)

    def authorize_resale_channel(self, draft_id: str) -> dict[str, Any]:
        """记录用户授权；原型仅授权 Demo connector，不代表真实平台授权。"""
        draft = self.get_resale_draft(draft_id)
        if not draft["selected_channel"]:
            raise ValueError("请先选择出售渠道")
        if draft["status"] != "channel_selected":
            raise ValueError("当前出售方案不能重复授权")
        with self.connect() as database:
            database.execute(
                """UPDATE resale_drafts
                   SET status='authorized',authorization_status='demo_authorized'
                   WHERE draft_id=?""",
                (draft_id,),
            )
        return self.get_resale_draft(draft_id)

    def record_resale_publish(self, draft_id: str, external_reference: str) -> dict[str, Any]:
        """保存渠道回执；当前 connector_mode 固定为 demo。"""
        draft = self.get_resale_draft(draft_id)
        if draft["status"] != "authorized":
            raise ValueError("只有已授权的出售方案可以提交")
        with self.connect() as database:
            database.execute(
                """UPDATE resale_drafts SET status='published_demo',external_reference=?
                   WHERE draft_id=?""",
                (external_reference, draft_id),
            )
        return self.get_resale_draft(draft_id)

    def update_item_status(self, item_id: str, status: str, next_action: str) -> None:
        with self.connect() as database:
            database.execute("UPDATE items SET status=?,next_action=? WHERE item_id=?", (status, next_action, item_id))

    def create_task(self, task: dict[str, Any]) -> dict[str, Any]:
        payload = dict(task)
        payload.setdefault("task_id", f"task-{uuid4().hex[:8]}")
        with self.connect() as database:
            existing = database.execute(
                "SELECT task_id FROM tasks WHERE item_id=? AND task_type=? AND status='pending'",
                (payload["item_id"], payload["task_type"]),
            ).fetchone()
            if existing:
                return self.get_task(existing["task_id"])
            database.execute(
                """INSERT INTO tasks(task_id,item_id,task_type,title,reason,priority,status,ui_schema_json)
                   VALUES (?,?,?,?,?,?,'pending',?)""",
                (payload["task_id"], payload["item_id"], payload["task_type"], payload["title"],
                 payload["reason"], payload["priority"], json.dumps(payload["ui_schema"], ensure_ascii=False)),
            )
        return self.get_task(payload["task_id"])

    def get_task(self, task_id: str) -> dict[str, Any]:
        with self.connect() as database:
            row = database.execute("SELECT * FROM tasks WHERE task_id=?", (task_id,)).fetchone()
        if row is None:
            raise ValueError("任务不存在")
        return self._task_from_row(row)

    def has_task_record(self, item_id: str, task_type: str) -> bool:
        """该物品是否已有此类任务的记录（含已完成）。

        用途：同一演示周期内每个任务只生成一次——用户处理过的事不再重复打扰，
        这也让演示叙事可复现：守护 → 处理 → 行程到达 → 处理 → 安静。
        """
        with self.connect() as database:
            row = database.execute(
                "SELECT 1 FROM tasks WHERE item_id=? AND task_type=? LIMIT 1", (item_id, task_type)
            ).fetchone()
        return row is not None

    def pending_tasks(self) -> list[dict[str, Any]]:
        with self.connect() as database:
            rows = database.execute("SELECT * FROM tasks WHERE status='pending' ORDER BY created_at DESC").fetchall()
        return [self._task_from_row(row) for row in rows]

    def complete_task(self, task_id: str, result: dict[str, Any]) -> dict[str, Any]:
        with self.connect() as database:
            database.execute("UPDATE tasks SET status='completed',result_json=? WHERE task_id=?", (json.dumps(result, ensure_ascii=False), task_id))
        return self.get_task(task_id)

    def create_plan(self, plan: dict[str, Any]) -> dict[str, Any]:
        """保存跨多个物品的系统级计划，例如旅行准备。"""
        payload = dict(plan)
        payload.setdefault("plan_id", f"plan-{uuid4().hex[:8]}")
        with self.connect() as database:
            database.execute("UPDATE plans SET status='superseded' WHERE plan_type=? AND status='pending'", (payload["plan_type"],))
            database.execute(
                """INSERT INTO plans(plan_id,plan_type,title,status,context_json,ui_schema_json)
                   VALUES (?,?,?,'pending',?,?)""",
                (payload["plan_id"], payload["plan_type"], payload["title"],
                 json.dumps(payload["context"], ensure_ascii=False), json.dumps(payload["ui_schema"], ensure_ascii=False)),
            )
        return self.get_plan(payload["plan_id"])

    def get_plan(self, plan_id: str) -> dict[str, Any]:
        with self.connect() as database:
            row = database.execute("SELECT * FROM plans WHERE plan_id=?", (plan_id,)).fetchone()
        if row is None:
            raise ValueError("计划不存在")
        return self._plan_from_row(row)

    def pending_plans(self) -> list[dict[str, Any]]:
        with self.connect() as database:
            rows = database.execute("SELECT * FROM plans WHERE status='pending' ORDER BY created_at DESC").fetchall()
        return [self._plan_from_row(row) for row in rows]

    def complete_plan(self, plan_id: str, result: dict[str, Any]) -> dict[str, Any]:
        with self.connect() as database:
            database.execute("UPDATE plans SET status='completed',result_json=? WHERE plan_id=?", (json.dumps(result, ensure_ascii=False), plan_id))
        return self.get_plan(plan_id)

    @staticmethod
    def _task_from_row(row: sqlite3.Row) -> dict[str, Any]:
        task = dict(row)
        task["ui_schema"] = json.loads(task.pop("ui_schema_json"))
        task["result"] = json.loads(task.pop("result_json")) if task.get("result_json") else None
        return task

    @staticmethod
    def _plan_from_row(row: sqlite3.Row) -> dict[str, Any]:
        plan = dict(row)
        plan["context"] = json.loads(plan.pop("context_json"))
        plan["ui_schema"] = json.loads(plan.pop("ui_schema_json"))
        plan["result"] = json.loads(plan.pop("result_json")) if plan.get("result_json") else None
        plan["task_id"] = plan["plan_id"]
        plan["task_type"] = plan["plan_type"]
        plan["item_id"] = None
        plan["reason"] = plan["ui_schema"].get("body", "")
        plan["priority"] = "high"
        return plan

    def clear(self) -> None:
        """仅供测试和重置演示使用。"""
        with self.connect() as database:
            database.execute("DELETE FROM tasks")
            database.execute("DELETE FROM events")
            database.execute("DELETE FROM plans")
            database.execute("DELETE FROM memories")
            database.execute("DELETE FROM value_events")
            database.execute("DELETE FROM observations")
            database.execute("DELETE FROM agent_runs")
            database.execute("DELETE FROM lifecycle_events")
            database.execute("DELETE FROM resale_drafts")
            database.execute("DELETE FROM items")


def demo_item_records() -> list[dict[str, Any]]:
    """返回五类初始物品，供首次启动建立可演示的个人仓。"""
    today = date.today()
    return [
        {"item_id":"airwave","name":"AirWave Pro 耳机","category":"电子","icon":"◉","source":"订单同步","brand":"AirWave","location":"书房","acquired_at":(today-timedelta(days=5)).isoformat(),"purchase_price":1299,"current_value":1299,"attributes":{"保修":"1 年"},"next_action":"监测保价","next_action_date":(today+timedelta(days=25)).isoformat()},
        {"item_id":"serum","name":"夜间修护精华","category":"护肤","icon":"◒","source":"相机识别","brand":"Nöra","location":"浴室","acquired_at":(today-timedelta(days=43)).isoformat(),"purchase_price":529,"current_value":310,"attributes":{"预计余量":"18%"},"next_action":"预计 12 天后用完","next_action_date":(today+timedelta(days=12)).isoformat()},
        {"item_id":"lipstick","name":"丝绒唇釉 07","category":"彩妆","icon":"✦","source":"订单同步","brand":"Miro","location":"随身包","acquired_at":(today-timedelta(days=210)).isoformat(),"purchase_price":239,"current_value":90,"attributes":{"开封期限":"12 个月"},"next_action":"开封期限剩 5 个月","next_action_date":(today+timedelta(days=150)).isoformat()},
        {"item_id":"chair","name":"Flow 人体工学椅","category":"家具","icon":"▰","source":"邮件识别","brand":"Morrow","location":"书房","acquired_at":(today-timedelta(days=330)).isoformat(),"purchase_price":3299,"current_value":2200,"attributes":{"材质":"织物"},"next_action":"建议深度清洁","next_action_date":(today+timedelta(days=9)).isoformat()},
        {"item_id":"car","name":"City EV","category":"汽车","icon":"◆","source":"设备连接","brand":"Nova Motors","location":"车库","acquired_at":(today-timedelta(days=680)).isoformat(),"purchase_price":168000,"current_value":126000,"attributes":{"里程":"18,420 km"},"next_action":"距保养 580 km","next_action_date":(today+timedelta(days=18)).isoformat()},
        # 行程演示相关物品：充电器双地点档案（家中 + 公司工位）与新购防晒霜
        {"item_id":"charger_home","name":"65W 氮化镓充电器","category":"电子","icon":"◉","source":"订单同步","brand":"Volta","location":"家中","acquired_at":(today-timedelta(days=120)).isoformat(),"purchase_price":169,"current_value":150,"attributes":{"功率":"65W","上次使用":"昨天"},"next_action":"检查出行携带","next_action_date":(today+timedelta(days=90)).isoformat()},
        {"item_id":"charger_office","name":"备用 65W 充电器","category":"电子","icon":"◉","source":"语音记录","brand":"Volta","location":"公司工位","acquired_at":(today-timedelta(days=60)).isoformat(),"purchase_price":169,"current_value":150,"attributes":{"备注":"上次出差时录入"},"next_action":"出差应急备用","next_action_date":(today+timedelta(days=30)).isoformat()},
        {"item_id":"sunscreen","name":"防晒霜 SPF50+","category":"护肤","icon":"◒","source":"订单同步","brand":"Solstice","location":"家中","acquired_at":(today-timedelta(days=2)).isoformat(),"purchase_price":269,"current_value":269,"attributes":{"容量":"90ml","防晒值":"SPF50+ PA++++"},"next_action":"出行携带提醒","next_action_date":(today+timedelta(days=30)).isoformat()},
        {"item_id":"projector","name":"Beam Mini 投影仪","category":"电子","icon":"◉","source":"订单同步","brand":"Beam","location":"客厅","acquired_at":(today-timedelta(days=5)).isoformat(),"purchase_price":2399,"current_value":2399,"attributes":{"退货截止":(today+timedelta(days=2)).isoformat(),"订单号":"BM-20481","使用次数":"1 次"},"next_action":"退货期剩 2 天","next_action_date":(today+timedelta(days=2)).isoformat()},
        {"item_id":"console","name":"Switch OLED 掌机","category":"电子","icon":"◉","source":"订单同步","brand":"Nintendo","location":"电视柜","acquired_at":(today-timedelta(days=420)).isoformat(),"purchase_price":2599,"current_value":1450,"attributes":{"闲置天数":"128","预计转售价":"¥1450","包装配件":"完整"},"next_action":"建议评估转售","next_action_date":today.isoformat()},
    ]
