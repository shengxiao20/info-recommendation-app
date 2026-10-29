# 文章洞察 · HTML 前端 + SQLite 后端

本项目只包含 HTML 前端与 Python HTTP/SQLite 后端。

## 启动

需要 **Python 3.9+**，后端只使用标准库，无需安装 Python 包或编译 SQLite 模块。

在新环境中，先在项目根目录创建配置文件：

```bash
cp .env.example .env
```

编辑 `.env`，填写 `DASHSCOPE_API_KEY`。本机现有密钥已迁入 `.env`，无需重新复制示例覆盖它。Windows PowerShell 可使用 `Copy-Item .env.example .env`。

然后在项目根目录执行：

```bash
python3 scripts/build_frontend.py
python3 -m backend.server
```

也可以使用 npm 快捷脚本（运行服务不需要先执行 `npm install`）：

```bash
npm start
```

`npm run start:web` 和 `npm run dev` 同样构建前端并启动后端。修改前端后需重新启动以加载新 HTML；这里没有开发服务器热更新。

浏览器打开 **http://127.0.0.1:8787**。按 Ctrl+C 停止后端。

不要双击生成的 HTML 文件离线打开；它是 HTTP 前端，需要连接后端。前端产物为 `release/文章洞察-前端.html`，CSS、JS、SVG 均内联，无外部依赖或 API 密钥。

## 发给别人看

在服务器或可被同事访问的电脑上启动：

```bash
ARTICLE_LENS_HOST=0.0.0.0 ARTICLE_LENS_PORT=8787 python3 -m backend.server
```

把 `http://你的服务器IP:8787` 发给别人。需要放通网络端口，并保持后端运行。Windows PowerShell 可使用：

```powershell
$env:ARTICLE_LENS_HOST = "0.0.0.0"
$env:ARTICLE_LENS_PORT = "8787"
python -m backend.server
```

**当前没有用户登录或访问控制，所有访问者共用一份文章库，也能触发付费 AI 调用。只用于可信网络。公网部署前，应通过反向代理配置 HTTPS、身份认证和访问限制。** 默认只监听 `127.0.0.1`，不会主动开放给其他电脑。

前后端职责和源文件独立，运行时由后端提供 HTML 和 `/api/*`，保持同源，避免浏览器 CORS。以后可将 HTML 放到静态服务器，并将同域 `/api/*` 转发到此后端；本版本没有另加跨域或代理回退。

## 功能

- SQLite 文章库：数据库为 `data/articles.db`，首次启动或库为空时从 `resources/articles.seed.db` 恢复 100 篇种子文章。
- 标题搜索：后端参数化 SQL `WHERE title LIKE ? ORDER BY id DESC`。
- JSON 导入：选择多个文件，后端逐文件校验并事务导入。某文件有非法文章时整份文件不入库，返回明确错误；其他合法文件可以正常导入。
- 导入字段定义见 `schemas/article-import.schema.json`：必填 `title`，可选 `content`、`source`、`publishedAt`、`tags`，不允许额外字段；`examples/` 中提供可导入的 JSON 示例。
- AI 筛选：后端逐篇调用真实 SystemOne `decision-model-preview`，每篇一次请求、每个兴趣标签一个 `noul` 问题；任意标签评分 ≥ 0.5 即入选。不改变文章库或原有标签。
- 前端保留文章库、标题搜索、标签添加/删除、筛选结果、文章详情和错误提示。文章在刷新及后端重启后仍保留。

**SystemOne 密钥保存在根目录 `.env`，由后端读取，不写入源码或发送到前端。** 浏览器只访问本后端，由 Python 请求 SystemOne，因此不依赖 SystemOne 开放浏览器跨域预检。API 密钥失效、网络错误及上游异常仍会明确报错；没有模拟筛选。

### 环境配置

- `.env.example`：不含真实密钥的配置模板，可以提交和分享。
- `.env`：本地密钥文件，已在 `.gitignore` 中忽略，不应提交或分享。
- 后端从项目根目录加载 `.env`，与启动时所在目录无关。文件必须存在，`DASHSCOPE_API_KEY` 必须非空，否则启动报错；没有硬编码密钥回退。
- 加载器使用 Python 标准库，支持 `KEY=value`、完整行注释、空行和包裹值的单/双引号；不进行变量展开。格式错误、重复字段、未闭合引号会报错。
- 显式导出的环境变量优先于 `.env` 中同名配置；现有 `ARTICLE_LENS_HOST` 和 `ARTICLE_LENS_PORT` 用法不变。
- 修改 `.env` 后需重启后端。对外分发项目时，只带 `.env.example`，让接收方配置自己的密钥。

## 文件与调用关系

```text
frontend/
├── template.html          HTML 页面外壳
├── styles.css             样式与移动端布局
└── app.js                 UI、文件选择、HTTP API 调用
scripts/build_frontend.py
└── release/文章洞察-前端.html
backend/
├── config.py              后端配置与环境变量读取
├── environment.py         .env 加载、必填变量校验
├── server.py              HTTP 路由与统一错误处理装饰器
├── validation.py          导入与兴趣标签校验
├── storage.py             SQLite、种子恢复、查询、事务导入
└── systemone.py           真实 AI 请求与评分处理
```

```text
浏览器 HTML
├── GET /api/articles[?query=关键词]
│   └── ArticleStore.list_articles → SQLite
├── POST /api/articles/import
│   └── 校验 JSON → 每文件事务 → SQLite
└── POST /api/articles/filter
    └── SQLite 文章快照 → SystemOne 逐篇判定 → 返回匹配文章
```

API 文章记录包含 `id`、`title`、`content`、`source`、`published_at`、`created_at`、`filtered` 和 JSON 字符串 `matched_tags`。

导入请求：

```json
{"files":[{"name":"articles.json","text":"[{\"title\":\"文章标题\"}]"}]}
```

导入响应：`{"importedCount":1,"errors":[]}`。

筛选请求：`{"tags":["AI","经济"]}`；响应是匹配文章数组。

请求错误 HTTP 400；SystemOne 错误 HTTP 502；内部错误 HTTP 500 且写服务端日志。前端显示错误，不使用离线数据回退。

## 回归测试

只运行后端测试，无需 Node 或安装依赖：

```bash
python3 scripts/build_frontend.py
python3 -m unittest discover -s tests -p 'test_backend.py'
```

完整回归需要 **Node.js 20+**、npm 和本机 Google Chrome：

```bash
npm install
npm test
```

`npm test` 自动构建 HTML 后运行后端测试及 Chrome 浏览器联调。npm 唯一的开发依赖是 Playwright，前端和后端运行时均不依赖它。

覆盖环境文件加载与必填密钥校验、种子恢复、LIKE 搜索、SQL 参数化、文件原子导入、SQLite 持久化、真实 HTTP 请求格式与鉴权头、AI 阈值和库隔离、上游错误、HTML 无密钥、浏览器搜索竞态、XSS、刷新/重启和移动端布局。

测试使用本地 SystemOne HTTP 测试服务，不请求真实付费接口。它验证前后端调用链，但不代表现有 API 密钥和远程服务已经通过在线可用性验证。
