for (const href of ["/warehouse.css", "/agent-ui.css", "/category-ui.css", "/item-detail.css", "/journey-ui.css", "/resale-ui.css", "/value-ui.css", "/workbench-ui.css", "/tour-ui.css"]) {
  const link = document.createElement("link");
  link.rel = "stylesheet";
  link.href = href;
  document.head.appendChild(link);
}

document.body.insertAdjacentHTML("beforeend", `
  <dialog id="categoryDialog" class="add-dialog category-dialog">
    <div class="catalog-head">
      <div><p class="eyebrow">CATEGORY MAP</p><h2>全部品类</h2><p>每个品类都有自己的生命周期规则。</p></div>
      <button class="icon-button" type="button" data-close-catalog aria-label="关闭品类">×</button>
    </div>
    <div id="categoryCatalog" class="category-catalog"></div>
  </dialog>`);

document.body.insertAdjacentHTML("beforeend", `
  <dialog id="itemDialog" class="add-dialog item-dialog">
    <article id="itemDetail"></article>
  </dialog>`);

document.body.insertAdjacentHTML("beforeend", `
  <dialog id="sceneDialog" class="add-dialog scene-dialog">
    <article>
      <header class="dialog-head"><div><p class="eyebrow">SPATIAL CAPTURE</p><h2>扫描一个空间</h2></div><button class="icon-button" type="button" data-close-scene aria-label="关闭空间扫描">×</button></header>
      <div id="sceneCaptureStep">
        <p class="dialog-copy">拍下房间、柜子或桌面。Ownly 会一次识别多件物品、检查重复，并只让你确认不确定的结果。</p>
        <label class="scene-camera"><input id="scenePhoto" type="file" accept="image/*" capture="environment"><span>◎</span><strong>拍照或选择照片</strong><small id="sceneFileName">照片仅用于本次识别</small></label>
        <label class="scene-location">这个空间是<input id="sceneLocation" value="客厅" aria-label="空间名称"></label>
        <button id="analyzeScene" class="primary-button" type="button">让 Agent 识别物品</button>
      </div>
      <div id="sceneReviewStep" hidden><div class="scene-summary" id="sceneSummary"></div><div id="sceneCandidates" class="scene-candidates"></div><button id="importScene" class="primary-button" type="button">确认并加入物品仓</button><p class="privacy-note">重复物品不会再次收录；低置信度候选默认不勾选。</p></div>
    </article>
  </dialog>`);

document.body.insertAdjacentHTML("beforeend", `
  <dialog id="valueReportDialog" class="add-dialog value-report-dialog">
    <article>
      <header><div><p class="eyebrow">MONTHLY VALUE REPORT</p><h2 id="reportMonth">本月价值账单</h2></div><button id="closeValueReport" class="icon-button" type="button" aria-label="关闭价值账单">×</button></header>
      <p class="report-lead"><strong id="reportSecured">¥0</strong><span>已经到账或明确避免的支出</span></p>
      <div id="reportTotals" class="report-totals"></div>
      <section><h3>每一笔都有依据</h3><ol id="reportEvents" class="report-events"></ol></section>
      <p class="privacy-note">数据保存在本地。处理中和潜在价值不会计入“已经守住”。</p>
    </article>
  </dialog>`);

document.querySelector(".header-actions").insertAdjacentHTML("afterbegin", `<button id="policyButton" class="icon-button" type="button" aria-label="打开授权策略中心">◎</button>`);
// 评委会先看到这个按钮：不用摸索，直接看完整条主线
document.querySelector(".brief-actions").insertAdjacentHTML("afterbegin", `<button id="tourButton" class="tour-button" type="button">▶ 40 秒看完整条主线</button>`);
document.querySelector("#taskReason").insertAdjacentHTML("afterend", `<details id="agentWorkbench" class="agent-workbench"><summary><span>查看 Agent 为什么这样做</span><b id="traceLevel">L0</b></summary><div id="traceContent"></div></details>`);
document.body.insertAdjacentHTML("beforeend", `
  <dialog id="policyDialog" class="add-dialog policy-dialog">
    <article><header><div><p class="eyebrow">AGENT AUTONOMY</p><h2>授权策略中心</h2></div><button id="closePolicy" class="icon-button" type="button" aria-label="关闭授权策略">×</button></header>
    <p class="dialog-copy">让 Ownly 记住你的边界。切换模式不会取消发布、支付和所有权转移的确认。</p>
    <div id="modeOptions" class="mode-options"></div><section><h3>逐项策略</h3><div id="policyList" class="policy-list"></div></section></article>
  </dialog>`);

