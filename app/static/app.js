/* TaskFlow 前端逻辑: 纯原生 JS + fetch, 无构建依赖 */
const API = '/api/v1';
const TOKEN_KEY = 'taskflow_token';

function getToken() { return localStorage.getItem(TOKEN_KEY); }
function setToken(t) { localStorage.setItem(TOKEN_KEY, t); }
function clearToken() { localStorage.removeItem(TOKEN_KEY); }

async function request(method, path, body) {
  const headers = {};
  if (getToken()) headers['Authorization'] = `Bearer ${getToken()}`;
  if (body) headers['Content-Type'] = 'application/json';
  const resp = await fetch(API + path, { method, headers, body: body ? JSON.stringify(body) : undefined });
  if (resp.status === 401 && location.pathname !== '/static/login.html') {
    clearToken();
    location.href = '/static/login.html';
    throw new Error('未登录');
  }
  const data = resp.status === 204 ? null : await resp.json().catch(() => null);
  return { status: resp.status, data };
}

function showError(el, msg) { if (el) { el.textContent = msg; } }
function fmtDate(s) { return s || '无截止日期'; }
function statusLabel(s) { return { pending: '待办', in_progress: '进行中', done: '已完成' }[s] || s; }

/* ==================== 登录/注册 ==================== */
if (document.getElementById('form-login')) {
  const tabLogin = document.getElementById('tab-login');
  const tabRegister = document.getElementById('tab-register');
  const err = document.getElementById('auth-error');

  function switchTab(login) {
    tabLogin.classList.toggle('active', login);
    tabRegister.classList.toggle('active', !login);
    document.getElementById('form-login').style.display = login ? '' : 'none';
    document.getElementById('form-register').style.display = login ? 'none' : '';
    showError(err, '');
  }
  tabLogin.onclick = () => switchTab(true);
  tabRegister.onclick = () => switchTab(false);

  document.getElementById('login-submit').onclick = async () => {
    const username = document.getElementById('login-username').value.trim();
    const password = document.getElementById('login-password').value;
    if (!username || !password) { showError(err, '请输入用户名和密码'); return; }
    const { status, data } = await request('POST', '/auth/login', { username, password });
    if (status === 200) { setToken(data.access_token); location.href = '/static/index.html'; }
    else showError(err, (data && data.detail) || '登录失败');
  };

  document.getElementById('register-submit').onclick = async () => {
    const username = document.getElementById('register-username').value.trim();
    const password = document.getElementById('register-password').value;
    if (!username || !password) { showError(err, '请输入用户名和密码'); return; }
    const { status, data } = await request('POST', '/auth/register', { username, password });
    if (status === 201) {
      switchTab(true);                    // 先切回登录表单
      showError(err, '注册成功, 请登录');   // 再写提示 (switchTab 会清空提示区)
    } else showError(err, (data && data.detail) || '注册失败');
  };
}

