"""Ownly Agent 状态机测试。"""

import sys
import tempfile
import unittest
from datetime import date, datetime
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent_core import OwnlyAgent  # noqa: E402
from storage import OwnlyStore, demo_history_records  # noqa: E402


class OwnlyAgentTest(unittest.TestCase):
    """验证多品类收录、统计和主动行动闭环。"""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        store = OwnlyStore(Path(self.temp_dir.name) / "test.db")
        self.agent = OwnlyAgent(store)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_demo_warehouse_contains_multiple_categories(self) -> None:
        state = self.agent.snapshot()
        self.assertEqual(state["summary"]["total"], 10)
        self.assertEqual(state["summary"]["categories"], 5)

    def test_demo_history_lands_in_current_month_and_is_idempotent(self) -> None:
        """演示历史流水必须落在当月账单里，重复写入不会重复计钱。"""
        records = demo_history_records()
        month = date.today().strftime("%Y-%m")
        self.assertTrue(all(record["occurred_at"].startswith(month) for record in records))
        expected = sum(
            record["amount"] for record in records if record["value_kind"] in {"realized", "avoided"}
        )
        self.agent.store.seed_demo_history(records)
        self.assertEqual(self.agent.snapshot()["value_report"]["secured"], expected)
        self.agent.store.seed_demo_history(records)  # 再写一次不应翻倍
        self.assertEqual(self.agent.snapshot()["value_report"]["secured"], expected)

    def test_demo_history_clamps_to_first_of_month(self) -> None:
        """月初重置时，历史流水不会退到上个月而漏出当月账单。"""
        records = demo_history_records(date(2026, 3, 2))
        self.assertTrue(all(record["occurred_at"].startswith("2026-03") for record in records))

    def test_seed_has_charger_two_location_records(self) -> None:
        """行程演示依赖双地点充电器档案：家中一支 + 公司工位备用一支。"""
        items = {item["item_id"]: item for item in self.agent.snapshot()["items"]}
        self.assertEqual(items["charger_home"]["location"], "家中")
        self.assertEqual(items["charger_office"]["location"], "公司工位")

    def test_natural_language_adds_persistent_item(self) -> None:
        item = self.agent.understand_item("我刚买了一瓶防晒霜，花了 269")
        state = self.agent.snapshot()
        self.assertEqual(item["category"], "护肤")
        self.assertEqual(item["purchase_price"], 269.0)
        self.assertEqual(state["summary"]["total"], 11)
        reopened = OwnlyAgent(OwnlyStore(Path(self.temp_dir.name) / "test.db"))
        self.assertEqual(reopened.snapshot()["summary"]["total"], 11)

    def test_complete_price_protection_journey(self) -> None:
        tasks = self.agent.scan()
        price_task = next(task for task in tasks if task["task_type"] == "price_protection")
        self.assertEqual(price_task["ui_schema"]["component"], "decision_card")
        completed = self.agent.execute(price_task["task_id"], "claim")
        self.assertEqual(completed["status"], "completed")
        self.assertIn("保价", completed["result"]["message"])

    def test_scan_creates_multiple_category_tasks(self) -> None:
        tasks = self.agent.scan()
        self.assertEqual(
            {task["task_type"] for task in tasks},
            {"replenish", "maintenance", "price_protection", "return_window", "resale"},
        )

    def test_trip_card_arrives_after_guardian_tasks_resolved(self) -> None:
        """行程事件在守护任务处理完后到达，生成出发卡（含逐项物品检查）。"""
        guardian = self.agent.scan()
        self.assertNotIn("trip_prep", {task["task_type"] for task in guardian})
        for task in guardian:
            primary = task["ui_schema"]["actions"][0]["id"]
            self.agent.execute(task["task_id"], primary)
        next_scan = self.agent.scan()
        trip = next(task for task in next_scan if task["task_type"] == "trip_prep")
        schema = trip["ui_schema"]
        self.assertEqual(schema["component"], "departure_card")
        self.assertEqual(schema["tone"], "trip")
        self.assertGreaterEqual(len(schema["checklist"]), 2)
        self.assertIn("充电器", " ".join(row["label"] for row in schema["checklist"]))
        completed = self.agent.execute(trip["task_id"], "gen_checklist")
        self.assertEqual(completed["status"], "completed")
        self.assertIn("清单", completed["result"]["message"])

    def test_trip_task_not_duplicated_by_repeated_scan(self) -> None:
        for task in self.agent.scan():
            self.agent.execute(task["task_id"], task["ui_schema"]["actions"][0]["id"])
        self.agent.scan()
        self.agent.scan()
        pending = self.agent.snapshot()["tasks"]
        self.assertEqual(len([task for task in pending if task["task_type"] == "trip_prep"]), 1)

    def test_rejects_action_outside_schema(self) -> None:
        task = self.agent.scan()[0]
        with self.assertRaisesRegex(ValueError, "授权范围"):
            self.agent.execute(task["task_id"], "unsafe_action")

    def test_rich_categories_are_detected(self) -> None:
        cases = {
            "我买了一双跑鞋": "鞋靴",
            "新买的猫粮": "宠物用品",
            "这台咖啡机花了 899": "家电",
            "收藏了一套纪念币": "收藏品",
        }
        for utterance, expected_category in cases.items():
            with self.subTest(utterance=utterance):
                item = self.agent.understand_item(utterance)
                self.assertEqual(item["category"], expected_category)

    def test_catalog_exposes_grouped_categories(self) -> None:
        catalog = self.agent.snapshot()["category_catalog"]
        self.assertGreaterEqual(len(catalog), 20)
        self.assertIn("穿搭配饰", {entry["group"] for entry in catalog})
        self.assertIn("家庭成员", {entry["group"] for entry in catalog})

    def test_trip_intent_uses_owned_items_and_context_tools(self) -> None:
        routed = self.agent.handle_intent("我下周去深圳四天，帮我准备")
        self.assertEqual(routed["kind"], "plan")
        plan = routed["result"]
        self.assertEqual(plan["plan_type"], "trip_preparation")
        self.assertEqual(plan["context"]["trip"]["destination"], "深圳")
        self.assertIn("天气", plan["ui_schema"]["body"])
        self.assertEqual(plan["ui_schema"]["component"], "journey_card")

    def test_trip_plan_executes_through_allowed_dynamic_action(self) -> None:
        plan = self.agent.plan_trip("去深圳出差")
        completed = self.agent.execute(plan["plan_id"], "build_pack")
        self.assertEqual(completed["status"], "completed")
        self.assertIn("AirWave Pro 耳机", completed["result"]["checklist"])


    def test_discovery_auto_imports_deduplicates_and_requests_confirmation(self) -> None:
        before = len(self.agent.snapshot()["items"])
        task = self.agent.discover_items()
        after = self.agent.snapshot()
        self.assertEqual(len(after["items"]), before + 2)
        self.assertEqual(task["ui_schema"]["component"], "discovery_card")
        verdicts = {row["verdict"] for row in task["ui_schema"]["discoveries"]}
        self.assertEqual(verdicts, {"已自动收录", "已在物品仓", "需要确认"})

    def test_confirmed_discovery_enters_long_term_inventory(self) -> None:
        task = self.agent.discover_items()
        self.agent.execute(task["task_id"], "confirm_discovery")
        item_ids = {item["item_id"] for item in self.agent.snapshot()["items"]}
        self.assertIn("discovered-lamp", item_ids)
        count = len(item_ids)
        repeated = self.agent.discover_items()
        self.assertEqual(repeated["status"], "no_change")
        self.assertEqual(len(self.agent.snapshot()["items"]), count)

    def test_purchase_intent_checks_owned_items_before_buying(self) -> None:
        routed = self.agent.handle_intent("我想买一个 65W 充电器，值得买吗")
        self.assertEqual(routed["kind"], "plan")
        plan = routed["result"]
        self.assertEqual(plan["plan_type"], "purchase_decision")
        self.assertEqual(len(plan["ui_schema"]["comparisons"]), 2)
        self.assertIn("先别买", plan["ui_schema"]["title"])

    def test_skipping_duplicate_purchase_records_saved_cost(self) -> None:
        plan = self.agent.plan_purchase("我想买一个 65W 充电器")
        completed = self.agent.execute(plan["plan_id"], "skip_purchase")
        self.assertEqual(completed["result"]["avoided_cost"], 169)
        self.assertEqual(completed["status"], "completed")

    def test_purchase_retrieval_generalizes_across_categories(self) -> None:
        cases = {
            "我想买一副耳机": ("耳机", 1),
            "准备买一瓶防晒": ("防晒", 1),
            "要不要买一把人体工学椅": ("椅", 1),
            "我想买一台相机": ("相机", 0),
        }
        for utterance, (subject, count) in cases.items():
            with self.subTest(utterance=utterance):
                plan = self.agent.plan_purchase(utterance)
                self.assertEqual(plan["context"]["subject"], subject)
                self.assertEqual(len(plan["context"]["matched_item_ids"]), count)

    def test_observation_creates_explainable_intent_hypothesis(self) -> None:
        result = self.agent.observe_and_infer(
            "product_interest",
            {"category": "电子", "subject": "新款游戏机", "shared_by_user": True},
            source="用户主动分享",
            confidence=0.9,
        )
        run = result["run"]
        self.assertTrue(run["proposed_action"]["is_hypothesis"])
        self.assertEqual(run["autonomy_level"], "L1")
        self.assertEqual(run["status"], "prepared")
        self.assertGreaterEqual(run["proposed_action"]["confidence"], 0.65)
        self.assertTrue(any("闲置" in row["label"] for row in run["evidence"]))
        self.assertFalse(run["proposed_action"]["external_effect"])

    def test_untrusted_observation_source_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "未获得授权"):
            self.agent.observe_and_infer(
                "browser_history", {"category": "电子"}, source="后台浏览监控"
            )

    def test_high_risk_capability_requires_confirmation(self) -> None:
        blocked = self.agent.capability_decision("external_listing")
        allowed = self.agent.capability_decision("external_listing", user_confirmed=True)
        self.assertFalse(blocked["allowed"])
        self.assertEqual(blocked["level"], "L2")
        self.assertTrue(allowed["allowed"])

    def test_policy_center_persists_mode_and_rules(self) -> None:
        center = self.agent.set_autonomy_mode("managed")
        self.assertEqual(center["mode"]["mode"], "managed")
        changed = self.agent.set_policy_enabled("policy-price-prepare", False)
        policy = next(row for row in changed["policies"] if row["policy_id"] == "policy-price-prepare")
        self.assertFalse(policy["enabled"])
        restored_agent = OwnlyAgent(OwnlyStore(self.agent.store.path))
        self.assertEqual(restored_agent.policy_center()["mode"]["mode"], "managed")
        restored = next(row for row in restored_agent.policy_center()["policies"] if row["policy_id"] == "policy-price-prepare")
        self.assertFalse(restored["enabled"])

    def test_price_task_explains_policy_and_agent_stages(self) -> None:
        self.agent.scan()
        price_task = next(task for task in self.agent.snapshot()["tasks"] if task.get("task_type") == "price_protection")
        trace = price_task["agent_trace"]
        self.assertEqual(trace["autonomy_level"], "L1")
        self.assertEqual(trace["matched_policy"]["policy_id"], "policy-price-prepare")
        self.assertEqual([step["phase"] for step in trace["steps"]], ["感知", "判断", "规划", "授权", "执行", "验证"])
        self.assertEqual(trace["steps"][3]["status"], "waiting")

    def test_purchase_gap_generates_wishlist_action(self) -> None:
        plan = self.agent.plan_purchase("我想买一台相机")
        actions = {action["id"] for action in plan["ui_schema"]["actions"]}
        self.assertIn("add_to_wishlist", actions)
        completed = self.agent.execute(plan["plan_id"], "add_to_wishlist")
        self.assertIn("愿望清单", completed["result"]["message"])

    def test_purchase_feedback_changes_the_next_decision(self) -> None:
        routed = self.agent.handle_intent("我想再买一个充电器")
        self.assertEqual(routed["kind"], "plan")
        first = routed["result"]
        self.agent.execute(first["plan_id"], "buy_anyway")
        second = self.agent.plan_purchase("我想买一个充电器")
        self.assertEqual(second["context"]["verdict"], "known_need")
        self.assertIn("我记得", second["ui_schema"]["title"])
        actions = {action["id"] for action in second["ui_schema"]["actions"]}
        self.assertIn("reassess_purchase", actions)

    def test_reassessment_can_clear_purchase_exception(self) -> None:
        first = self.agent.plan_purchase("我想买一副耳机")
        self.agent.execute(first["plan_id"], "buy_anyway")
        remembered = self.agent.plan_purchase("我想买一副耳机")
        self.agent.execute(remembered["plan_id"], "reassess_purchase")
        next_plan = self.agent.plan_purchase("我想买一副耳机")
        self.assertEqual(next_plan["context"]["verdict"], "duplicate")

    def test_departure_guard_combines_context_and_item_locations(self) -> None:
        plan = self.agent.plan_departure_guard()
        self.assertEqual(plan["plan_type"], "departure_guard")
        self.assertEqual(plan["ui_schema"]["component"], "ambient_card")
        locations = {row["verdict"] for row in plan["ui_schema"]["checks"]}
        self.assertEqual(locations, {"仍在家中", "公司工位"})
        self.assertIn("出发倒计时：3 小时 40 分", plan["ui_schema"]["facts"])
        starts_at = datetime.fromisoformat(plan["context"]["trip"]["starts_at"])
        remaining = starts_at - datetime.now().astimezone()
        self.assertAlmostEqual(remaining.total_seconds(), 3 * 3600 + 40 * 60, delta=5)

    def test_departure_guard_executes_follow_up(self) -> None:
        plan = self.agent.plan_departure_guard()
        completed = self.agent.execute(plan["plan_id"], "use_home")
        self.assertEqual(completed["status"], "completed")
        self.assertIn("15 分钟", completed["result"]["follow_up"])

    def test_aftercare_scan_finds_return_and_resale_value(self) -> None:
        tasks = self.agent.scan()
        task_types = {task["task_type"] for task in tasks}
        self.assertIn("return_window", task_types)
        self.assertIn("resale", task_types)
        aftercare = self.agent.snapshot()["aftercare"]
        self.assertEqual(aftercare["open_returns"], 1)
        self.assertEqual(aftercare["idle_items"], 1)

    def test_pending_claim_is_not_counted_as_secured_value(self) -> None:
        tasks = self.agent.scan()
        price_task = next(task for task in tasks if task["task_type"] == "price_protection")
        self.agent.execute(price_task["task_id"], "claim")
        snapshot = self.agent.snapshot()
        self.assertEqual(snapshot["aftercare"]["value_created"], 0)
        self.assertEqual(snapshot["value_report"]["pending"], 200)
        self.assertEqual(snapshot["value_report"]["secured"], 0)

    def test_avoided_purchase_is_counted_once(self) -> None:
        plan = self.agent.plan_purchase("我想买一个 65W 充电器")
        self.agent.execute(plan["plan_id"], "skip_purchase")
        report = self.agent.snapshot()["value_report"]
        self.assertEqual(report["avoided"], 169)
        self.assertEqual(report["secured"], 169)

    def test_console_has_complete_purchase_lifecycle_history(self) -> None:
        events = [event for event in self.agent.snapshot()["lifecycle_events"] if event["item_id"] == "console"]
        stages = {event["stage"] for event in events}
        self.assertTrue({"order", "shipping", "delivered", "price", "usage", "idle"}.issubset(stages))

    def test_resale_draft_is_real_and_item_exits_after_sale(self) -> None:
        tasks = self.agent.scan()
        resale = next(task for task in tasks if task["task_type"] == "resale")
        completed = self.agent.execute(resale["task_id"], "draft_listing")
        draft = self.agent.snapshot()["resale_drafts"][0]
        self.assertEqual(draft["draft_id"], completed["result"]["draft_id"])
        self.assertIn("Nintendo Switch OLED", draft["title"])
        self.assertEqual(len(draft["photos"]), 4)
        self.assertEqual(len(draft["channels"]), 3)
        with self.assertRaisesRegex(ValueError, "授权"):
            self.agent.publish_resale_draft(draft["draft_id"])
        self.agent.select_resale_channel(draft["draft_id"], "xianyu")
        selected = self.agent.store.get_resale_draft(draft["draft_id"])
        self.assertEqual(selected["status"], "channel_selected")
        with self.assertRaisesRegex(ValueError, "回执"):
            self.agent.mark_item_sold(draft["draft_id"])
        self.agent.authorize_resale_channel(draft["draft_id"])
        with self.assertRaisesRegex(ValueError, "重复授权"):
            self.agent.authorize_resale_channel(draft["draft_id"])
        self.agent.publish_resale_draft(draft["draft_id"])
        published = self.agent.store.get_resale_draft(draft["draft_id"])
        self.assertEqual(published["status"], "published_demo")
        self.assertTrue(published["external_reference"].startswith("DEMO-"))
        self.agent.mark_item_sold(draft["draft_id"])
        report = self.agent.snapshot()["value_report"]
        self.assertEqual(report["realized"], 1450)
        self.assertEqual(report["potential"], 0)
        item_ids = {item["item_id"] for item in self.agent.snapshot()["items"]}
        self.assertNotIn("console", item_ids)
        self.assertEqual(self.agent.store.get_resale_draft(draft["draft_id"])["status"], "sold")


if __name__ == "__main__":
    unittest.main()
