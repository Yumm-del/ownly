# Ownly 原型架构

## 设计原则

Agent 是个人所有权图谱上的状态机与工具调度者，界面只是当前情境的投影。用户不为维护库存而打开应用；购买、出发、维护或流转机会出现时，Agent 才组织相关物品与服务，生成一次性的行动界面。

## 七个系统能力

| 能力 | 原型实现 | 后续替换点 |
| --- | --- | --- |
| perception | 接收手机拍摄的凭证，演示适配器返回结构化结果 | Vision model / Agent OS 多模态接口 |
| memory | SQLite 保存物品、事件、执行结果与可撤销的用户决策偏好 | 本地加密 / Agent OS 长期记忆 |
| planner | 跨品类规则扫描、旅行规划与购前替代品判断 | LLM planner + 用户策略 |
| tools | 演示日历与天气、规则查询、价格检查、模拟售后提交 | 商家、邮件、真实日历、天气与物流服务 |
| generative_ui | Agent 输出受限 schema，客户端生成证据与动作 | 更多安全组件协议 |
| proactivity | 后台扫描与离家环境事件主动生成任务 | 系统 geofence、后台任务与通知 |
| handoff | 手机与 Watch 页面共享任务和执行状态 | 实际设备 runtime |

## 状态流

```text
unseen
  -> observing
  -> owned
  -> monitoring
  -> opportunity_found
  -> awaiting_approval
  -> executing
  -> completed
```

## 技术边界

- `app.py`：标准库 HTTP 服务与多端 API。
- `agent_core.py`：意图理解、生命周期规划和 Dynamic UI schema。
- `storage.py`：SQLite 物品、事件与任务持久化。
- `memories` 表：保存会改变后续 planner 行为的结构化偏好，而不只是操作日志。
- `lifecycle_events` 表：保存订单、物流、签收、权益、使用、闲置和退出事件。
- `resale_drafts` 表：保存可发布的二手标题、描述、成色、价格、图片计划与发布状态。
- `context_tools.py`：日历与天气 adapter；演示数据可替换而不改变 planner 与界面协议。
- `static/`：Mobile-first PWA 与动态界面。
- `tests/`：验证状态转换、金额和期限计算。
- 所有外部能力均通过清晰的 adapter 边界进入，避免把模拟结果伪装成真实服务。
