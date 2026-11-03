const tasksEl = document.querySelector("#tasks");
const form = document.querySelector("#task-form");
const message = document.querySelector("#form-message");

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.error || `HTTP ${response.status}`);
  }
  return response.status === 204 ? null : response.json();
}

async function loadTasks() {
  try {
    const tasks = await api("/api/tasks");
    if (!tasks.length) {
      tasksEl.innerHTML = '<p class="muted">还没有任务，创建第一条试试。</p>';
      return;
    }
    tasksEl.replaceChildren();
    for (const task of tasks) {
      const row = document.createElement("article");
      row.className = "task";
      const info = document.createElement("div");
      const title = document.createElement("h3");
      title.textContent = `#${task.id} ${task.title}`;
      const desc = document.createElement("p");
      desc.textContent = task.description || "无描述";
      info.append(title, desc);

      const actions = document.createElement("div");
      actions.className = "actions";
      const select = document.createElement("select");
      for (const [value, label] of [["todo","待处理"],["doing","进行中"],["done","已完成"]]) {
        const option = document.createElement("option");
        option.value = value; option.textContent = label;
        option.selected = task.status === value;
        select.append(option);
      }
      select.addEventListener("change", async () => {
        try { await api(`/api/tasks/${task.id}`, { method:"PATCH", body:JSON.stringify({status:select.value}) }); await loadTasks(); }
        catch (e) { alert(e.message); }
      });
      const del = document.createElement("button");
      del.className = "delete"; del.textContent = "删除";
      del.addEventListener("click", async () => {
        if (!confirm(`确定删除任务 #${task.id}？`)) return;
        try { await api(`/api/tasks/${task.id}`, {method:"DELETE"}); await loadTasks(); }
        catch (e) { alert(e.message); }
      });
      actions.append(select, del);
      row.append(info, actions);
      tasksEl.append(row);
    }
  } catch (e) {
    tasksEl.textContent = `加载失败：${e.message}`;
  }
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const title = document.querySelector("#title").value.trim();
  const description = document.querySelector("#description").value.trim();
  try {
    await api("/api/tasks", { method:"POST", body:JSON.stringify({title, description}) });
    form.reset();
    message.textContent = "创建成功";
    await loadTasks();
  } catch (e) { message.textContent = `创建失败：${e.message}`; }
});

document.querySelector("#refresh").addEventListener("click", loadTasks);
loadTasks();
