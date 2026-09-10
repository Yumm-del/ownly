# 个人物品仓开源调研

调研日期：2026-09-04。Stars 会随时间变化。

## 自动发现补充调研

| 项目 | Stars | 最近更新 | License | 可借鉴部分 | 判断 |
| --- | ---: | --- | --- | --- | --- |
| [receipt-parser-legacy](https://github.com/ReceiptManager/receipt-parser-legacy) | 854 | 2024-08 | Apache-2.0 | OCR 后的模糊字段抽取 | 只输出商店、日期和金额，不是物品图谱 |
| [Nestarr](https://github.com/tokendad/Nestarr) | 95 | 2026-09 | MIT | 照片识别、位置层级、票据和保修字段 | 仍以手动 inventory CRUD 为核心 |
| [ExpensiveMail](https://github.com/svtrhub/expensivemail) | 1 | 2026-09 | MIT | 来源验证、规则/模型双解析、hash 去重 | 面向费用账本，不能直接替代物品仓 |

结论：Ownly 继续从零实现轻量 adapter 与 Agent 决策层，采用“来源证据 + 置信度分流 + 确定性去重”；高置信度物品自动入仓，低置信度结果才请求确认。

## 购前决策补充调研

- [googlarz/fashion-skill](https://github.com/googlarz/fashion-skill)：14 stars，2026-05 更新；仓库元数据未识别标准 License，README 自述 MIT。它验证了 wardrobe inventory、pre-purchase check 与 Buy/Skip 判断的价值，但仅覆盖穿搭，移动端依赖手工同步，也没有跨品类的系统级介入。
- 常见 home inventory 与 grocery 项目仍以“买完后登记”和购物清单为中心，没有找到成熟的通用“基于个人所有权图谱拦截重复购买”实现。

结论：Ownly 自建通用购前决策层，以充电器、耳机、防晒、家具和相机验证“购物意图 → 识别品类 → 检索替代品或发现缺口 → 动态建议 → 记录用户选择”的完整闭环。

### 商品页面内介入

- `fractal-nyc/alangarber-shopping-assistant`：0 stars，2025-03 更新，未声明 License；方向是浏览器内 AI shopping assistant，但成熟度不足。
- `BrianZhang2018/temu-price-comparison-extension`：2 stars，MIT，2025-12 更新；可参考“自动识别商品页并就地展示结果”，但决策依据仍是其他平台价格。

Ownly 借鉴页面上下文自动触发方式，区别在于它不推荐另一个商品，而是先查询用户已经拥有的物品。原型通过独立购物页面验证系统浮层，后续可替换成 Agent OS 屏幕理解或浏览器扩展。

## 主动环境服务补充调研

- `deliciafernandes/Checklst`：10 stars，2020-12 更新，未声明 License；以地图和用户预设地点任务为中心。
- `jaeger-2601/GeoAlarm`：5 stars，MIT，2022-05 更新；使用 Geofencing API 在进入或离开地点时触发预设闹钟。

两者都要求用户事先配置提醒。Ownly 的实现不保存固定闹钟，而是把“离家”作为环境事件，再联合日历行程、物品位置和历史状态即时生成动作。

| 项目 | Stars | 最近更新 | License | 可借鉴部分 | 不直接改造的原因 |
| --- | ---: | --- | --- | --- | --- |
| [Grocy](https://github.com/grocy/grocy) | 9.4k | 2026-09-03 | MIT | 耗材、保质期、扫码、补货、REST API | 核心是家庭 ERP 与手动库存流程 |
| [HomeBox](https://github.com/sysadminsmedia/homebox) | 7.1k | 2026-09-01 | AGPL-3.0 | 品类、位置、自定义字段、保修、维护 | 最接近个人物品仓，但交互仍是传统 CRUD |
| [Shelf](https://github.com/Shelf-nu/shelf.nu) | 3.0k | 2026-09-03 | AGPL-3.0 | 通用资产模型、QR、位置、审计与提醒 | 面向团队和设备管理，系统较重 |
| [LubeLogger](https://github.com/hargata/lubelog) | 2.8k | 2026-09-02 | MIT | 汽车里程、保养、费用时间线 | 仅覆盖汽车单一类别 |
| [Warracker](https://github.com/sassanix/Warracker) | 1.5k | 2026-08-31 | AGPL-3.0 | 凭证与保修期限 | 只覆盖售后权益 |

## 路线判断

- 直接使用：能快速获得完整库存能力，但作品会成为传统系统换皮，不符合 Agent 原生评审方向。
- 改造现有项目：HomeBox 数据模型最接近，但 AGPL 和现有架构会提高十天原型的改造成本。
- 从零实现轻量核心：当前推荐。借鉴成熟项目的数据字段与领域规则，独立验证自动收录、长期状态、主动行动和动态 UI。

## Ownly 的差异

现有项目要求用户先进入功能、选择表单并维护数据。Ownly 让物品从环境和服务中自动进入统一记忆，Agent 持续更新状态，只在需要决策时生成操作界面。

## Purchase aftercare 补充调研

- [Warracker](https://github.com/sassanix/Warracker)：约 1.48k stars，AGPL-3.0，2026-09-07 仍活跃；证明票据、保修和到期提醒有需求，但仍依赖用户维护。
- [changedetection.io](https://github.com/dgtlmoon/changedetection.io)：约 33.7k stars，Apache-2.0，2026-09 活跃；适合参考网页变化与价格监测，不具备个人所有权和退货状态。
- 暂未找到成熟的“个人使用信号 → 闲置识别 → 自动生成转售资料”通用开源产品。

建议继续独立实现统一 lifecycle，而不是拼接三个后台工具：同一个订单身份同时承载退货截止、价格变化、保修凭证、使用频率和退出方式。