const $ = (selector) => document.querySelector(selector);
const elements = {
  total: $("#totalCount"), categories: $("#categoryCount"), attention: $("#attentionCount"),
  valueCreated: $("#valueCreated"), returnCount: $("#returnCount"), idleCount: $("#idleCount"),
  nav: $("#categoryNav"), grid: $("#itemGrid"), title: $("#listTitle"), visible: $("#visibleCount"),
  dialog: $("#addDialog"), form: $("#addForm"), categoryInput: $("#categoryInput"),
  intentForm: $("#intentForm"), intent: $("#intentInput"), opportunity: $("#opportunityCard"),
  taskTitle: $("#opportunityMessage"), taskReason: $("#taskReason"), taskFacts: $("#taskFacts"),
  taskChecklist: $("#taskChecklist"),
  taskActions: $("#taskActions"), taskPager: $("#taskPager"), completion: $("#completionCard"),
  claim: $("#claimDetail"), events: $("#eventList"), toast: $("#toast"),
  categoryDialog: $("#categoryDialog"), categoryCatalog: $("#categoryCatalog"),
  itemDialog: $("#itemDialog"), itemDetail: $("#itemDetail"),
  resaleStudio: $("#resaleStudio"), draftStatus: $("#draftStatus"), draftTitle: $("#draftTitle"),
  draftDescription: $("#draftDescription"), draftCondition: $("#draftCondition"), draftPrice: $("#draftPrice"),
  draftPhotos: $("#draftPhotos"), draftActions: $("#draftActions"),
  draftChannels: $("#draftChannels"), connectorNotice: $("#connectorNotice"),
  handoffPanel: $("#handoffPanel"), handoffSummary: $("#handoffSummary"),
  valueReportDialog: $("#valueReportDialog"), reportMonth: $("#reportMonth"),
  reportSecured: $("#reportSecured"), reportTotals: $("#reportTotals"), reportEvents: $("#reportEvents"),
  agentWorkbench: $("#agentWorkbench"), traceLevel: $("#traceLevel"), traceContent: $("#traceContent"),
  policyDialog: $("#policyDialog"), modeOptions: $("#modeOptions"), policyList: $("#policyList"),
  sceneDialog: $("#sceneDialog"), sceneCaptureStep: $("#sceneCaptureStep"),
  sceneReviewStep: $("#sceneReviewStep"), sceneCandidates: $("#sceneCandidates"),
};
let state = null;
let activeCategory = "全部";
let activeTask = 0;
let scenePreview = null;

async function api(path, payload = {}) {
  const response = await fetch(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || "Agent 暂时无法完成任务");
  return data;
}

function toast(message) {
  elements.toast.textContent = message;
  elements.toast.classList.add("show");
  setTimeout(() => elements.toast.classList.remove("show"), 2200);
}

const money = (value) => value == null ? "持续更新" : `¥${new Intl.NumberFormat("zh-CN").format(value)}`;
const formatDate = (value) => value ? new Intl.DateTimeFormat("zh-CN", { year: "numeric", month: "long", day: "numeric" }).format(new Date(`${value}T00:00:00`)) : "尚未记录";

/** 把统一字段、品类专属属性和 Agent 任务组合成完整物品档案。 */
function openItemDetail(itemId) {
  const item = state.items.find((entry) => entry.item_id === itemId);
  if (!item) return;
  const relatedTasks = state.tasks.filter((task) => task.item_id === itemId);
  const attributes = Object.entries(item.attributes || {});
  const lifecycle = (state.lifecycle_events || []).filter((event) => event.item_id === itemId);
  elements.itemDetail.innerHTML = `
    <header class="item-detail-head">
      <div class="detail-symbol category-${item.category}">${item.icon}</div>
      <div><p>${item.category} · ${item.status}</p><h2>${item.name}</h2></div>
      <button class="icon-button" type="button" data-close-item aria-label="关闭物品详情">×</button>
    </header>
    <section class="detail-action"><p>OWNLY NEXT</p><h3>${item.next_action}</h3><span>${formatDate(item.next_action_date)}</span></section>
    <section class="detail-section"><h3>物品信息</h3><dl>
      <div><dt>品牌</dt><dd>${item.brand || "尚未识别"}</dd></div>
      <div><dt>位置</dt><dd>${item.location}</dd></div>
      <div><dt>收录来源</dt><dd>${item.source}</dd></div>
      <div><dt>获得日期</dt><dd>${formatDate(item.acquired_at)}</dd></div>
      <div><dt>购买价格</dt><dd>${money(item.purchase_price)}</dd></div>
      <div><dt>当前价值</dt><dd>${money(item.current_value)}</dd></div>
    </dl></section>
    <section class="detail-section"><h3>${item.category}专属信息</h3><dl>${attributes.length ? attributes.map(([key, value]) => `<div><dt>${key}</dt><dd>${value}</dd></div>`).join("") : "<div><dt>状态</dt><dd>等待 Agent 持续补全</dd></div>"}</dl></section>
    <section class="detail-section"><h3>Agent 任务</h3>${relatedTasks.length ? relatedTasks.map((task) => `<div class="related-task"><i></i><span><strong>${task.title}</strong><small>${task.reason}</small></span></div>`).join("") : "<p class=empty-detail>现在没有需要你处理的事情。</p>"}</section>
    <section class="detail-section"><h3>完整生命周期</h3><ol class="lifecycle-list">${lifecycle.length ? lifecycle.map((event) => `<li><time>${event.occurred_at}</time><i></i><div><strong>${event.title}</strong><small>${event.detail}</small></div></li>`).join("") : "<li><div><strong>等待第一个生命周期事件</strong></div></li>"}</ol></section>
    <footer class="detail-foot">物品 ID · ${item.item_id}</footer>`;
  elements.itemDialog.showModal();
}

