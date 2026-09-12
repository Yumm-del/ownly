"""Ownly Agent 内核：理解输入、生成任务与受限动态界面。"""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta
from typing import Any

from context_tools import DemoCalendarTool, DemoWeatherTool
from storage import RESALE_CHANNELS, OwnlyStore, demo_item_records


# 中央仲裁器使用确定性规则做控制面，不让 LLM 自行决定安全与授权优先级。
# 分数只表达“现在先处理什么”，并不删除或完成被暂缓的任务。
TASK_ROUTING = {
    "safety_alert": {"score": 600, "role": "守护 Agent", "reason": "人身或产品安全风险优先"},
    "purchase_decision": {"score": 520, "role": "获得 Agent", "reason": "用户正在做明确的购买决定"},
    "return_window": {"score": 500, "role": "守护 Agent", "reason": "退货期限临近，错过后损失不可逆"},
    "price_protection": {"score": 480, "role": "守护 Agent", "reason": "价保存在期限和财务损失"},
    "departure_guard": {"score": 460, "role": "使用 Agent", "reason": "环境变化要求立即完成出发检查"},
    "trip_prep": {"score": 450, "role": "使用 Agent", "reason": "近期行程需要跨物品准备"},
    "trip_preparation": {"score": 450, "role": "使用 Agent", "reason": "近期行程需要跨物品准备"},
    "replenish": {"score": 300, "role": "使用 Agent", "reason": "消耗预测需要补给决策"},
    "maintenance": {"score": 240, "role": "使用 Agent", "reason": "维护可以在紧急事项之后处理"},
    "resale": {"score": 200, "role": "流转 Agent", "reason": "闲置流转属于可延后优化"},
    "source_review": {"score": 180, "role": "获得 Agent", "reason": "候选物品等待身份确认"},
}
DEFAULT_ROUTING = {"score": 100, "role": "所有权 Agent", "reason": "普通所有权事件"}


CATEGORY_RULES = {
    "电子": {"group":"数码家电", "keywords": ("充电器", "移动电源", "耳机", "手机", "电脑", "相机", "平板", "手表", "游戏机"), "icon": "◉", "action": "检查保修、电池与价值"},
    "家电": {"group":"数码家电", "keywords": ("电视", "冰箱", "空调", "洗衣机", "吸尘器", "咖啡机"), "icon": "▣", "action": "跟滤芯、清洁与保修"},
    "彩妆": {"group":"美妆个护", "keywords": ("口红", "唇釉", "粉底", "眼影", "腮红"), "icon": "✦", "action": "关注开封期限与色号"},
    "护肤": {"group":"美妆个护", "keywords": ("精华", "面霜", "防晒", "洁面", "乳液"), "icon": "◒", "action": "预测用量并补货"},
    "个护": {"group":"美妆个护", "keywords": ("牙膏", "洗发水", "沐浴露", "剃须", "卫生巾"), "icon": "≈", "action": "跟踪用量与更换周期"},
    "服饰": {"group":"穿搭配饰", "keywords": ("上衣", "外套", "裤", "裙", "衬衫", "羽绒服"), "icon": "♢", "action": "记录洗护与穿着频率"},
    "鞋靴": {"group":"穿搭配饰", "keywords": ("鞋", "靴", "球鞋", "跑鞋"), "icon": "⌁", "action": "跟踪穿着与清洁"},
    "箱包": {"group":"穿搭配饰", "keywords": ("背包", "手提包", "行李箱", "钱包"), "icon": "▱", "action": "记录保养与出行使用"},
    "珠宝配饰": {"group":"穿搭配饰", "keywords": ("项链", "戒指", "手镯", "耳环", "首饰"), "icon": "◇", "action": "记录保养、证书与价值"},
    "家具": {"group":"家居生活", "keywords": ("椅", "桌", "沙发", "床", "灯", "柜"), "icon": "▰", "action": "安排清洁与维护"},
    "家纺": {"group":"家居生活", "keywords": ("床单", "被子", "枕头", "窗帘", "毛巾"), "icon": "▧", "action": "安排洗护与换季收纳"},
    "厨具餐具": {"group":"家居生活", "keywords": ("锅", "刀", "餐具", "杯", "砧板"), "icon": "◐", "action": "跟踪清洁与耗损"},
    "食品饮料": {"group":"家居生活", "keywords": ("牛奶", "零食", "咖啡豆", "茶", "食品", "饮料"), "icon": "◍", "action": "管理库存、保质期与补货"},
    "母婴": {"group":"家庭成员", "keywords": ("奶粉", "纸尿裤", "婴儿", "儿童座椅"), "icon": "❋", "action": "跟踪用量、安全与成长阶段"},
    "宠物用品": {"group":"家庭成员", "keywords": ("猫粮", "狗粮", "猫砂", "宠物"), "icon": "⌾", "action": "跟踪用量与健康周期"},
    "汽车": {"group":"出行兴趣", "keywords": ("汽车", "轿车", "SUV", "电动车"), "icon": "◆", "action": "跟踪保养、保险与年检"},
    "运动户外": {"group":"出行兴趣", "keywords": ("球拍", "帐篷", "自行车", "滑雪", "哑铃", "瑜伽垫"), "icon": "△", "action": "记录使用、保养与安全检查"},
    "图书文具": {"group":"出行兴趣", "keywords": ("书", "钢笔", "笔记本", "文具"), "icon": "▤", "action": "记录阅读、借出与耗材"},
    "玩具乐器": {"group":"出行兴趣", "keywords": ("玩具", "吉他", "钢琴", "积木", "模型"), "icon": "♫", "action": "记录配件、调校与使用"},
    "收藏品": {"group":"出行兴趣", "keywords": ("手办", "卡牌", "邮票", "纪念币", "收藏"), "icon": "✧", "action": "记录来源、品相与估值"},
    "其他": {"group":"其他", "keywords": (), "icon": "●", "action": "持续守护"},
}

CATEGORY_GROUPS = ("数码家电", "美妆个护", "穿搭配饰", "家居生活", "家庭成员", "出行兴趣", "其他")

AUTONOMY_CAPABILITIES = {
    "observe_item_state": {"level":"L0","label":"观察物品状态","requires_confirmation":False,"external_effect":False},
    "prepare_price_claim": {"level":"L1","label":"准备保价材料","requires_confirmation":False,"external_effect":False},
    "prepare_resale": {"level":"L1","label":"准备出售方案","requires_confirmation":False,"external_effect":False},
    "external_listing": {"level":"L2","label":"向外部平台发布","requires_confirmation":True,"external_effect":True},
    "transfer_ownership": {"level":"L2","label":"转移物品所有权","requires_confirmation":True,"external_effect":True},
    "spend_money": {"level":"L2","label":"支付或产生费用","requires_confirmation":True,"external_effect":True},
    "low_risk_reminder": {"level":"L3","label":"按长期策略创建提醒","requires_confirmation":False,"external_effect":False},
}

