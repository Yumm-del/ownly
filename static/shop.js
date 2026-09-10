const pulse = document.querySelector("#ownlyPulse");
const sheet = document.querySelector("#ownlySheet");
const toast = document.querySelector("#shopToast");
let activePlan = null;

async function post(path, payload) {
  const response = await fetch(path, {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify(payload)});
  if (!response.ok) throw new Error("Ownly 暂时无法检查这件商品");
  return response.json();
}

function showToast(message) {
  toast.textContent = message;
  toast.classList.add("show");
}

function renderDecision(state) {
  activePlan = state.tasks.find((task) => task.task_type === "purchase_decision");
  if (!activePlan) return;
  const schema = activePlan.ui_schema;
  document.querySelector("#sheetTitle").textContent = schema.title;
  document.querySelector("#sheetBody").textContent = schema.body;
  document.querySelector("#sheetFacts").innerHTML = schema.facts.map((fact) => `<span>${fact}</span>`).join("");
  document.querySelector("#sheetMatches").innerHTML = schema.comparisons.map((item) => `<li><div><strong>${item.label}</strong><small>${item.detail}</small></div><b>${item.verdict}</b></li>`).join("");
  document.querySelector("#sheetActions").innerHTML = schema.actions.map((action) => `<button data-action="${action.id}" class="${action.style}">${action.label}</button>`).join("");
  pulse.hidden = true;
  sheet.hidden = false;
}

async function checkCurrentProduct() {
  try {
    const state = await post("/api/intent", {text:"我想买一个 65W 充电器，值得买吗", source:"购物页面上下文"});
    renderDecision(state);
  } catch (error) {
    pulse.querySelector("span").textContent = error.message;
  }
}

sheet.addEventListener("click", async (event) => {
  const button = event.target.closest("button[data-action]");
  if (!button || !activePlan) return;
  await post("/api/execute", {task_id:activePlan.task_id, action_id:button.dataset.action});
  sheet.hidden = true;
  showToast(button.dataset.action === "skip_purchase" ? "已避免一次重复购买 · 节省 ¥169" : "已记住：这次购买有额外需求");
});

document.querySelector("#buyButton").addEventListener("click", () => showToast("Ownly 建议先处理上方购买检查"));
setTimeout(checkCurrentProduct, 650);