/** Agent 决定卡片内容与动作，客户端只渲染受限 schema。 */
function renderTask() {
  const tasks = state.tasks || [];
  if (!tasks.length) { elements.opportunity.hidden = true; return; }
  activeTask = Math.min(activeTask, tasks.length - 1);
  const task = tasks[activeTask];
  const schema = task.ui_schema;
  const paused = task.attention_state === "paused";
  elements.opportunity.hidden = false;
  elements.opportunity.dataset.tone = schema.tone;
  elements.taskTitle.textContent = schema.title;
  elements.taskReason.textContent = schema.body;
  const sections = schema.sections || [];
  elements.taskFacts.innerHTML = schema.facts.map((fact) => `<span>${fact}</span>`).join("") + sections.map((section) => `<div class="schema-section"><strong>${section.title}</strong><ul>${section.items.map((item) => `<li>${item}</li>`).join("")}</ul></div>`).join("");
  // 出发卡（departure_card）额外渲染逐项物品检查清单；其余卡片隐藏该区域
  const detailRows = schema.component === "departure_card" ? schema.checklist : (schema.discoveries || schema.comparisons || schema.checks);
  elements.taskChecklist.hidden = !(detailRows || []).length;
  elements.taskChecklist.innerHTML = (detailRows || []).map((row) =>
    `<li class="trip-row is-${row.state}"><span>${row.label}</span><b>${row.verdict}</b><small>${row.detail}</small></li>`).join("");
  elements.taskActions.innerHTML = paused
    ? `<p class="arbitration-pause">先处理“${task.paused_by_title}”，完成后这项行动会自动恢复。</p>`
    : schema.actions.map((action) => `<button type="button" data-task="${task.task_id}" data-action="${action.id}" class="${action.style === "primary" ? "primary-button light" : "secondary-button"}">${action.label}</button>`).join("");
  elements.taskPager.innerHTML = tasks.map((_, index) => `<button type="button" data-index="${index}" class="${index === activeTask ? "active" : ""}" aria-label="查看任务 ${index + 1}"></button>`).join("");
  const trace = task.agent_trace;
  elements.agentWorkbench.hidden = !trace;
  if (trace) {
    elements.traceLevel.textContent = trace.autonomy_level;
    elements.traceContent.innerHTML = `<p class="trace-headline">${trace.headline}</p><p class="arbitration-note"><span>${trace.role}</span><strong>${trace.priority_reason}</strong>${trace.paused_by_title ? `<small>暂缓原因：${trace.paused_by_title} 的优先级更高</small>` : ""}</p><div class="trace-columns"><section><small>支持证据</small><ul>${trace.evidence.map((row) => `<li>${row}</li>`).join("")}</ul></section><section><small>仍需注意</small><ul>${trace.counterevidence.map((row) => `<li>${row}</li>`).join("")}</ul></section></div>${trace.matched_policy ? `<p class="matched-policy"><span>命中长期策略</span><strong>${trace.matched_policy.name}</strong><small>${trace.matched_policy.behavior === "prepare_only" ? "允许自动准备，提交前仍需确认" : "涉及外部影响时始终确认"}</small></p>` : ""}<ol class="agent-steps">${trace.steps.map((step) => `<li class="is-${step.status}"><i></i><div><strong>${step.phase}</strong><small>${step.detail}</small></div></li>`).join("")}</ol>`;
  }
}

