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
| 订单导入 + AI 解析 + 字段校正 + 导出 | ✅ 完成 |
| 生产排产（工序级产能核对 + 30 天日计划） | ✅ 完成 v1（2026-07-11） |
| 发货计划（30 天，按交期排序，含危险品船期约束） | 🚧 待开发 |
| 排产升级：机台级指派 / 换型规则 / 注塑产能接入 | 🚧 待开发 |
| 异常协调（缺料 / 产能冲突 / 客户邮件起草） | 🚧 待开发 |
| 产品主数据 SKU 库 / BOM 库对接 | 🚧 待开发 |

### 生产排产 v1 说明

- **产能主数据**：`data/capacity.json`，由工厂 2026-07-08 提供的产能 Excel（`排产数据/排产软件/`，不入库）解析而来，覆盖 38 个型号 × 6 道工序
- **工艺路线**（工厂确认 2026-07-11）：焊接→加气→调火(试火)→翻板/组装→机检/手检(质检)→包装；注塑是配件线、独立工单,不在整机路线内
- **口径**：工序级瓶颈汇总；产能区间取保守下限；同机多型号未建模争用；包装的"通用"机台归入共享池,型号专用机台不足时自动启用
- **引擎**：`utils/scheduler.py`，EDD 顺序 + 每日产能池 + 隔日转运；支持加班系数、周日停工
- **重新生成主数据**（工厂更新 Excel 后）：
  ```powershell
  python -m utils.capacity_loader "排产数据\排产软件" data\capacity.json
  ```
- 型号不在主数据、某工序无数据、交期不可达都会在界面上明确提示

---

## 五、安全注意事项

- `.env` 已在 `.gitignore` 中，**不要提交到 GitHub**
- 不要在 demo 数据库中放真实客户敏感数据
- Streamlit Cloud Secrets 中存 API key，仓库即使是 private 也不要硬编码
- 客户演示完后可在 Streamlit Cloud 控制台 **暂停 / 删除 app**，避免被外部访问
