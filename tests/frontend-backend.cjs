const assert = require('node:assert/strict');
const { spawn } = require('node:child_process');
const { once } = require('node:events');
const fs = require('node:fs/promises');
const os = require('node:os');
const path = require('node:path');
const { chromium } = require('playwright');

(async () => {
  const root = path.resolve(__dirname, '..');
  const temp = await fs.mkdtemp(path.join(os.tmpdir(), 'article-lens-http-'));
  const database = path.join(temp, 'articles.db');
  let child;
  let browser;
  async function startBackend() {
    child = spawn('python3', ['-u', '-m', 'tests.serve_backend_fixture', database], { cwd: root, stdio: ['ignore', 'pipe', 'pipe'] });
    child.stderr.on('data', () => {});
    return new Promise((resolve, reject) => {
      let output = '';
      child.stdout.on('data', (chunk) => {
        output += chunk;
        if (output.includes('\n')) resolve(JSON.parse(output.split('\n')[0]));
      });
      child.on('error', reject);
      child.on('exit', (code) => { if (!output) reject(new Error(`Backend fixture exited: ${code}`)); });
    });
  }
  async function stopBackend() {
    const exited = once(child, 'exit');
    child.kill('SIGINT');
    await exited;
    child = undefined;
  }
  try {
    let addresses = await startBackend();
    browser = await chromium.launch({ channel: 'chrome', headless: true });
    const page = await browser.newPage();
    const errors = [];
    const requests = [];
    page.on('pageerror', (error) => errors.push(error.message));
    page.on('request', (request) => requests.push(request));
    const navigate = (action) => page.locator(`[data-action="${action}"]`).click();
    const upload = async (name, data) => {
      await page.locator('#import-files').setInputFiles({ name, mimeType: 'application/json', buffer: Buffer.from(JSON.stringify(data)) });
      await page.waitForFunction(() => document.getElementById('notice').textContent.startsWith('成功导入'));
    };
    await page.goto(addresses.base);
    await page.waitForFunction(() => document.querySelectorAll('.card').length === 100);
    assert.equal(requests.some((request) => request.url().includes('aliyuncs.com')), false);
    assert.equal(requests.some((request) => 'authorization' in request.headers()), false);
    assert.equal((await page.content()).includes('test-server-key'), false);
    await page.locator('.card').first().click();
    assert.match(await page.locator('dialog').textContent(), /仅包含标题/);
    await page.getByRole('button', { name: '关闭', exact: true }).click();
    await navigate('search');
    await page.locator('#search-input').fill('人工智能');
    await page.waitForFunction(() => document.querySelectorAll('.card h3').length > 0 && [...document.querySelectorAll('.card h3')].every((item) => item.textContent.includes('人工智能')));
    await page.locator('#search-input').fill('不存在的标题123456');
    await page.waitForFunction(() => document.querySelectorAll('.card').length === 0);
    await navigate('library');
    await page.waitForFunction(() => document.querySelectorAll('.card').length === 100);
    await upload('invalid.json', [{ title: '不能部分导入' }, { title: 'bad', extra: true }]);
    assert.match(await page.locator('#notice').textContent(), /成功导入 0 篇/);
    assert.equal(await page.locator('.card').count(), 100);
    await upload('valid.json', [{ title: '测试-人工智能文章', content: '完整正文', tags: ['AI'], source: 'https://example.com/article' }, { title: '<img src=x onerror="window.PWNED=1">', content: '</script><script>window.PWNED=2</script>这是全文', source: 'javascript:alert(1)' }]);
    assert.equal(await page.locator('.card').count(), 102);
    assert.equal(await page.evaluate(() => window.PWNED), undefined);
    await page.locator('.card').first().click();
    assert.match(await page.locator('.article-content').textContent(), /这是全文/);
    assert.equal(await page.locator('dialog a').count(), 0);
    await page.getByRole('button', { name: '关闭', exact: true }).click();
    await page.reload();
    await page.waitForFunction(() => document.querySelectorAll('.card').length === 102);
    await stopBackend();
    addresses = await startBackend();
    await page.goto(addresses.base);
    await page.waitForFunction(() => document.querySelectorAll('.card').length === 102);

    // Slow older queries must not overwrite a newer response.
    await navigate('search');
    await page.route('**/api/articles?query=slow', async (route) => {
      await new Promise((resolve) => setTimeout(resolve, 350));
      await route.continue();
    });
    await page.locator('#search-input').fill('slow');
    await page.locator('#search-input').fill('测试-');
    await page.waitForFunction(() => document.querySelectorAll('.card').length === 1 && document.querySelector('.card h3').textContent.startsWith('测试-'));
    await page.waitForTimeout(500);
    assert.equal(await page.locator('.card').count(), 1);
    await page.unroute('**/api/articles?query=slow');

    await navigate('filter');
    await navigate('filter-run');
    assert.match(await page.locator('#notice').textContent(), /至少添加/);
    for (const tag of ['AI', '经济']) {
      await page.locator('#tag-input').fill(tag);
      await page.locator('#tag-input').press('Enter');
    }
    await fetch(`${addresses.upstream}/?mode=success`);
    await navigate('filter-run');
    await page.waitForFunction(() => document.getElementById('notice').textContent.includes('AI 筛选完成'));
    assert.equal(await page.locator('.filter-results .card').count(), 2);
    assert.equal((await (await fetch(addresses.upstream)).json()).calls, 102);
    await navigate('library');
    await page.waitForFunction(() => document.querySelectorAll('.card').length === 102);
    assert.equal(await page.locator('.card-tags').first().textContent(), '', 'AI results do not modify stored tags');
    await navigate('filter');
    await page.locator('[data-remove-tag="1"]').click();
    assert.equal(await page.locator('.tag').count(), 1);
    assert.equal(await page.locator('.filter-results').count(), 0);
    for (const [mode, message] of [['http', /401/], ['invalid', /返回格式错误/], ['invalid-json', /合法 JSON/]]) {
      await fetch(`${addresses.upstream}/?mode=${mode}`);
      await navigate('filter-run');
      await page.waitForFunction(() => !document.querySelector('[data-action="filter-run"]').disabled);
      assert.match(await page.locator('#notice').textContent(), message);
      assert.equal(await page.locator('.filter-results').count(), 0);
    }
    await page.setViewportSize({ width: 390, height: 844 });
    await navigate('library');
    assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth));
    await stopBackend();
    await navigate('library');
    await page.waitForFunction(() => document.getElementById('notice').textContent.includes('无法连接后端'));
    assert.deepEqual(errors, []);
    assert.equal(requests.some((request) => request.url().includes('aliyuncs.com')), false);
    console.log('PASS: HTML/SQLite HTTP integration, 100 seed articles, server search and race handling, atomic import, refresh/backend restart persistence, XSS safety, server-only AI requests, threshold, isolated results, errors and mobile layout.');
    console.log('SystemOne was a local HTTP fixture; no paid external API requests were made.');
  } finally {
    if (child) await stopBackend();
    if (browser) await browser.close();
    await fs.rm(temp, { recursive: true, force: true });
  }
})().catch((error) => { console.error(error); process.exitCode = 1; });