function renderCatalog() {
  const counts = Object.fromEntries(state.items.map((item) => item.category).map((category) => [category, state.items.filter((item) => item.category === category).length]));
  const groups = [...new Set(state.category_catalog.map((entry) => entry.group))];
  elements.categoryCatalog.innerHTML = groups.map((group) => `<section><h3>${group}</h3><div>${state.category_catalog.filter((entry) => entry.group === group).map((entry) => `<button type="button" data-catalog-category="${entry.name}"><i>${entry.icon}</i><span><strong>${entry.name}</strong><small>${entry.action}</small></span><b>${counts[entry.name] || 0}</b></button>`).join("")}</div></section>`).join("");
  elements.categoryInput.innerHTML = groups.map((group) => `<optgroup label="${group}">${state.category_catalog.filter((entry) => entry.group === group).map((entry) => `<option>${entry.name}</option>`).join("")}</optgroup>`).join("");
}

function renderDraft() {
  const draft = (state.resale_drafts || [])[0];
  elements.resaleStudio.hidden = !draft;
  if (!draft) return;
  const statusLabels = {draft:"等待选择渠道",channel_selected:"等待授权",authorized:"可以提交",published_demo:"Demo 回执已返回",sold:"已售出"};
  elements.draftStatus.textContent = statusLabels[draft.status] || draft.status;
  elements.draftTitle.textContent = draft.title;
  elements.draftDescription.textContent = draft.description;
  elements.draftCondition.textContent = draft.condition;
  elements.draftPrice.textContent = money(draft.price);
  elements.draftPhotos.innerHTML = draft.photos.map((photo) => `<li>${photo}</li>`).join("");
  elements.draftChannels.innerHTML = draft.channels.map((channel) => `<button type="button" class="channel-card ${draft.selected_channel === channel.id ? "selected" : ""}" data-channel-id="${channel.id}" data-draft="${draft.draft_id}"><span><strong>${channel.name}</strong>${channel.recommended ? "<em>Agent 推荐</em>" : ""}</span><b>${money(channel.price)}</b><small>${channel.arrival}</small><small>${channel.fee}</small><i>${channel.fit}</i></button>`).join("");
  const selectedChannel = draft.channels.find((channel) => channel.id === draft.selected_channel);
  elements.handoffPanel.hidden = !selectedChannel || draft.status === "sold";
  elements.handoffSummary.textContent = selectedChannel ? `${selectedChannel.name} · ${money(selectedChannel.price)} · 标题、描述、价格与 ${draft.photos.length} 张拍摄清单已整理` : "";
  if (draft.status === "draft") elements.draftActions.innerHTML = `<p>选择一个渠道，Agent 会准备对应发布流程。</p>`;
  else if (draft.status === "channel_selected") elements.draftActions.innerHTML = `<button class="primary-button" data-draft-action="authorize" data-draft="${draft.draft_id}">确认本次发布授权</button>`;
  else if (draft.status === "authorized") elements.draftActions.innerHTML = `<button class="primary-button" data-draft-action="publish" data-draft="${draft.draft_id}">提交到 Demo connector</button>`;
  else if (draft.status === "published_demo") elements.draftActions.innerHTML = `<button class="primary-button" data-draft-action="sold" data-draft="${draft.draft_id}">模拟收到售出回执并归档</button>`;
  else elements.draftActions.innerHTML = `<p>生命周期已完成，历史记录仍然保留。</p>`;
  elements.connectorNotice.textContent = draft.status === "published_demo" ? `Demo 回执：${draft.external_reference}。当前没有真实发布到第三方平台。` : "原型使用 Demo connector；真实发布需获得平台准入并由用户授权账号。";
}

function renderValueReport() {
  const report = state.value_report;
  const [year, month] = report.month.split("-");
  const labels = {realized:"已经到账",avoided:"避免支出",pending:"处理中",potential:"潜在机会"};
  elements.reportMonth.textContent = `${year} 年 ${Number(month)} 月价值账单`;
  elements.reportSecured.textContent = money(report.secured);
  elements.reportTotals.innerHTML = ["realized","avoided","pending","potential"].map((kind) => `<div class="is-${kind}"><span>${labels[kind]}</span><strong>${money(report[kind])}</strong></div>`).join("");
  elements.reportEvents.innerHTML = report.events.length ? report.events.map((entry) => `<li><i class="is-${entry.value_kind}"></i><div><strong>${entry.title}</strong><small>${entry.detail}</small></div><span><b>${money(entry.amount)}</b><small>${labels[entry.value_kind]}</small></span></li>`).join("") : `<li class="empty-report">完成一次保价、退货、购前检查或闲置出售后，价值会出现在这里。</li>`;
}