/* ==================== 任务主页 ==================== */
if (document.getElementById('task-list')) {
  let currentFilter = '';
  let currentTasks = [];

  const $ = (t) => document.querySelector(`[data-testid="${t}"]`);

  async function loadUser() {
    const { status, data } = await request('GET', '/users/me');
    if (status === 200) $('current-username').textContent = `👤 ${data.username}`;
  }

  async function loadStats() {
    const mySeq = loadSeq;
    const { status, data } = await request('GET', '/stats/summary');
    if (status !== 200 || mySeq !== loadSeq) return;  // 过期统计响应直接丢弃
    $('stats-total').textContent = data.total;
    $('stats-pending').textContent = data.pending;
    $('stats-in_progress').textContent = data.in_progress;
    $('stats-done').textContent = data.done;
    $('stats-completion').textContent = `${Math.round(data.completion_rate * 100)}%`;
  }

  let loadSeq = 0;  // 请求序号: 快速切换筛选时丢弃过期响应, 防止旧数据覆盖新状态

  async function loadTasks() {
    const q = currentFilter ? `?status=${currentFilter}` : '';
    const mySeq = ++loadSeq;
    const { status, data } = await request('GET', `/tasks${q}`);
    if (status !== 200 || mySeq !== loadSeq) return;  // 过期响应直接丢弃
    currentTasks = data.items;
    renderTasks();
    loadStats();
  }

  function renderTasks() {
    const list = $('task-list');
    list.innerHTML = '';
    $('empty-tip').style.display = currentTasks.length ? 'none' : '';
    currentTasks.forEach((t) => {
      const item = document.createElement('div');
      item.className = 'task-item';
      item.dataset.testid = 'task-item';
      item.dataset.taskId = t.id;
      item.innerHTML = `
        <div class="task-main">
          <div class="task-title ${t.status === 'done' ? 'done' : ''}" data-testid="task-title">${escapeHtml(t.title)}</div>
          <div class="task-meta">
            <span class="badge ${t.priority}" data-testid="task-priority">${t.priority}</span>
            <span class="badge ${t.status}" data-testid="task-status">${statusLabel(t.status)}</span>
            <span data-testid="task-due">${fmtDate(t.due_date)}</span>
          </div>
        </div>
        <div class="task-actions">
          ${t.status === 'pending' ? `<button data-testid="task-start-btn" data-id="${t.id}">开始</button>` : ''}
          ${t.status !== 'done' ? `<button class="done-btn" data-testid="task-done-btn" data-id="${t.id}">完成</button>` : ''}
          <button data-testid="task-edit-btn" data-id="${t.id}">编辑</button>
          <button class="delete-btn" data-testid="task-delete-btn" data-id="${t.id}">删除</button>
        </div>`;
      list.appendChild(item);
    });
  }

  function escapeHtml(s) {
    return s.replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  }

  /* 事件委托: 列表按钮 */
  $('task-list').addEventListener('click', async (e) => {
    const btn = e.target.closest('button');
    if (!btn) return;
    const id = btn.dataset.id;
    const run = async (fn) => { await fn(); await loadTasks(); };

    if (btn.dataset.testid === 'task-start-btn') {
      await run(async () => request('PATCH', `/tasks/${id}/status`, { status: 'in_progress' }));
    } else if (btn.dataset.testid === 'task-done-btn') {
      await run(async () => request('PATCH', `/tasks/${id}/status`, { status: 'done' }));
    } else if (btn.dataset.testid === 'task-delete-btn') {
      if (confirm('确定删除该任务吗?')) await run(async () => request('DELETE', `/tasks/${id}`));
    } else if (btn.dataset.testid === 'task-edit-btn') {
      editTask(btn, id);
    }
  });

  function editTask(btn, id) {
    const item = btn.closest('[data-testid="task-item"]');
    const titleEl = item.querySelector('[data-testid="task-title"]');
    const oldTitle = currentTasks.find((t) => t.id === Number(id)).title;
    const row = document.createElement('div');
    row.className = 'task-edit-row';
    row.innerHTML = `
      <input data-testid="task-edit-input" value="${escapeHtml(oldTitle)}" maxlength="100">
      <button class="btn btn-primary" style="width:auto" data-testid="task-edit-save" data-id="${id}">保存</button>
      <button data-testid="task-edit-cancel">取消</button>`;
    titleEl.replaceWith(row);
    const input = row.querySelector('input');
    input.focus();
    input.setSelectionRange(oldTitle.length, oldTitle.length);

    row.querySelector('[data-testid="task-edit-save"]').onclick = async () => {
      const title = input.value.trim();
      if (!title) { alert('标题不能为空'); return; }
      await request('PATCH', `/tasks/${id}`, { title });
      await loadTasks();
    };
    row.querySelector('[data-testid="task-edit-cancel"]').onclick = () => loadTasks();
  }

  /* 筛选 tab */
  document.querySelectorAll('.filter-tabs button').forEach((btn) => {
    btn.onclick = () => {
      document.querySelectorAll('.filter-tabs button').forEach((b) => b.classList.remove('active'));
      btn.classList.add('active');
      currentFilter = btn.dataset.testid.replace('filter-', '');
      if (currentFilter === 'all') currentFilter = '';
      loadTasks();
    };
  });

  /* 新建任务 */
  $('task-add-btn').onclick = async () => {
    const title = $('task-title-input').value.trim();
    if (!title) { showError($('add-error'), '请输入任务标题'); return; }
    const body = {
      title,
      priority: $('task-priority-select').value,
      due_date: $('task-due-input').value || null,
    };
    // 提交即清空输入框: 若等请求返回再清空, 会覆盖用户已输入的下一任务内容
    $('task-title-input').value = '';
    $('task-due-input').value = '';
    const { status, data } = await request('POST', '/tasks', body);
    if (status === 201) {
      showError($('add-error'), '');
      await loadTasks();
    } else {
      $('task-title-input').value = title;  // 创建失败时恢复用户输入
      showError($('add-error'), (data && data.detail) || '创建失败');
    }
  };

  $('logout-btn').onclick = () => { clearToken(); location.href = '/static/login.html'; };

  /* 未登录直接访问主页时跳回登录页 */
  if (!getToken()) { location.href = '/static/login.html'; }
  else { loadUser(); loadStats(); loadTasks(); }
}
