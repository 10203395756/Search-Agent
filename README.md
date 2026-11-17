# Search-Agent 智能调研助手

基于 LangGraph + LLM + Serper 搜索引擎的自主调研 Agent，自动搜索、抓取网页、校验信息、生成调研报告，支持追加指令迭代优化报告。 前端采用 SSE 流式渲染，实时展示调研进度，可导出 Markdown。

## ✨ 功能特性

- 🧠 自主规划：大模型自动生成搜索关键词
- 🔍 联网搜索：调用 Serper API 谷歌搜索
- 📄 网页精读：自动抓取网页正文，剔除广告、导航等冗余内容
- 🔁 循环检索：自动判断信息是否充足，不足则补充搜索（最多 5 轮）
- ✍️ 流式写报告：SSE 实时推送报告内容
- ✏️ 追加迭代：报告生成后，支持继续深挖、修改、精简
- 📤 报告导出：一键复制、导出 Markdown
- 🎨 简单前端页面，PC / 移动端自适应

## 📁 项目结构

```
search-agent/
├── backend/
│   ├── .env                # 环境密钥配置（自行新建，不要提交git）
│   ├── research_agent_v2.py # LangGraph Agent核心逻辑
│   ├── main.py             # FastAPI SSE后端服务
│   └── venv/               # Python虚拟环境（自动生成）
└── index.html              # 前端页面，直接浏览器打开
```

## 🧰 环境依赖

- Python >= 3.10（推荐 3.11/3.12；3.13 也可，注意 uvicorn reload 兼容性）
- 密钥准备：
  1. Serper API Key：https://serper.dev/ 注册获取（用于谷歌搜索）
  2. LLM API Key：兼容 OpenAI 格式接口（OpenAI / 豆包 / 通义千问 / DeepSeek 等）

## 🚀 快速部署

### 1. 克隆 / 下载项目，进入后端目录

```
cd search-agent/backend
```

### 2. 创建并激活虚拟环境

```
# 创建虚拟环境
python -m venv venv

# Windows cmd 激活
venv\Scripts\activate
# Windows PowerShell 激活
venv\Scripts\Activate.ps1
# Mac / Linux
source venv/bin/activate
```

激活成功，终端前缀出现 `(venv)`

### 3. 安装依赖包

```
pip install langgraph langchain-openai beautifulsoup4 requests python-dotenv fastapi uvicorn
```

### 4. 配置 .env 文件

在 backend 目录新建 `.env`，写入下面内容并替换密钥：

```
SERPER_API_KEY=你的Serper密钥
OPENAI_API_KEY=你的LLM密钥
OPENAI_BASE_URL=https://api.openai.com/v1
MODEL_NAME=gpt-3.5-turbo
```

> 国内大模型示例（DeepSeek）：
>
> ```
> OPENAI_BASE_URL=https://api.deepseek.com/v1
> MODEL_NAME=deepseek-chat
> ```

### 5. 启动后端服务

```
python main.py
```

服务启动成功：`http://0.0.0.0:8000`

> 备选（开发热重载，Windows 下 3.13 容易报错）：
>
> ```
> uvicorn main:app --reload
> ```

### 6. 打开前端

直接双击打开 `index.html`，在页面输入调研需求，开始调研。

## 📖 使用说明

1. **新建调研**：输入调研主题，展开高级选项选择输出格式（要点清单 / 对比表格 / 完整调研报告），选择是否过滤营销软文，点击【开始调研】

2. **查看进度**：看板实时展示：拆解目标 → 搜索网页 → 精读内容 → 信息校验 → 生成报告

3. 追加指令

   ：报告生成完成后，在追加输入框提交指令，例如：

   - 深挖 XX 部分，增加数据
   - 精简全文到 300 字
   - 对比 A 和 B 的优缺点

4. **导出**：复制全文 / 导出 Markdown

## ⚙️ 核心参数说明（在 research_agent_v2.py）

```
MAX_ROUND = 5  # 最大搜索轮次，防止无限搜索
```

## 🐛 常见问题

1. ```
   ModuleNotFoundError: No module named xxx
   ```

   - 确认已经激活虚拟环境 `(venv)`，再执行 pip install

2. ```
   ImportError: cannot import name 'SerperDevTool'
   ```

   - 当前版本已经移除 langchain 内置 Serper 工具，使用原生 requests 调用，使用本文提供的完整 `research_agent_v2.py`

3. 后端启动成功，前端无响应

   - F12 打开浏览器控制台，检查 SSE 连接；检查 `.env` 密钥是否正确、接口是否能连通

4. Windows + Python3.13 使用 

   ```
   uvicorn --reload
   ```

    报错

   - 改用 `python main.py` 启动，改代码手动重启服务

5. 网页抓取失败

   - 部分网站有反爬，会返回【抓取失败】，属于正常现象

## 📌 开发 & 扩展方向

- 接入 SQLite 持久化任务，重启服务不丢失历史报告
- 增加用户登录、历史记录列表
- 支持图片搜索、PDF 上传作为参考资料
- 优化抓取策略，增加代理池
- 增加导出 PDF、Word 功能
- 前端打包独立部署，Nginx 托管

## 📄 License

MIT License，仅供学习研究使用。

### 前端界面：

![前端界面](D:\work\code\search-agent\前端界面.png)