function renderPolicyCenter() {
  const center = state.policy_center;
  const modes = [
    {id:"cautious",label:"谨慎",description:"尽量先问我"},
    {id:"balanced",label:"平衡",description:"自动准备，执行确认"},
    {id:"managed",label:"托管",description:"按逐项策略主动工作"},
  ];
  elements.modeOptions.innerHTML = modes.map((mode) => `<button type="button" data-mode="${mode.id}" class="${center.mode.mode === mode.id ? "selected" : ""}"><strong>${mode.label}</strong><small>${mode.description}</small></button>`).join("");
  const behaviorLabels = {prepare_only:"只自动准备",always_confirm:"始终需要确认"};
  elements.policyList.innerHTML = center.policies.map((policy) => `<label><span><strong>${policy.name}</strong><small>${behaviorLabels[policy.behavior]}${policy.condition.max_amount ? ` · ¥${policy.condition.max_amount}以内` : ""}</small></span><input type="checkbox" data-policy-id="${policy.policy_id}" ${policy.enabled ? "checked" : ""}></label>`).join("");
}

function render(nextState) {
  state = nextState;
  elements.total.textContent = state.summary.total;
  elements.categories.textContent = state.summary.categories;
  elements.attention.textContent = state.summary.attention;
  elements.valueCreated.textContent = money(state.aftercare.value_created);
  elements.returnCount.textContent = state.aftercare.open_returns;
  elements.idleCount.textContent = state.aftercare.idle_items;
  const usedCategories = [...new Set(state.items.map((item) => item.category))];
  elements.nav.innerHTML = ["全部", ...usedCategories].map((category) => `<button class="category-chip ${category === activeCategory ? "active" : ""}" data-category="${category}">${category}</button>`).join("") + `<button class="category-chip catalog-trigger" data-open-catalog>＋ 全部品类</button>`;
  const items = activeCategory === "全部" ? state.items : state.items.filter((item) => item.category === activeCategory);
  elements.title.textContent = activeCategory === "全部" ? "Ownly 记得的物品" : activeCategory;
  elements.visible.textContent = `${items.length} 件`;
  elements.grid.innerHTML = items.map((item) => `<button type="button" class="inventory-card" data-item-id="${item.item_id}" aria-label="查看 ${item.name} 的完整信息"><div class="inventory-icon category-${item.category}">${item.icon}</div><div class="inventory-main"><div class="item-meta"><span>${item.category}</span><span>${item.location}</span></div><h3>${item.name}</h3><p>${item.brand || item.source} · ${money(item.current_value)}</p><div class="next-action"><i></i><span>${item.next_action}</span></div></div><span class="card-arrow">›</span></button>`).join("");
  elements.events.innerHTML = state.events.map((event) => `<li><strong>${event.title}</strong>${event.detail}</li>`).join("");
  elements.completion.hidden = true;
  renderCatalog();
  renderTask();
  renderDraft();
  renderValueReport();
  renderPolicyCenter();
}

