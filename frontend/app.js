'use strict';
(() => {
  const state = { page: 'library', articles: [], searchArticles: [], tags: [], query: '', results: null, loading: false, importing: false, notice: '' };
  const root = document.getElementById('root');
  const fileInput = document.getElementById('import-files');
  let searchVersion = 0;
  const escapeHtml = (value) => String(value).replace(/[&<>"']/g, (char) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[char]);
  const paths = {
    book: '<path d="M4 3h6a3 3 0 0 1 3 3v15a4 4 0 0 0-4-2H4zM20 3h-4a3 3 0 0 0-3 3v15a4 4 0 0 1 4-2h3z"/>',
    grid: '<rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/>',
    search: '<circle cx="10" cy="10" r="7"/><path d="m15 15 6 6"/>',
    spark: '<path d="m12 3 3 6 6 3-6 3-3 6-3-6-6-3 6-3zM20 2v4M18 4h4"/>',
    upload: '<path d="M12 16V3m-5 5 5-5 5 5M4 16v5h16v-5"/>',
    close: '<path d="m6 6 12 12M6 18 18 6"/>',
    plus: '<path d="M12 4v16M4 12h16"/>',
    check: '<circle cx="12" cy="12" r="9"/><path d="m8 12 3 3 5-6"/>',
    info: '<circle cx="12" cy="12" r="9"/><path d="M12 11v6M12 7h.01"/>',
    loader: '<path d="M21 12a9 9 0 1 1-9-9"/>'
  };
  const icon = (name) => `<svg ${name === 'loader' ? 'class="spin"' : ''} viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${paths[name]}</svg>`;
  const button = (action, label, symbol, className = '', disabled = false) => `<button type="button" data-action="${action}" class="${className}" ${disabled ? 'disabled' : ''}>${icon(symbol)}${label}</button>`;
  const normalize = (articles) => articles.map((article) => ({ ...article, tags: JSON.parse(article.matched_tags) }));
  const grid = (items, message) => items.length ? `<div class="grid">${items.map((article) => `<article class="card" tabindex="0" role="button" data-article="${article.id}" aria-label="查看：${escapeHtml(article.title)}"><div class="card-cover"><span>${escapeHtml(article.title.slice(0, 18))}</span><div class="cover-line"></div></div><div class="card-body"><div class="card-meta"><span>${escapeHtml(new Date(article.created_at).toLocaleDateString('zh-CN'))}</span>${icon('check')}</div><h3>${escapeHtml(article.title)}</h3><p>${escapeHtml(article.content || '仅标题文章，点击查看详情。')}</p><div class="card-tags">${article.tags.slice(0, 2).map((tag) => `<span>${escapeHtml(tag)}</span>`).join('')}</div></div></article>`).join('')}</div>` : `<div class="empty">${escapeHtml(message)}</div>`;

  async function request(path, body) {
    let response;
    try {
      response = await fetch(path, body === undefined ? {} : { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify(body) });
    } catch (error) { throw new Error(`无法连接后端：${error.message}。请启动后端并通过 HTTP 地址打开页面。`); }
    const data = await response.json();
    if (!response.ok) throw new Error(data.error);
    return data;
  }
  // A single error-reporting wrapper for all asynchronous UI actions.
  const reportErrors = (action) => async (...args) => {
    try { await action(...args); }
    catch (error) { showNotice(error.message); }
  };
  function showNotice(message) {
    state.notice = message;
    document.getElementById('notice').textContent = message;
  }
  function render() {
    const isFilter = state.page === 'filter';
    const isSearch = state.page === 'search';
    const busy = state.loading || state.importing;
    root.innerHTML = `<div class="app"><aside><div class="brand"><div class="brand-mark">${icon('book')}</div><span>文章洞察</span></div><div class="nav-label">工作台</div><nav>${[['library', '文章库', 'grid'], ['filter', 'AI 筛选', 'spark'], ['search', '标题搜索', 'search']].map(([page, label, symbol]) => button(page, label, symbol, state.page === page ? 'active' : '')).join('')}</nav><div class="sidebar-bottom">${button('settings', '使用说明 / 设置', 'info')}<div class="profile"><div class="avatar">M</div><div><strong>Michael</strong><small>SQLite · 后端工作区</small></div></div></div></aside><main><header><div><div class="eyebrow">${isFilter ? '个性化推荐' : isSearch ? '查找文章' : '我的收藏'}</div><h1>${isFilter ? 'AI 智能筛选' : isSearch ? '搜索文章标题' : '文章库'}</h1><p>${isFilter ? '添加兴趣标签，后端 AI 将逐篇判断文章是否相关。' : isSearch ? '输入关键词，在后端 SQLite 中模糊匹配文章标题。' : '所有文章均从后端 SQLite 数据库读取，刷新和重启不会丢失。'}</p></div>${!isFilter ? button('import', state.importing ? '正在导入…' : '导入文章', state.importing ? 'loader' : 'upload', 'primary', busy) : ''}</header><div id="notice" class="notice" role="status"></div>
      ${isFilter ? `<section class="filter-panel"><div class="panel-icon">${icon('spark')}</div><h2>你想关注什么？</h2><p>添加一个或多个兴趣标签。后端会逐篇调用 SystemOne API，展示与任意标签相关的文章；不修改文章库。只有标题的文章将按标题判断。</p><div class="tag-box">${state.tags.map((tag, index) => `<span class="tag">${escapeHtml(tag)}<button type="button" data-remove-tag="${index}" aria-label="移除 ${escapeHtml(tag)}" ${busy ? 'disabled' : ''}>${icon('close')}</button></span>`).join('')}<input id="tag-input" placeholder="输入兴趣标签后按回车…" aria-label="兴趣标签" ${busy ? 'disabled' : ''}>${button('add-tag', '', 'plus', 'add-tag', busy)}</div><div class="filter-actions"><span>本次将分析文章库中的 ${state.articles.length} 篇文章</span>${button('filter-run', state.loading ? '正在分析…' : '开始 AI 筛选', state.loading ? 'loader' : 'spark', 'primary', busy)}</div>${state.results !== null ? `<div class="filter-results"><div class="toolbar"><span class="result-count">AI 筛选结果：${state.results.length} 篇文章</span></div>${grid(state.results, '没有文章与当前兴趣标签相关。')}</div>` : ''}</section>` : `<section class="content"><div class="toolbar">${isSearch ? `<div class="search-input">${icon('search')}<input id="search-input" value="${escapeHtml(state.query)}" placeholder="输入文章标题关键词…" aria-label="标题关键词"></div><span id="search-count" class="result-count">共 ${state.searchArticles.length} 篇</span>` : `<span class="result-count">共 ${state.articles.length} 篇文章</span><span class="sort">按导入时间排序</span>`}</div><div id="article-grid">${grid(isSearch ? state.searchArticles : state.articles, isSearch ? '未找到匹配标题的文章。' : '暂无文章。请导入符合协议的 JSON 文件。')}</div></section>`}<p class="hint">纯 HTML 前端 · SQLite 持久化后端。AI 密钥仅保存在后端，筛选需要联网并产生 API 调用费用。</p></main></div>`;
    showNotice(state.notice);
  }
  async function loadLibrary() {
    state.articles = normalize(await request('/api/articles'));
    render();
  }
  async function search(value) {
    state.query = value;
    const version = ++searchVersion;
    const results = normalize(await request(`/api/articles?query=${encodeURIComponent(value)}`));
    if (version !== searchVersion) return;
    state.searchArticles = results;
    if (state.page === 'search') {
      document.getElementById('article-grid').innerHTML = grid(results, '未找到匹配标题的文章。');
      document.getElementById('search-count').textContent = `共 ${results.length} 篇`;
    }
  }
  async function navigate(page) {
    state.page = page;
    render();
    if (page === 'library') await loadLibrary();
    if (page === 'search') { document.getElementById('search-input').focus(); await search(state.query); }
  }
  function addTag() {
    const tag = document.getElementById('tag-input').value.trim();
    if (!tag || state.tags.includes(tag)) return;
    state.tags.push(tag);
    state.results = null;
    render();
    document.getElementById('tag-input').focus();
  }
  async function importFiles(files) {
    state.importing = true;
    state.notice = '';
    render();
    try {
      const payload = await Promise.all(files.map(async (file) => ({ name: file.name, text: await file.text() })));
      const result = await request('/api/articles/import', { files: payload });
      state.results = null;
      state.articles = normalize(await request('/api/articles'));
      if (state.page === 'search') await search(state.query);
      state.notice = `成功导入 ${result.importedCount} 篇文章${result.errors.length ? `\n${result.errors.join('\n')}` : ''}`;
    } finally { state.importing = false; render(); }
  }
  async function runFilter() {
    if (!state.tags.length) { showNotice('请至少添加一个兴趣标签'); return; }
    state.loading = true;
    state.results = null;
    state.notice = '后端正在逐篇调用 SystemOne，请耐心等待。';
    render();
    try {
      state.results = normalize(await request('/api/articles/filter', { tags: [...state.tags] }));
      state.notice = `AI 筛选完成，找到 ${state.results.length} 篇相关文章`;
    } finally { state.loading = false; render(); }
  }
  function openDialog(title, content) {
    const dialog = document.createElement('dialog');
    dialog.innerHTML = `<div class="dialog-header"><h2>${escapeHtml(title)}</h2><button class="close" aria-label="关闭">${icon('close')}</button></div>${content}`;
    root.append(dialog);
    dialog.querySelector('.close').addEventListener('click', () => dialog.close());
    dialog.addEventListener('close', () => dialog.remove());
    dialog.showModal();
  }
  function viewArticle(id) {
    const visible = state.page === 'search' ? state.searchArticles : state.page === 'filter' ? state.results : state.articles;
    const article = visible.find((item) => item.id === id);
    const source = article.source && URL.canParse(article.source) ? new URL(article.source) : null;
    const safeLink = source && ['http:', 'https:'].includes(source.protocol);
    openDialog(article.title, `<div class="card-tags">${article.tags.map((tag) => `<span>${escapeHtml(tag)}</span>`).join('')}</div><div class="article-content">${escapeHtml(article.content || '这篇文章仅包含标题，尚未导入正文。')}</div>${article.published_at ? `<p>发布时间：${escapeHtml(article.published_at)}</p>` : ''}${safeLink ? `<a href="${escapeHtml(source.href)}" target="_blank" rel="noopener noreferrer">查看原文 ↗</a>` : `<p>来源：${escapeHtml(article.source || '未提供')}</p>`}`);
  }
  const actions = {
    library: () => navigate('library'), search: () => navigate('search'), filter: () => navigate('filter'),
    import: () => fileInput.click(), 'add-tag': addTag, 'filter-run': runFilter,
    settings: () => openDialog('使用说明 / 设置', '<p>HTML 前端通过 HTTP API 访问独立后端。所有文章保存在后端 data/articles.db，刷新或后端重启不会丢失。不要双击 HTML 离线打开，请使用后端提供的 HTTP 地址。</p><p>导入 JSON 可为单篇对象或非空数组。必填 title；可选 content、source（URL）、publishedAt（ISO 日期时间）、tags（字符串数组）。不允许其他字段。每个文件校验成功后整批导入；失败文件会明确显示错误。</p><pre>{ "title": "文章标题", "content": "文章正文", "tags": ["AI"] }</pre><p>后端逐篇调用 SystemOne decision-model-preview，任意标签 noul ≥ 0.5 即入选，不修改文章库。密钥不会发送到浏览器。网络、HTTP 或响应格式错误会明确显示，不使用模拟筛选。</p><p>当前是共享文章库，无用户登录或访问控制。请只部署到可信网络；公网部署前应配置身份认证、HTTPS 与访问限制。</p>')
  };
  root.addEventListener('input', (event) => {
    if (event.target.id === 'search-input') void reportErrors(search)(event.target.value);
  });
  root.addEventListener('keydown', (event) => {
    if (event.target.id === 'tag-input' && event.key === 'Enter') { event.preventDefault(); addTag(); }
    const card = event.target.closest('[data-article]');
    if (card && ['Enter', ' '].includes(event.key)) { event.preventDefault(); viewArticle(Number(card.dataset.article)); }
  });
  root.addEventListener('click', (event) => {
    const card = event.target.closest('[data-article]');
    if (card) { viewArticle(Number(card.dataset.article)); return; }
    const remove = event.target.closest('[data-remove-tag]');
    if (remove && !state.loading && !state.importing) { state.tags.splice(Number(remove.dataset.removeTag), 1); state.results = null; render(); return; }
    const action = event.target.closest('[data-action]')?.dataset.action;
    if (action) void reportErrors(actions[action])();
  });
  fileInput.addEventListener('change', () => {
    const files = [...fileInput.files];
    fileInput.value = '';
    void reportErrors(importFiles)(files);
  });
  render();
  void reportErrors(loadLibrary)();
})();
