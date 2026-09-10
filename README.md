# Ownly

Ownly is a personal ownership agent that understands what a person owns, what they intend to do, and which objects should become available for the situation ahead.

The product is not an inventory manager or an after-sales assistant. Its ownership graph stays in the background while the Agent intervenes before purchases, departures, maintenance decisions, and ownership transfers. Return protection, price protection, warranty memory, duplicate-purchase checks, and resale are actions inside that broader ownership layer.

## 运行

项目仅依赖 Python 3 标准库：

```powershell
python app.py
```

然后访问 <http://127.0.0.1:8765>。用户可以表达购买、出发、寻找或处理物品的意图；Agent 也会结合物品状态主动生成当前值得处理的任务。系统级购物介入位于 <http://127.0.0.1:8765/shop>，环境服务位于 <http://127.0.0.1:8765/ambient>，Watch 授权交接位于 <http://127.0.0.1:8765/watch>。

Switch OLED 演示物品包含从订单、物流、签收、保价、使用、闲置到转售的持久化生命周期。在转售任务中点击“生成转售资料”后，会出现包含标题、描述、成色、价格和图片清单的真实草稿；确认发布并模拟售出后，物品退出活跃仓，历史事件继续保留。

运行测试：

```powershell
python -m unittest discover -s tests -v
```

## 原型边界

- 物品、生命周期事件和 Agent 任务保存在本地 SQLite 数据库。
- 用户对购前建议的反馈会成为结构化长期记忆，并改变下一次同类判断；用户也可以要求重新评估。
- 自然语言感知目前使用可解释规则；真实 Vision/LLM adapter 尚未接入。
- 日历、天气、商家价格变化和保价提交均为可重复验证的模拟工具，并在代码中明确标注 adapter 边界。
- Dynamic UI 由 Agent 输出的受限 schema 生成，未声明动作会被服务端拒绝。
- 后续可将相同接口替换为真实 Vision、商家服务和 Agent OS 能力。

产品命题见 [PRODUCT.md](PRODUCT.md)，系统边界见 [ARCHITECTURE.md](ARCHITECTURE.md)。