elements.nav.addEventListener("click", (event) => {
  if (event.target.closest("[data-open-catalog]")) { elements.categoryDialog.showModal(); return; }
  const button = event.target.closest("button[data-category]");
  if (!button) return;
  activeCategory = button.dataset.category;
  render(state);
});
elements.grid.addEventListener("click", (event) => {
  const card = event.target.closest("button[data-item-id]");
  if (card) openItemDetail(card.dataset.itemId);
});
elements.itemDialog.addEventListener("click", (event) => {
  if (event.target.closest("[data-close-item]")) elements.itemDialog.close();
});
elements.categoryCatalog.addEventListener("click", (event) => {
  const button = event.target.closest("button[data-catalog-category]");
  if (!button) return;
  activeCategory = button.dataset.catalogCategory;
  elements.categoryDialog.close();
  render(state);
});
$("[data-close-catalog]").addEventListener("click", () => elements.categoryDialog.close());
$("#valueReportButton").addEventListener("click", () => elements.valueReportDialog.showModal());
$("#closeValueReport").addEventListener("click", () => elements.valueReportDialog.close());
$("#policyButton").addEventListener("click", () => elements.policyDialog.showModal());
$("#closePolicy").addEventListener("click", () => elements.policyDialog.close());
elements.modeOptions.addEventListener("click", async (event) => {
  const button = event.target.closest("button[data-mode]");
  if (!button) return;
  render(await api("/api/policy/mode", {mode:button.dataset.mode}));
  toast(`已切换为${button.querySelector("strong").textContent}模式`);
});
elements.policyList.addEventListener("change", async (event) => {
  const input = event.target.closest("input[data-policy-id]");
  if (!input) return;
  render(await api("/api/policy/toggle", {policy_id:input.dataset.policyId, enabled:input.checked}));
  toast(input.checked ? "策略已启用" : "策略已停用");
});
elements.intentForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!elements.intent.value.trim()) return;
  toast("Agent 正在理解并建立物品身份…");
  const next = await api("/api/intent", { text: elements.intent.value, source: "自然语言" });
  elements.intent.value = "";
  activeCategory = "全部";
  render(next);
  toast(next.intent_kind === "plan" ? "已生成跨物品行动方案" : "已进入长期物品记忆");
});
$("#addButton").addEventListener("click", () => {
  scenePreview = null;
  elements.sceneCaptureStep.hidden = false;
  elements.sceneReviewStep.hidden = true;
  elements.sceneDialog.showModal();
});
$("[data-close-scene]").addEventListener("click", () => elements.sceneDialog.close());
$("#scenePhoto").addEventListener("change", (event) => {
  $("#sceneFileName").textContent = event.target.files[0]?.name || "照片仅用于本次识别";
});
$("#analyzeScene").addEventListener("click", async () => {
  toast("Vision Agent 正在识别、分类并检查重复…");
  scenePreview = await api("/api/scene/preview", {location:$("#sceneLocation").value});
  const summary = scenePreview.summary;
  $("#sceneSummary").innerHTML = `<strong>识别 ${summary.detected} 件</strong><span>${summary.new} 件新物品 · ${summary.duplicate} 件已存在 · ${summary.needs_review} 件待判断</span>`;
  elements.sceneCandidates.innerHTML = scenePreview.candidates.map((item) => `<label class="scene-candidate ${item.duplicate ? "is-duplicate" : ""}"><input type="checkbox" value="${item.candidate_id}" ${item.selected ? "checked" : ""} ${item.duplicate ? "disabled" : ""}><i class="category-${item.category}">${state.category_catalog.find((entry) => entry.name === item.category)?.icon || "●"}</i><span><strong>${item.name}</strong><small>${item.category} · ${item.confidence.toLocaleString("zh-CN", {style:"percent"})} 置信度</small></span><b>${item.duplicate ? "已在仓内" : item.confidence < .8 ? "请确认" : "已识别"}</b></label>`).join("");
  elements.sceneCaptureStep.hidden = true;
  elements.sceneReviewStep.hidden = false;
});
$("#importScene").addEventListener("click", async () => {
  const candidateIds = [...elements.sceneCandidates.querySelectorAll("input:checked")].map((input) => input.value);
  const next = await api("/api/scene/import", {location:scenePreview.location, candidate_ids:candidateIds});
  render(next);
  elements.sceneDialog.close();
  toast(`已将 ${next.scene_import.imported} 件物品加入 ${next.scene_import.location}`);
});
// 手动逐件收录仍保留为次级入口，便于补充视觉无法识别的物品。
$("#addButton").addEventListener("contextmenu", (event) => { event.preventDefault(); elements.dialog.showModal(); });
$("#closeDialog").addEventListener("click", () => elements.dialog.close());
elements.form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = new FormData(elements.form);
  render(await api("/api/capture", { name: form.get("name"), category: form.get("category"), source: form.get("source") }));
  elements.dialog.close();
  elements.form.reset();
  toast("已实时加入物品仓");
});
$("#scanButton").addEventListener("click", async () => {
  toast("Agent 正在结合行程、意图和物品状态…");
  const result = await api("/api/scan");
  activeTask = 0;
  render(result.state);
  setTimeout(() => elements.opportunity.scrollIntoView({ behavior: "smooth", block: "center" }), 100);
});
$("#discoverButton").addEventListener("click", async () => {
  toast("Agent 正在核对订单、邮件与相册…");
  activeTask = 0;
  const next = await api("/api/discover");
  render(next);
  setTimeout(() => elements.opportunity.scrollIntoView({ behavior: "smooth", block: "center" }), 100);
  toast(next.discovery_status === "no_change" ? "同步完成，没有发现新的物品" : "自动收录完成，只留下 1 件待确认");
});
elements.taskActions.addEventListener("click", async (event) => {
  const button = event.target.closest("button[data-action]");
  if (!button) return;
  render(await api("/api/execute", { task_id: button.dataset.task, action_id: button.dataset.action }));
  elements.claim.textContent = "任务结果已写入长期记忆，并同步到 Watch。";
  elements.completion.hidden = false;
});
elements.taskPager.addEventListener("click", (event) => {
  const button = event.target.closest("button[data-index]");
  if (!button) return;
  activeTask = Number(button.dataset.index);
  renderTask();
});
elements.draftActions.addEventListener("click", async (event) => {
  const button = event.target.closest("button[data-draft-action]");
  if (!button) return;
  const paths = {authorize:"/api/resale/authorize", publish:"/api/resale/publish", sold:"/api/resale/sold"};
  const path = paths[button.dataset.draftAction];
  render(await api(path, {draft_id:button.dataset.draft}));
  const messages = {authorize:"已记录本次 Demo 授权", publish:"Demo connector 已返回模拟发布回执", sold:"已售出并退出活跃物品仓"};
  toast(messages[button.dataset.draftAction]);
});
elements.draftChannels.addEventListener("click", async (event) => {
  const button = event.target.closest("button[data-channel-id]");
  if (!button) return;
  render(await api("/api/resale/select-channel", {draft_id:button.dataset.draft, channel_id:button.dataset.channelId}));
  toast(`已选择${button.querySelector("strong").textContent}，等待你的授权`);
});
/** 把结构化草稿转换成任何二手平台都能使用的文本素材包。 */
function buildHandoffText(draft) {
  const channel = draft.channels.find((entry) => entry.id === draft.selected_channel);
  return [
    `【标题】${draft.title}`,
    `【价格】${money(channel?.price ?? draft.price)}`,
    `【成色】${draft.condition}`,
    `【描述】${draft.description}`,
    `【待拍照片】${draft.photos.join("、")}`,
    "由 Ownly 根据物品档案生成，请在发布前确认实际成色。",
  ].join("\n\n");
}
elements.handoffPanel.addEventListener("click", async (event) => {
  const button = event.target.closest("button[data-handoff]");
  if (!button) return;
  const draft = (state.resale_drafts || [])[0];
  if (!draft?.selected_channel) return;
  const text = buildHandoffText(draft);
  if (button.dataset.handoff === "share" && navigator.share) {
    await navigator.share({title:draft.title, text});
    toast("已打开手机分享面板");
    return;
  }
  await navigator.clipboard.writeText(text);
  toast(button.dataset.handoff === "share" ? "当前设备不支持分享，已改为复制全部素材" : "标题、描述、价格和拍摄清单已复制");
});
$("#resetButton").addEventListener("click", async () => { activeCategory = "全部"; activeTask = 0; render(await api("/api/reset")); toast("演示仓已重置"); });

