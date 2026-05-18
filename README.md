# 🔥 Lighter Order Parser — Demo

打火机厂商销售订单 **AI 自动解析** 流水线 Demo。

客户邮件 / PDF / Excel / 表格 → 一键抽取 **型号、颜色、数量、配件、品质要求、交期、Incoterms** 等字段 → 导出 JSON / Excel，供下游发货排程与生产排产使用。

支持任意语言的订单（已内置中 / 英 / 西班牙语样例），UI 中英双语切换。

---

## 一、本地运行

### 1. 安装依赖（Python 3.10+）

```powershell
cd D:\Demo
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 2. 配置 API Key

复制 `.env.example` 为 `.env`，填入 DeepSeek key（在 https://platform.deepseek.com 注册获取）：

```
DEEPSEEK_API_KEY=sk-xxxxxxxxxxxxxxxx
DEEPSEEK_MODEL=deepseek-chat
```

> 没有 key 也能跑 UI——点 **「演示模式」** 按钮即可，使用内置假数据。

### 3. 启动

```powershell
streamlit run app.py
```

浏览器自动打开 http://localhost:8501

---

## 二、给客户/同事看（云部署）

让别人不装任何东西、点开链接就能用，推荐 **Streamlit Community Cloud**（免费）。

### 步骤

1. 在 GitHub 新建一个 **私有仓库**，把本目录推上去
   ```powershell
   cd D:\Demo
   git init
   git add .
   git commit -m "init lighter order parser demo"
   git branch -M main
   git remote add origin https://github.com/<your-account>/<repo>.git
   git push -u origin main
   ```
   > `.gitignore` 已经排除 `.env`，确保 API key 不会泄漏到 GitHub。

2. 访问 https://share.streamlit.io → 登录 GitHub → **New app**
   - Repository: 选刚才那个仓库
   - Main file path: `app.py`

3. 在 app 的 **Settings → Secrets** 里填入 API key：
   ```toml
   DEEPSEEK_API_KEY = "sk-xxxxxxxxxxxxxxxx"
   DEEPSEEK_MODEL = "deepseek-chat"
   ```
   保存后 app 会自动重启。

4. 拿到一个形如 `https://xxx.streamlit.app` 的公网链接，直接发给客户。

> Streamlit Cloud 免费档允许 3 个公开 app 同时在线，足够 demo 用。

---

## 三、目录结构

```
D:\Demo\
├── app.py                       # Streamlit 主入口
├── agents/
│   └── order_parser.py          # 订单解析 Agent (DeepSeek)
├── utils/
│   ├── i18n.py                  # 中英双语界面
│   └── file_loader.py           # PDF/Excel/CSV/TXT 加载
├── samples/                     # 多语言样例订单
│   ├── sample_en_email.txt
│   ├── sample_cn_order.txt
│   └── sample_es_order.txt
├── .streamlit/config.toml       # UI 主题
├── .env.example
├── .gitignore
├── requirements.txt
└── README.md
```

---

## 四、当前状态 / Roadmap

| 模块 | 状态 |
|---|---|
| 订单导入 + AI 解析 + 字段校正 + 导出 | ✅ 完成（本 Demo） |
| 发货计划（30 天，按交期排序，含危险品船期约束） | 🚧 待开发 |
| 生产排产（按 BOM + 工艺路线倒排） | 🚧 待开发 |
| 异常协调（缺料 / 产能冲突 / 客户邮件起草） | 🚧 待开发 |
| 产品主数据 SKU 库 / BOM 库对接 | 🚧 待开发 |

下一步建议先打通 **发货计划**——拿到结构化订单后已经可以基于客户要求交期 + 运输方式自动生成发货时间表，逻辑相对简单且业务价值直观。

---

## 五、安全注意事项

- `.env` 已在 `.gitignore` 中，**不要提交到 GitHub**
- 不要在 demo 数据库中放真实客户敏感数据
- Streamlit Cloud Secrets 中存 API key，仓库即使是 private 也不要硬编码
- 客户演示完后可在 Streamlit Cloud 控制台 **暂停 / 删除 app**，避免被外部访问