TRUSTED_OBSERVATION_SOURCES = {"用户主动分享", "物品事件", "设备状态", "家庭节点"}


class OwnlyAgent:
    """以 SQLite 为记忆，以任务 schema 为当前交互输出。"""

    def __init__(self, store: OwnlyStore) -> None:
        self.store = store
        self.store.seed_missing(demo_item_records())
        self.calendar = DemoCalendarTool()
        self.weather = DemoWeatherTool()
        self._seed_console_lifecycle()

    def _seed_console_lifecycle(self) -> None:
        """建立一件商品从订单到闲置的可验证演示历史。"""
        today = date.today()
        events = [
            ("order", "订单自动出现", "从订单邮件识别 Nintendo Switch OLED · ¥2599", today-timedelta(days=420)),
            ("shipping", "物流开始运输", "承运商已揽收，预计 2 天送达", today-timedelta(days=419)),
            ("delivered", "签收并建立物品身份", "序列号、购买凭证和 7 天退货期已保存", today-timedelta(days=417)),
            ("price", "发现降价并完成保价", "购买后第 4 天降价 ¥100，保价结果已归档", today-timedelta(days=413)),
            ("usage", "持续记录使用", "累计使用 34 次，最后一次启动在 128 天前", today-timedelta(days=128)),
            ("idle", "识别为长期闲置", "连续 128 天未使用，当前预计转售价 ¥1450", today),
        ]
        for stage, title, detail, occurred_at in events:
            self.store.add_lifecycle_event("console", stage, title, detail, occurred_at.isoformat())

    def handle_intent(self, utterance: str, source: str = "自然语言") -> dict[str, Any]:
        """判断用户是在描述新物品，还是要求系统完成跨物品任务。"""
        if any(keyword in utterance for keyword in ("旅行", "出差", "去深圳", "打包", "行李")):
            return {"kind": "plan", "result": self.plan_trip(utterance)}
        purchase_pattern = r"(?:(?:想|准备|打算|要不要|值得).{0,3}(?:买|购买)|再买|下单)"
        if re.search(purchase_pattern, utterance):
            return {"kind": "plan", "result": self.plan_purchase(utterance)}
        return {"kind": "item", "result": self.understand_item(utterance, source)}

    def observe_and_infer(
        self,
        signal_type: str,
        payload: dict[str, Any],
        source: str = "用户主动分享",
        confidence: float = 1.0,
    ) -> dict[str, Any]:
        """从一条有来源的信号形成可解释假设，不把行为信号直接当成用户意图。

        输入是未来浏览器分享、设备或家庭节点产生的结构化观察；输出同时包含
        正向证据、反证、置信度和允许的下一步。推断不足时只继续观察。
        """
        if source not in TRUSTED_OBSERVATION_SOURCES:
            raise ValueError("观察来源未获得授权")
        if not signal_type.strip():
            raise ValueError("观察信号类型不能为空")
        bounded_confidence = max(0.0, min(float(confidence), 1.0))
        observation = self.store.add_observation({
            "signal_type": signal_type,
            "source": source,
            "payload": payload,
            "confidence": bounded_confidence,
        })

        category = str(payload.get("category", "其他"))
        subject = str(payload.get("subject", "同类新品"))
        subject_relations = {
            "游戏": ("Switch", "掌机", "游戏机", "主机"),
            "耳机": ("耳机",),
            "手机": ("手机",),
            "电脑": ("电脑", "笔记本"),
            "充电": ("充电器", "移动电源"),
        }
        relation_terms = next(
            (terms for keyword, terms in subject_relations.items() if keyword in subject), ()
        )
        category_items = [item for item in self.store.list_items() if item["category"] == category]
        related_items = (
            [item for item in category_items if any(term in item["name"] for term in relation_terms)]
            if relation_terms else category_items
        )
        evidence = [{"type":"observation","label":f"用户主动分享了{subject}","source":source,"weight":0.2 * bounded_confidence}]
        counterevidence: list[dict[str, Any]] = []
        score = 0.2 * bounded_confidence

        if related_items:
            evidence.append({"type":"ownership","label":f"物品仓已有 {len(related_items)} 件{category}物品","source":"个人所有权图谱","weight":0.15})
            score += 0.15
        idle_items = []
        for item in related_items:
            idle_days = int(item.get("attributes", {}).get("闲置天数", "0") or 0)
            if idle_days >= 90:
                idle_items.append(item)
                evidence.append({"type":"idle","label":f"{item['name']} 已闲置 {idle_days} 天","source":"物品生命周期","weight":0.35})
                score += 0.35
            if item.get("attributes", {}).get("上次使用") in {"今天", "昨天"}:
                counterevidence.append({"type":"recent_use","label":f"{item['name']} 最近仍在使用","source":"物品生命周期","weight":-0.25})
                score -= 0.25

        score = round(max(0.0, min(score, 0.95)), 2)
        prepare = score >= 0.65 and bool(idle_items)
        proposed_action = {
            "capability_id": "prepare_resale" if prepare else "observe_item_state",
            "mode": "prepare_only" if prepare else "observe_only",
            "title": "比较继续持有、出售与置换" if prepare else "继续观察，不主动打扰",
            "requires_confirmation": False,
            "external_effect": False,
            "item_ids": [item["item_id"] for item in idle_items],
        }
        steps = [
            {"phase":"perception","status":"completed","detail":f"接收 {source} 信号"},
            {"phase":"reasoning","status":"completed","detail":f"找到 {len(related_items)} 件相关物品，并检查反证"},
            {"phase":"planning","status":"completed" if prepare else "skipped","detail":proposed_action["title"]},
            {"phase":"authorization","status":"not_required","detail":"当前动作不产生外部影响"},
            {"phase":"execution","status":"prepared" if prepare else "not_started","detail":"仅准备，不发布、不支付、不转移所有权"},
            {"phase":"verification","status":"waiting","detail":"等待用户后续行为或新的物品事件"},
        ]
        run = self.store.create_agent_run({
            "goal": f"判断用户是否正在考虑更换{category}物品",
            "status": "prepared" if prepare else "observing",
            "autonomy_level": "L1" if prepare else "L0",
            "evidence": evidence,
            "counterevidence": counterevidence,
            "proposed_action": {**proposed_action, "confidence": score, "is_hypothesis": True},
            "steps": steps,
        })
        self.store.add_event("inference", "形成可解释的意图假设", f"置信度 {score:.0%} · {proposed_action['title']}")
        return {"observation": observation, "run": run}

    @staticmethod
    def capability_decision(capability_id: str, user_confirmed: bool = False) -> dict[str, Any]:
        """中央权限判断：外部发布、支付和所有权转移不能被预测意图越权执行。"""
        capability = AUTONOMY_CAPABILITIES.get(capability_id)
        if capability is None:
            raise ValueError("未知的 Agent 能力")
        allowed = not capability["requires_confirmation"] or user_confirmed
        return {
            "capability_id": capability_id,
            **capability,
            "allowed": allowed,
            "reason": "用户已明确授权" if user_confirmed else ("低风险本地动作" if allowed else "涉及外部影响，需要用户明确授权"),
        }

    def set_autonomy_mode(self, mode: str) -> dict[str, Any]:
        """保存用户选择的总体自主模式；高风险能力不会因模式变化而取消确认。"""
        modes = {
            "cautious": {"label":"谨慎模式","description":"只观察和解释，准备材料前也尽量询问"},
            "balanced": {"label":"平衡模式","description":"低风险材料自动准备，对外动作始终确认"},
            "managed": {"label":"托管模式","description":"依据逐项策略主动准备，高风险动作仍需确认"},
        }
        if mode not in modes:
            raise ValueError("未知的自主模式")
        self.store.set_memory("autonomy_mode", {"mode":mode, **modes[mode], "updated_at":date.today().isoformat()})
        self.store.add_event("policy", "自主模式已更新", modes[mode]["label"])
        return self.policy_center()

    def set_policy_enabled(self, policy_id: str, enabled: bool) -> dict[str, Any]:
        policy = self.store.set_policy_enabled(policy_id, enabled)
        self.store.add_event("policy", "授权策略已更新", f"{policy['name']} · {'已启用' if enabled else '已停用'}")
        return self.policy_center()

    def policy_center(self) -> dict[str, Any]:
        mode = self.store.get_memory("autonomy_mode") or {
            "mode":"balanced", "label":"平衡模式", "description":"低风险材料自动准备，对外动作始终确认"
        }
        return {"mode":mode, "policies":self.store.authorization_policies()}

    def _task_agent_trace(self, task: dict[str, Any]) -> dict[str, Any]:
        """把任务状态投影为面向用户的可解释 Agent 工作台。"""
        schema = task["ui_schema"]
        task_type = task.get("task_type") or task.get("plan_type", "unknown")
        capability_by_task = {
            "price_protection":"prepare_price_claim",
            "resale":"prepare_resale",
            "return_window":"observe_item_state",
            "replenish":"observe_item_state",
            "maintenance":"observe_item_state",
            "trip_prep":"observe_item_state",
            "source_review":"observe_item_state",
        }
        capability_id = capability_by_task.get(task_type, "observe_item_state")
        policies = self.store.authorization_policies()
        amount = 200 if task_type == "price_protection" else None
        matched_policy = next((policy for policy in policies if policy["enabled"] and policy["capability_id"] == capability_id and (policy["condition"].get("max_amount") is None or amount is not None and amount <= policy["condition"]["max_amount"])), None)
        counterevidence = {
            "price_protection":["商家可能因活动规则或商品规格不同而驳回"],
            "return_window":["一次使用较少不等于物品对未来没有价值"],
            "resale":["未来重新使用的可能性仍需由用户判断"],
            "replenish":["实际用量可能因出行计划而变化"],
            "maintenance":["真实清洁状态尚未经过视觉确认"],
        }.get(task_type, ["当前结论会随新的物品事件更新"])
        paused = task.get("attention_state") == "paused"
        needs_confirmation = bool(schema.get("actions")) and not paused
        return {
            "headline": "已暂缓，先处理更紧急的事" if paused else ("已完成判断，等待你的选择" if needs_confirmation else "正在持续观察"),
            "role": task.get("agent_role", "所有权 Agent"),
            "attention_state": task.get("attention_state", "active"),
            "priority_reason": task.get("priority_reason", "当前结论会随新事件更新"),
            "paused_by_title": task.get("paused_by_title"),
            "autonomy_level":AUTONOMY_CAPABILITIES[capability_id]["level"],
            "capability":AUTONOMY_CAPABILITIES[capability_id]["label"],
            "evidence":schema.get("facts", []),
            "counterevidence":counterevidence,
            "matched_policy":matched_policy,
            "steps":[
                {"phase":"感知","status":"completed","detail":"物品事件已进入 Agent"},
                {"phase":"判断","status":"completed","detail":f"已检查 {len(schema.get('facts', []))} 条证据和反证"},
                {"phase":"规划","status":"completed","detail":schema["title"]},
                {"phase":"授权","status":"paused" if paused else ("waiting" if needs_confirmation else "not_required"),"detail":f"先处理：{task['paused_by_title']}" if paused else ("等待你的选择" if needs_confirmation else "当前动作不需要授权")},
                {"phase":"执行","status":"pending","detail":"尚未产生外部影响"},
                {"phase":"验证","status":"pending","detail":"执行后等待工具回执"},
            ],
        }

    @staticmethod
    def _arbitrate_tasks(tasks: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        """统一排序并解释任务冲突，始终只开放当前最高优先级行动。"""
        if not tasks:
            return [], {"state": "quiet", "primary": None, "active_count": 0, "paused_count": 0}

        ranked: list[dict[str, Any]] = []
        for original in tasks:
            task = dict(original)
            routing = TASK_ROUTING.get(task.get("task_type", ""), DEFAULT_ROUTING)
            task["arbitration_score"] = routing["score"]
            task["agent_role"] = routing["role"]
            task["priority_reason"] = routing["reason"]
            ranked.append(task)
        ranked.sort(key=lambda task: (-task["arbitration_score"], task.get("created_at", "")))

        primary = ranked[0]
        for task in ranked:
            active = task["arbitration_score"] == primary["arbitration_score"]
            task["attention_state"] = "active" if active else "paused"
            if not active:
                task["paused_by"] = primary["task_id"]
                task["paused_by_title"] = primary["title"]

        active_count = sum(task["attention_state"] == "active" for task in ranked)
        return ranked, {
            "state": "focused",
            "primary": {"task_id": primary["task_id"], "title": primary["title"], "role": primary["agent_role"], "reason": primary["priority_reason"]},
            "active_count": active_count,
            "paused_count": len(ranked) - active_count,
        }

    def plan_purchase(self, utterance: str) -> dict[str, Any]:
        """在购买发生前检索已有物品，生成基于所有权的消费决策。"""
        items = self.store.list_items()
        keyword_matches = [
            (category, keyword)
            for category, rule in CATEGORY_RULES.items()
            for keyword in rule["keywords"]
            if keyword.lower() in utterance.lower()
        ]
        category, subject = max(keyword_matches, key=lambda pair: len(pair[1])) if keyword_matches else ("其他", "这件商品")
        matched_items = [item for item in items if subject in item["name"]]
        price_match = re.search(r"(?:¥|￥|价格(?:是)?|售价)\s*(\d+(?:\.\d+)?)|(\d+(?:\.\d+)?)\s*元", utterance)
        parsed_price = next((float(value) for value in price_match.groups() if value), None) if price_match else None
        reference_prices = {"充电器":169, "耳机":1299, "防晒":269, "椅":3299}
        estimated_cost = int(parsed_price or reference_prices.get(subject, 0))
        purchase_memory = self.store.get_memory(f"purchase_exception:{subject}")
        comparisons = [
            {"label":item["name"],"verdict":item["location"],"state":"ok","detail":f"{item['category']} · {item['next_action']}"}
            for item in matched_items
        ]
        has_alternative = bool(matched_items)
        remembers_need = bool(purchase_memory and purchase_memory.get("allow_additional"))
        if has_alternative and remembers_need:
            title = f"我记得：你需要额外的{subject}"
            body = f"虽然物品仓已有 {len(matched_items)} 件同类物品，但你上次确认过额外需求。Ownly 保留已有物品信息，不再机械阻止购买。"
            actions = [{"id":"buy_anyway","label":"继续购买","style":"primary"},{"id":"reassess_purchase","label":"重新评估","style":"secondary"}]
        elif has_alternative:
            title = f"先别买：你已经有 {len(matched_items)} 件可替代的{subject}"
            body = "Ownly 检查了同类物品的位置和状态。这次购买与现有能力重叠，新增价值较低。"
            actions = [{"id":"skip_purchase","label":"不买了","style":"primary"},{"id":"buy_anyway","label":"仍然需要","style":"secondary"}]
        else:
            title = f"物品仓里没有{subject}，可以考虑购买"
            body = f"Ownly 已检查全部物品，没有发现同类{subject}；建议先加入愿望清单，继续比较需求与价格。"
            actions = [{"id":"add_to_wishlist","label":"加入愿望清单","style":"primary"},{"id":"buy_anyway","label":"继续购买","style":"secondary"}]
        schema = {
            "version": 1,
            "component": "purchase_card",
            "tone": "purchase",
            "title": title,
            "body": body,
            "facts": [f"识别品类：{category}", f"检索 {len(items)} 件已有物品", f"找到 {len(matched_items)} 件同类替代品"] + (["长期记忆：已确认额外需求"] if remembers_need else []) + ([f"预计避免重复支出 ¥{estimated_cost}"] if estimated_cost and has_alternative and not remembers_need else []),
            "comparisons": comparisons,
            "actions": actions,
        }
        verdict = "known_need" if remembers_need and has_alternative else ("duplicate" if has_alternative else "gap")
        plan = self.store.create_plan({"plan_type":"purchase_decision","title":schema["title"],"context":{"utterance":utterance,"subject":subject,"category":category,"verdict":verdict,"matched_item_ids":[item["item_id"] for item in matched_items],"avoided_cost":estimated_cost},"ui_schema":schema})
        self.store.add_event("intent", "识别购买意图", utterance)
        self.store.add_event("retrieval", "检索可替代物品", f"在 {len(items)} 件物品中找到 {len(matched_items)} 件{subject}")
        self.store.add_event("decision", "生成购前建议", "建议避免重复购买" if has_alternative else "未发现同类，可以考虑购买")
        return plan

    def plan_departure_guard(self) -> dict[str, Any]:
        """组合离家状态、近期行程和物品位置，生成无需打开 App 的主动提醒。"""
        items = {item["item_id"]: item for item in self.store.list_items()}
        trip = self.calendar.upcoming_trip("即将离家前往深圳")
        starts_at = datetime.fromisoformat(trip["starts_at"])
        now = datetime.now().astimezone()
        remaining_minutes = max(0, round((starts_at - now).total_seconds() / 60))
        remaining_hours, remaining_minutes = divmod(remaining_minutes, 60)
        countdown = f"{remaining_hours} 小时 {remaining_minutes} 分"
        home = items.get("charger_home")
        office = items.get("charger_office")
        checks = []
        if home:
            checks.append({"label":home["name"],"verdict":"仍在家中","state":"warn","detail":"常用充电器 · 尚未检测到装包"})
        if office:
            checks.append({"label":office["name"],"verdict":"公司工位","state":"info","detail":"备用方案 · 路线顺路可取"})
        schema = {
            "version": 1,
            "component": "ambient_card",
            "tone": "ambient",
            "title": "你准备离开，但充电器还没进包",
            "body": "根据深圳行程和离家状态，Ownly 主动检查了出行物品。家中充电器尚未检测到移动，公司还有一件备用。",
            "facts": ["环境：正在离开家", "行程：深圳 · 4 天", f"出发倒计时：{countdown}"],
            "checks": checks,
            "actions": [{"id":"use_home","label":"带上家中这件","style":"primary"},{"id":"route_office","label":"去公司取备用","style":"secondary"}],
        }
        plan = self.store.create_plan({"plan_type":"departure_guard","title":schema["title"],"context":{"trip":trip,"trigger":"leaving_home","checked_item_ids":[item["item_id"] for item in (home, office) if item]},"ui_schema":schema})
        self.store.add_event("context", "检测到环境变化", "手机位置状态：准备离开家")
        self.store.add_event("planner", "主动检查出行物品", f"检查 {len(items)} 件物品并定位两件充电器")
        return plan

    def understand_item(self, utterance: str, source: str = "自然语言") -> dict[str, Any]:
        """从一句自然语言中提取物品名称、品类与可选价格。

        原型先使用可解释规则保证稳定；后续 Vision/LLM adapter 输出相同结构即可替换。
        """
        text = utterance.strip()
        if not text:
            raise ValueError("请描述你想收录的物品")
        category = next((name for name, rule in CATEGORY_RULES.items() if any(word.lower() in text.lower() for word in rule["keywords"])), "其他")
        price_match = re.search(r"(?:¥|￥|花了?|价格(?:是)?)\s*(\d+(?:\.\d+)?)", text)
        price = float(price_match.group(1)) if price_match else None
        name = re.sub(r"^(?:这是|这个是|帮我记住|我(?:刚)?买了?|新增|收录)\s*", "", text)
        name = re.sub(r"(?:，|,)?\s*(?:¥|￥|花了?|价格(?:是)?)\s*\d+(?:\.\d+)?.*$", "", name).strip(" ，。,.!")
        name = name or text
        rule = CATEGORY_RULES[category]
        item = self.store.add_item({"name": name, "category": category, "icon": rule["icon"], "source": source,
                                    "purchase_price": price, "current_value": price, "attributes": {"理解方式":"自然语言"},
                                    "next_action": rule["action"], "next_action_date": (date.today()+timedelta(days=30)).isoformat()})
        self.store.add_event("perception", "理解自然语言", f"{category} · {name}")
        self.store.add_event("planner", "建立管理计划", rule["action"])
        return item

    def scan(self) -> list[dict[str, Any]]:
        """根据整个物品仓的状态生成任务，而不是返回固定提醒。

        两层扫描：第一层是物品生命周期的"守护"（补货/维护/保价），
        每个守护任务在演示周期内只生成一次（has_task_record 守卫），
        处理过的事不再重复打扰；守护全部处理后，第二层把"行程"作为
        新的输入事件推给 Agent，反查物品图谱生成出发卡（departure_card）。
        叙事可复现：守护 → 处理 → 行程到达 → 处理 → 安静。
        """
        items = {item["item_id"]: item for item in self.store.list_items()}
        tasks = []
        if "serum" in items and not self.store.has_task_record("serum", "replenish"):
            tasks.append(self.store.create_task(self._replenish_task(items["serum"])))
        if "chair" in items and not self.store.has_task_record("chair", "maintenance"):
            tasks.append(self.store.create_task(self._maintenance_task(items["chair"])))
        if "airwave" in items and not self.store.has_task_record("airwave", "price_protection"):
            self.store.update_item_value("airwave", 1099)
            tasks.append(self.store.create_task(self._price_task(items["airwave"])))
        if "projector" in items and not self.store.has_task_record("projector", "return_window"):
            tasks.append(self.store.create_task(self._return_task(items["projector"])))
        if "console" in items and not self.store.has_task_record("console", "resale"):
            tasks.append(self.store.create_task(self._resale_task(items["console"])))
        # 行程层：守护无未决任务、且行程任务从未生成过时才触发
        pending_types = {task["task_type"] for task in self.store.pending_tasks()}
        if not pending_types & {"replenish", "maintenance", "price_protection", "trip_prep"}:
            anchor = items["car"]["item_id"] if "car" in items else items[list(items)[0]]["item_id"]
            if not self.store.has_task_record(anchor, "trip_prep"):
                tasks.append(self.store.create_task(self._trip_task(items)))
        self.store.add_event("proactivity", "后台扫描完成", f"从 {len(items)} 件物品中生成 {len(tasks)} 个可行动任务")
        return tasks

    def discover_items(self) -> dict[str, Any]:
        """从生活数据源发现物品，并只把低置信度结果交给用户确认。"""
        items = {item["item_id"]: item for item in self.store.list_items()}
        anchor = "car" if "car" in items else next(iter(items))
        if self.store.has_task_record(anchor, "source_review"):
            self.store.add_event("dedupe", "数据源同步完成", "没有发现需要处理的新物品")
            return {"status": "no_change"}
        candidates = [
            {"item_id":"discovered-coffee","name":"AeroPress Go 咖啡器","category":"厨具餐具","icon":"◐","source":"邮件识别","brand":"AeroPress","location":"厨房","purchase_price":299,"confidence":.96,"evidence":"品牌订单邮件 · 2026-08-21"},
            {"item_id":"discovered-bag","name":"CabinZero 28L 背包","category":"箱包","icon":"▱","source":"订单同步","brand":"CabinZero","location":"玄关","purchase_price":699,"confidence":.93,"evidence":"购物订单 · 已签收"},
            {"item_id":"airwave","name":"AirWave Pro 耳机","category":"电子","icon":"◉","source":"订单同步","brand":"AirWave","location":"书房","purchase_price":1299,"confidence":.99,"evidence":"订单与已有序列号一致"},
            {"item_id":"discovered-lamp","name":"便携阅读灯","category":"家电","icon":"▣","source":"相册识别","brand":"","location":"待确认","purchase_price":None,"confidence":.68,"evidence":"最近相册出现 4 次 · 型号不可见"},
        ]
        rows: list[dict[str, str]] = []
        imported = 0
        for candidate in candidates:
            if candidate["item_id"] in items:
                rows.append({"label":candidate["name"],"verdict":"已在物品仓","state":"info","detail":candidate["evidence"]})
            elif candidate["confidence"] >= .9:
                self.store.add_item({
                    **{key: value for key, value in candidate.items() if key not in {"confidence", "evidence"}},
                    "current_value": candidate["purchase_price"],
                    "attributes": {"发现置信度": f"{candidate['confidence']:.0%}", "来源证据": candidate["evidence"]},
                    "next_action": "等待首次使用信号",
                    "next_action_date": (date.today() + timedelta(days=30)).isoformat(),
                })
                imported += 1
                rows.append({"label":candidate["name"],"verdict":"已自动收录","state":"ok","detail":candidate["evidence"]})
            else:
                rows.append({"label":candidate["name"],"verdict":"需要确认","state":"warn","detail":candidate["evidence"]})
        schema = self._schema(
            "discovery", "Ownly 从生活痕迹中发现了新物品",
            "我已完成来源核对、分类和去重；高置信度结果直接进入物品仓，只留下一个判断给你。",
            ["已连接 3 个演示数据源", f"自动收录 {imported} 件", "跳过 1 件重复记录 · 1 件待确认"],
            [{"id":"confirm_discovery","label":"是我的，收录","style":"primary"},{"id":"dismiss_discovery","label":"不是我的","style":"secondary"}],
            component="discovery_card",
        )
        schema["discoveries"] = rows
        task = self.store.create_task({"item_id":anchor,"task_type":"source_review","title":schema["title"],"reason":schema["body"],"priority":"medium","ui_schema":schema})
        self.store.add_event("connector", "读取生活数据源", "订单、邮件与相册演示 adapter")
        self.store.add_event("dedupe", "完成身份合并", f"自动收录 {imported} 件，跳过 1 件重复记录")
        return task

    def plan_trip(self, utterance: str) -> dict[str, Any]:
        """组合日历、天气和物品仓，生成旅行准备的系统级动态界面。"""
        trip = self.calendar.upcoming_trip(utterance)
        weather = self.weather.forecast(trip["destination"], trip["start_date"], trip["days"])
        items = self.store.list_items()
        owned_names = [item["name"] for item in items]
        available = [name for name in owned_names if any(word in name for word in ("耳机", "防晒", "行李箱", "充电"))]
        concerns = []
        if any("精华" in name for name in owned_names):
            concerns.append("精华余量约 18%，旅途中可能用完")
        if not any("充电器" in name or "移动电源" in name for name in owned_names):
            concerns.append("没有找到移动电源或旅行充电器")
        if not any("伞" in name for name in owned_names):
            concerns.append("预报有阵雨，物品仓没有找到雨具")
        schema = {
            "version": 1,
            "component": "journey_card",
            "tone": "journey",
            "title": f"{trip['destination']} {trip['days']} 天，物品已准备 {max(35, 80-len(concerns)*10)}%",
            "body": "我结合行程、天气和你已经拥有的物品生成了准备方案。",
            "facts": [f"{weather['temperature']} · {' / '.join(weather['conditions'])}", f"已找到 {len(available)} 件可用物品", f"发现 {len(concerns)} 个需要处理的缺口"],
            "sections": [
                {"title": "可以直接带走", "items": available or ["AirWave Pro 耳机"]},
                {"title": "出发前处理", "items": concerns},
            ],
            "actions": [{"id": "build_pack", "label": "生成打包计划", "style": "primary"}, {"id": "adjust", "label": "调整行程", "style": "secondary"}],
        }
        context = {"trip": trip, "weather": weather, "owned_item_ids": [item["item_id"] for item in items], "concerns": concerns}
        plan = self.store.create_plan({"plan_type": "trip_preparation", "title": schema["title"], "context": context, "ui_schema": schema})
        self.store.add_event("intent", "理解旅行意图", f"{trip['destination']} · {trip['days']} 天")
        self.store.add_event("tool", "组合日历与天气", f"{weather['temperature']}，{weather['rain_probability']}% 降雨概率")
        self.store.add_event("planner", "读取个人物品图谱", f"检查 {len(items)} 件物品并发现 {len(concerns)} 个缺口")
        return plan

    def execute(self, task_id: str, action_id: str) -> dict[str, Any]:
        """执行动态卡片中的受限动作，并保存跨端共享结果。"""
        if task_id.startswith("plan-"):
            return self._execute_plan(task_id, action_id)
        task = self.store.get_task(task_id)
        allowed = {action["id"] for action in task["ui_schema"]["actions"]}
        if action_id not in allowed:
            raise ValueError("该动作不在 Agent 授权范围内")
        if task["task_type"] == "source_review" and action_id == "confirm_discovery":
            existing_ids = {item["item_id"] for item in self.store.list_items()}
            if "discovered-lamp" not in existing_ids:
                self.store.add_item({"item_id":"discovered-lamp","name":"便携阅读灯","category":"家电","icon":"▣","source":"相册识别","location":"待确认","attributes":{"发现置信度":"68%","来源证据":"最近相册出现 4 次"},"next_action":"询问放置位置","next_action_date":(date.today()+timedelta(days=7)).isoformat()})
        result = {"action_id": action_id, "message": self._result_message(task["task_type"], action_id), "completed_at": date.today().isoformat()}
        if task["task_type"] == "price_protection" and action_id == "claim":
            result["pending_value"] = 200
            self.store.record_value_event({"source_key":f"task:{task_id}","item_id":task["item_id"],"value_kind":"pending","amount":200,"title":"保价申请处理中","detail":"耳机降价 ¥200，材料已提交，等待商家确认"})
        if task["task_type"] == "return_window" and action_id == "start_return":
            result["pending_value"] = 2399
            self.store.record_value_event({"source_key":f"task:{task_id}","item_id":task["item_id"],"value_kind":"pending","amount":2399,"title":"退货退款处理中","detail":"已生成退货材料，到账后才计入实际获得"})
        if task["task_type"] == "resale" and action_id == "draft_listing":
            result["potential_value"] = 1450
            draft = self.store.create_resale_draft({
                "item_id":"console",
                "title":"Nintendo Switch OLED 白色 95新｜原装配件齐全",
                "description":"自用 Nintendo Switch OLED 白色款，功能正常，屏幕无明显划痕。累计使用约 34 次，已闲置 128 天。原装底座、Joy-Con、充电器、腕带和包装盒齐全，可当面验机。",
                "condition":"95 新 · 功能正常 · 轻微使用痕迹",
                "price":1450,
                "photos":["正面亮屏照","背面与序列号","Joy-Con 与底座","完整包装配件"],
                "channels": RESALE_CHANNELS,
            })
            result["draft_id"] = draft["draft_id"]
            self.store.record_value_event({"source_key":f"resale:{draft['draft_id']}","item_id":"console","value_kind":"potential","amount":1450,"title":"可释放闲置价值","detail":"Switch 出售方案已生成，尚未成交"})
            self.store.add_lifecycle_event("console", "resale_draft", "生成二手发布草稿", "标题、描述、成色、价格和图片清单已完成", date.today().isoformat())
        completed = self.store.complete_task(task_id, result)
        self.store.add_event("action", "任务已执行", result["message"])
        self.store.add_event("handoff", "跨设备状态同步", "手机与 Watch 已读取同一任务结果")
        return completed

    def _execute_plan(self, plan_id: str, action_id: str) -> dict[str, Any]:
        plan = self.store.get_plan(plan_id)
        allowed = {action["id"] for action in plan["ui_schema"]["actions"]}
        if action_id not in allowed:
            raise ValueError("该动作不在 Agent 授权范围内")
        if plan["plan_type"] == "purchase_decision":
            subject = plan["context"]["subject"]
            if action_id == "buy_anyway":
                self.store.set_memory(f"purchase_exception:{subject}", {"allow_additional":True,"reason":"用户确认额外需求","learned_at":date.today().isoformat()})
            elif action_id in {"skip_purchase", "reassess_purchase"}:
                self.store.set_memory(f"purchase_exception:{subject}", {"allow_additional":False,"reason":"用户要求恢复购前检查","learned_at":date.today().isoformat()})
            messages = {"skip_purchase":"已取消这次重复购买；以后遇到同类商品会先检查现有物品", "add_to_wishlist":"已加入愿望清单，Ownly 会继续观察价格与实际需求", "buy_anyway":"已记住这次购买有额外需求，不再按重复购买处理", "reassess_purchase":"已恢复严格购前检查，下次会重新判断是否重复"}
            result = {"action_id":action_id,"message":messages[action_id],"avoided_cost":plan["context"]["avoided_cost"] if action_id=="skip_purchase" else 0,"completed_at":date.today().isoformat()}
            if action_id == "skip_purchase":
                self.store.record_value_event({"source_key":f"plan:{plan_id}","item_id":plan["context"]["matched_item_ids"][0] if plan["context"]["matched_item_ids"] else None,"value_kind":"avoided","amount":plan["context"]["avoided_cost"],"title":"避免重复购买","detail":f"购买前发现已有同类物品：{subject}"})
        elif plan["plan_type"] == "departure_guard":
            message = "已把家中充电器加入出发清单，并在 15 分钟后复查位置" if action_id == "use_home" else "已将公司加入出发路线，到达附近时会再次提醒"
            result = {"action_id": action_id, "message": message, "follow_up": "15 分钟后复查", "completed_at": date.today().isoformat()}
        else:
            result = {
                "action_id": action_id,
                "message": "打包计划已生成；出发前一天将主动复查天气、充电状态和物品位置" if action_id == "build_pack" else "等待用户调整行程",
                "checklist": ["AirWave Pro 耳机", "为电子设备充电", "补充或替换精华", "准备雨具"],
                "completed_at": date.today().isoformat(),
            }
        completed = self.store.complete_plan(plan_id, result)
        event_titles = {"purchase_decision":"购买决策已记录", "departure_guard":"离家方案已执行"}
        event_title = event_titles.get(plan["plan_type"], "旅行准备计划已建立")
        self.store.add_event("action", event_title, result["message"])
        self.store.add_event("handoff", "跨设备状态同步", "手机与 Watch 已读取相同结果")
        return completed

    def snapshot(self) -> dict[str, Any]:
        items = self.store.list_items()
        tasks, arbitration = self._arbitrate_tasks(self.store.pending_plans() + self.store.pending_tasks())
        for task in tasks:
            task["agent_trace"] = self._task_agent_trace(task)
        open_returns = sum(1 for item in items if item.get("attributes", {}).get("退货截止", "") >= date.today().isoformat())
        idle_items = sum(1 for item in items if int(item.get("attributes", {}).get("闲置天数", "0")) >= 90)
        catalog = [{"name": name, "group": rule["group"], "icon": rule["icon"], "action": rule["action"]} for name, rule in CATEGORY_RULES.items()]
        return {"phase": "attention" if tasks else "warehouse", "items": items, "tasks": tasks, "category_catalog": catalog,
                "events": self.store.recent_events(), "summary": {"total": len(items), "categories": len({item["category"] for item in items}), "attention": len(tasks)},
                "aftercare": {"value_created": self.store.value_created(), "open_returns": open_returns, "idle_items": idle_items},
                "value_report": self.store.value_report(),
                "lifecycle_events": self.store.lifecycle_events(), "resale_drafts": self.store.resale_drafts(),
                "agent_runs": self.store.agent_runs(), "capabilities": AUTONOMY_CAPABILITIES,
                "policy_center": self.policy_center(), "attention_arbitration": arbitration}

    def select_resale_channel(self, draft_id: str, channel_id: str) -> dict[str, Any]:
        """让 Agent 保存渠道选择，但不越过用户执行账号授权。"""
        draft = self.store.select_resale_channel(draft_id, channel_id)
        channel = next(row for row in draft["channels"] if row["id"] == channel_id)
        self.store.add_event("decision", "已选择出售渠道", f"{channel['name']} · 预计到手 ¥{channel['price']:.0f}")
        return draft

    def authorize_resale_channel(self, draft_id: str) -> dict[str, Any]:
        """演示授权边界：只连接 Demo connector，不冒充真实闲鱼授权。"""
        draft = self.store.authorize_resale_channel(draft_id)
        self.store.add_event("consent", "用户已确认发布授权", "仅授权本次 Demo connector 提交")
        return draft

    def publish_resale_draft(self, draft_id: str) -> dict[str, Any]:
        draft = self.store.get_resale_draft(draft_id)
        policy = self.capability_decision("external_listing", draft["authorization_status"] == "demo_authorized")
        if not policy["allowed"]:
            raise ValueError("发布前需要用户确认渠道授权")
        reference = f"DEMO-{draft_id.upper()}"
        draft = self.store.record_resale_publish(draft_id, reference)
        channel = next(row for row in draft["channels"] if row["id"] == draft["selected_channel"])
        self.store.add_lifecycle_event(draft["item_id"], "published_demo", "Demo 渠道已返回发布回执", f"{channel['name']} · 回执 {reference} · 非真实挂牌", date.today().isoformat())
        self.store.add_event("tool", "Demo connector 返回回执", f"{channel['name']} · {reference} · 非真实发布")
        return draft

    def mark_item_sold(self, draft_id: str) -> dict[str, Any]:
        current = self.store.get_resale_draft(draft_id)
        if current["status"] != "published_demo":
            raise ValueError("收到渠道发布回执后才能记录售出")
        draft = self.store.update_resale_status(draft_id, "sold")
        self.store.record_value_event({"source_key":f"resale:{draft_id}","item_id":draft["item_id"],"value_kind":"realized","amount":draft["price"],"title":"闲置出售收入","detail":f"{draft['title']} 已成交并退出活跃物品仓"})
        self.store.update_item_status(draft["item_id"], "已出售", "生命周期已完成")
        self.store.add_lifecycle_event(draft["item_id"], "sold", "物品已经售出", f"成交价 ¥{draft['price']:.0f}，退出活跃物品仓", date.today().isoformat())
        self.store.add_event("lifecycle", "物品退出活跃仓", f"{draft['title']} · 已售出")
        return draft

    @staticmethod
    def _schema(kind: str, title: str, body: str, facts: list[str], actions: list[dict[str, str]], component: str = "decision_card") -> dict[str, Any]:
        """生成受限 UI schema；前端只能渲染允许的组件与动作。

        参数 component 决定前端渲染哪种卡片：decision_card（单问题决策）或
        departure_card（行程出发检查，带逐项清单）。
        """
        return {"version": 1, "component": component, "tone": kind, "title": title, "body": body, "facts": facts, "actions": actions}

    def _replenish_task(self, item: dict[str, Any]) -> dict[str, Any]:
        schema = self._schema("care", "出行前补充精华？", "按当前用量预计 12 天后用完。", ["预计余量 18%", "补货配送约 3 天"], [{"id":"add_to_plan","label":"加入补货计划","style":"primary"},{"id":"later","label":"稍后","style":"secondary"}])
        return {"item_id":item["item_id"], "task_type":"replenish", "title":schema["title"], "reason":schema["body"], "priority":"high", "ui_schema":schema}

    def _maintenance_task(self, item: dict[str, Any]) -> dict[str, Any]:
        schema = self._schema("maintenance", "座椅该清洁了", "使用周期与材质需要一次深度清洁。", ["已使用 330 天", "织物材质"], [{"id":"schedule","label":"安排周末","style":"primary"},{"id":"done","label":"已经清洁","style":"secondary"}])
        return {"item_id":item["item_id"], "task_type":"maintenance", "title":schema["title"], "reason":schema["body"], "priority":"medium", "ui_schema":schema}

    def _price_task(self, item: dict[str, Any]) -> dict[str, Any]:
        schema = self._schema("value", "耳机降价 ¥200", "仍在保价期，证据已经准备好。", ["购买价 ¥1299", "当前价 ¥1099"], [{"id":"claim","label":"申请保价","style":"primary"},{"id":"ignore","label":"忽略","style":"secondary"}])
        return {"item_id":item["item_id"], "task_type":"price_protection", "title":schema["title"], "reason":schema["body"], "priority":"medium", "ui_schema":schema}

    def _return_task(self, item: dict[str, Any]) -> dict[str, Any]:
        deadline = item["attributes"]["退货截止"]
        schema = self._schema("return", "投影仪退货期只剩 2 天", "使用次数很低，我已经整理好订单信息；现在决定仍来得及。", [f"退货截止 {deadline}", "购买价 ¥2399", "目前仅使用 1 次"], [{"id":"start_return","label":"开始退货","style":"primary"},{"id":"keep_item","label":"决定留下","style":"secondary"}])
        return {"item_id":item["item_id"],"task_type":"return_window","title":schema["title"],"reason":schema["body"],"priority":"high","ui_schema":schema}

    def _resale_task(self, item: dict[str, Any]) -> dict[str, Any]:
        schema = self._schema("resale", "Switch 已闲置 128 天", "根据使用记录和当前二手价格，现在出售仍能保留约 56% 的购买价值。", ["连续 128 天未使用", "预计转售价 ¥1450", "包装与配件完整"], [{"id":"draft_listing","label":"生成转售资料","style":"primary"},{"id":"keep_item","label":"继续保留","style":"secondary"}])
        return {"item_id":item["item_id"],"task_type":"resale","title":schema["title"],"reason":schema["body"],"priority":"medium","ui_schema":schema}

    def _trip_task(self, items: dict[str, dict[str, Any]]) -> dict[str, Any]:
        """行程事件到达时，反查物品图谱生成出发卡。

        逐项检查真实物品档案并给出结论（需携带/应急可用/无需补货），
        证明"Agent 知道用户拥有什么"这件事本身能替用户做决定。
        演示叙事使用固定行程（明天深圳提案），日期与星期动态计算避免过期感。
        """
        trip_day = date.today() + timedelta(days=1)
        weekday = "一二三四五六日"[trip_day.weekday()]
        day_label = f"明天（{trip_day.month} 月 {trip_day.day} 日 {weekday}）"
        # 检查清单：每行对应图谱中的一件真实物品，读档案字段生成结论
        checklist: list[dict[str, str]] = []
        if "charger_home" in items:
            charger = items["charger_home"]
            checklist.append({"label": charger["name"], "verdict": "需携带", "state": "ok",
                              "detail": f"{charger['location']} · {charger['attributes'].get('上次使用', '常用')} · 已加入出发清单"})
        if "charger_office" in items:
            spare = items["charger_office"]
            checklist.append({"label": spare["name"], "verdict": "应急备用", "state": "info",
                              "detail": f"{spare['location']} · {spare['attributes'].get('备注', '出差常备')} · 忘带时顺路可取，不用回家"})
        if "serum" in items:
            serum = items["serum"]
            checklist.append({"label": serum["name"], "verdict": "无需补货", "state": "ok",
                              "detail": f"余量 {serum['attributes'].get('预计余量', '充足')} · 出差 3 天够用，预计 12 天后才需补充"})
        if "sunscreen" in items:
            sunscreen = items["sunscreen"]
            checklist.append({"label": sunscreen["name"], "verdict": "建议携带", "state": "warn",
                              "detail": f"{sunscreen['location']} · 新购 · 深圳紫外线强 · 已加入出发清单"})
        context_facts = [f"行程：{day_label} 10:00 · 深圳南山 · 客户提案",
                         "深圳 26–32℃ · 午后有阵雨", f"已检查物品图谱 {len(items)} 件，命中 {len(checklist)} 项关联"]
        actions = [{"id": "gen_checklist", "label": "生成出差清单", "style": "primary"},
                   {"id": "remind_later", "label": "出发前再提醒", "style": "secondary"}]
        title = "出差深圳 · 物品就绪检查"
        body = f"收到行程：{day_label} 10:00 客户提案。Agent 已按目的地天气与行程时长检查物品图谱，结论如下。"
        schema = self._schema("trip", title, body, context_facts, actions, component="departure_card")
        schema["checklist"] = checklist
        # 行程任务挂在图谱中一件真实物品下（car 常驻种子），避免悬挂记录
        anchor = items["car"]["item_id"] if "car" in items else items[list(items)[0]]["item_id"]
        self.store.add_event("context", "收到行程", f"{day_label} · 深圳南山 · 客户提案")
        self.store.add_event("planner", "为行程检查图谱", f"检查 {len(items)} 件物品，命中 {len(checklist)} 项关联")
        return {"item_id": anchor, "task_type": "trip_prep", "title": title, "reason": body,
                "priority": "high", "ui_schema": schema}

    @staticmethod
    def _result_message(task_type: str, action_id: str) -> str:
        messages = {("replenish","add_to_plan"):"已加入出行前补货计划", ("maintenance","schedule"):"已安排周末清洁", ("price_protection","claim"):"保价申请已模拟提交",
                    ("trip_prep","gen_checklist"):"出差清单已生成：充电器 ×1、防晒霜已加入，备用充电器已标记应急位", ("trip_prep","remind_later"):"已设为出发前 1 小时提醒",
                    ("source_review","confirm_discovery"):"便携阅读灯已确认并进入长期物品记忆", ("source_review","dismiss_discovery"):"已忽略该候选，不会写入物品仓",
                    ("return_window","start_return"):"退货材料已生成，并模拟预约上门取件", ("return_window","keep_item"):"已确认保留，不再提醒本次退货窗口",
                    ("resale","draft_listing"):"已生成标题、描述、成色与建议售价", ("resale","keep_item"):"已继续保留，90 天后再评估使用情况"}
        return messages.get((task_type, action_id), "已按你的选择更新任务")