/* ==================== 评委导览：40 秒走完整条主线 ====================
   目的：第一次打开的人不知道该点哪里，很容易错过产品最关键的部分。
   这条导览按真实接口把主线走一遍，底部讲解条告诉评委"现在该看什么"、
   "它为什么重要"。
   原理：每一步 = 一次真实 API 调用（或一次真实界面操作）+ 一句讲解。
   这里没有专为演示准备的假路径——导览走的就是用户自己走的同一条路，
   所以它同时也是录 1 分钟视频时的分镜脚本。 */

const TOUR_STEPS = [
  {
    hold: 4500,
    text: "此刻没有需要你决定的事。Ownly 保持安静——安静是它的默认状态，而不是一屏待办清单。",
    run: async () => {
      activeCategory = "全部";
      activeTask = 0;
      render(await api("/api/reset"));
      window.scrollTo({ top: 0 });
    },
  },
  {
    hold: 4600,
    text: "环境变化：你正在离开家，而深圳行程 3 小时 40 分后出发。",
    run: async () => {
      activeTask = 0;
      render(await api("/api/context-event"));
    },
  },
  {
    hold: 8500,
    text: "不用打开 App，行动自己到达：家中那支 65W 充电器还没进包，公司工位还有一支备用——忘带时顺路可取，不必回家。",
    run: () => focusTourCard(),
  },
  {
    hold: 7500,
    text: "每一步都能追问：支持证据、反证，以及它命中了哪一条长期策略。",
    run: () => {
      elements.agentWorkbench.open = true;
      elements.agentWorkbench.scrollIntoView({ behavior: "smooth", block: "center" });
    },
  },
  {
    hold: 6000,
    text: "你只需要做决定，执行交给它：一键生成出发清单，并同步到手表。",
    run: async () => {
      elements.agentWorkbench.open = false;
      const task = (state.tasks || [])[0];
      if (!task) return;
      const actions = task.ui_schema.actions || [];
      const primary = actions.find((action) => action.style === "primary") || actions[0];
      if (!primary) return;
      render(await api("/api/execute", { task_id: task.task_id, action_id: primary.id }));
      elements.claim.textContent = "任务结果已写入长期记忆，并同步到 Watch。";
      elements.completion.hidden = false;
    },
  },
  {
    hold: 6500,
    text: () => `本月已经守住 ${money(state.aftercare.value_created)}。每一笔都有依据，处理中的金额绝不混进"已经守住"。`,
    run: () => elements.valueReportDialog.showModal(),
  },
  {
    hold: 6000,
    text: "这就是所有权层：你只管出发，物品自己就位。",
    run: () => {
      elements.valueReportDialog.close();
      window.scrollTo({ top: 0, behavior: "smooth" });
    },
  },
];

let tourRunning = false;
let tourTimers = [];
let tourWake = null;

/** 高亮当前被讲解的那张卡，让人知道该看哪里。 */
function focusTourCard() {
  elements.opportunity.classList.add("tour-focus");
  elements.opportunity.scrollIntoView({ behavior: "smooth", block: "center" });
}

/** 可被打断的等待：跳过导览时立刻唤醒，不留悬挂的定时器。 */
function tourSleep(milliseconds) {
  return new Promise((resolve) => {
    tourWake = resolve;
    tourTimers.push(setTimeout(() => { tourWake = null; resolve(); }, milliseconds));
  });
}

/** 懒创建导览的 DOM，只在第一次点击时插入页面。 */
function tourLayer() {
  let layer = document.querySelector("#tourLayer");
  if (layer) return layer;
  document.body.insertAdjacentHTML("beforeend", `
    <div id="tourLayer" class="tour-layer" hidden>
      <div class="tour-caption">
        <span class="tour-step" id="tourStep"></span>
        <p id="tourText"></p>
        <div class="tour-foot">
          <div class="tour-dots" id="tourDots"></div>
          <button class="tour-skip" id="tourSkip" type="button">跳过导览</button>
        </div>
      </div>
    </div>`);
  document.querySelector("#tourSkip").addEventListener("click", stopTour);
  return document.querySelector("#tourLayer");
}

async function runTour() {
  if (tourRunning) return;
  tourRunning = true;
  const layer = tourLayer();
  layer.hidden = false;
  elements.valueReportDialog.close();
  for (let index = 0; index < TOUR_STEPS.length; index += 1) {
    if (!tourRunning) return;
    const step = TOUR_STEPS[index];
    document.querySelector("#tourStep").textContent = `第 ${index + 1} / ${TOUR_STEPS.length} 步`;
    document.querySelector("#tourText").textContent = typeof step.text === "function" ? step.text() : step.text;
    document.querySelector("#tourDots").innerHTML = TOUR_STEPS
      .map((_, dot) => `<i class="${dot === index ? "is-active" : dot < index ? "is-done" : ""}"></i>`).join("");
    // 重放一次入场动画，让每一步的切换在视觉上看得出来
    const caption = layer.querySelector(".tour-caption");
    caption.style.animation = "none";
    void caption.offsetWidth;
    caption.style.animation = "";
    try {
      await step.run();
    } catch (error) {
      toast(error.message || "导览中断");
      break;
    }
    if (!tourRunning) return;
    await tourSleep(step.hold);
  }
  stopTour();
}

/** 结束或跳过导览：清掉定时器、高亮和展开状态，把界面还给用户。 */
function stopTour() {
  const wasRunning = tourRunning;
  tourRunning = false;
  tourTimers.forEach(clearTimeout);
  tourTimers = [];
  if (tourWake) { tourWake(); tourWake = null; }
  elements.opportunity.classList.remove("tour-focus");
  elements.agentWorkbench.open = false;
  const layer = document.querySelector("#tourLayer");
  if (layer) layer.hidden = true;
  if (wasRunning) toast("导览结束，现在可以自己探索了");
}

$("#tourButton").addEventListener("click", runTour);

fetch("/api/state").then((response) => response.json()).then((next) => {
  render(next);
  // 支持 ?tour=1 直接进入导览，方便把链接发给评委或用来录屏
  if (new URLSearchParams(location.search).get("tour") === "1") runTour();
}).catch(() => toast("无法连接 Ownly Agent"));
