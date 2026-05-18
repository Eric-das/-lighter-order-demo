"""订单解析 Agent
- 真实模式: 调用 DeepSeek / OpenAI 兼容 API 抽取字段
- 演示模式: 根据样例订单内容关键字匹配预设结果, 无需 API key
"""
import json
import os
import time
from typing import Optional

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()


SYSTEM_PROMPT = """You are a professional sales-order parser for a lighter manufacturer.
The input can be an email, an excerpt of an Excel/CSV table, a PDF text dump, or any free-form order text, in ANY language (English / Chinese / Spanish / French / German / Arabic / ...).

Extract the order into strict JSON with TWO top-level keys:
  1. "order_meta" — order-level metadata
  2. "line_items" — an array of product lines

Schema:

order_meta:
  customer              (string)
  contact               (string)
  email                 (string)
  po_number             (string)
  requested_delivery    (string)  prefer YYYY-MM-DD
  incoterms             (string)
  destination           (string)
  payment_terms         (string)
  original_language     (string)  zh / en / es / ...
  notes                 (string)

line_items[]:
  sku                   (string)
  color                 (string)  "中文 (English)" when possible
  quantity              (number)  plain number, parse "10,000" / "15.000"
  unit                  (string)
  accessories           (string)  comma-separated
  quality_requirements  (string)
  unit_price            (string)  with currency
  notes                 (string)

Rules:
- If a field is missing, set null. DO NOT invent.
- quantity must be a number.
- Output MUST be valid JSON only, no markdown fences, no commentary.
"""


# ---------------------------------------------------------------------------
# Pre-canned demo results — one per sample file, looks like AI output
# ---------------------------------------------------------------------------
DEMO_RESULTS = {
    "en": {
        "order_meta": {
            "customer": "ACME Lighting Co., Ltd.",
            "contact": "John Smith",
            "email": "john.smith@acme-lighting.com",
            "po_number": "PO-2026-0518",
            "requested_delivery": "2026-06-30",
            "incoterms": "FOB Shenzhen",
            "destination": "Hamburg, Germany",
            "payment_terms": "T/T 30 days after BL",
            "original_language": "en",
            "notes": "Logo artwork for Item 2 attached separately",
        },
        "line_items": [
            {
                "sku": "LT-101 Classic",
                "color": "红色 (Red)",
                "quantity": 10000,
                "unit": "pcs",
                "accessories": "flint stone, windproof cap",
                "quality_requirements": "ISO 9994, CE",
                "unit_price": "USD 0.35",
                "notes": None,
            },
            {
                "sku": "LT-202 Slim",
                "color": "黑色 (Black)",
                "quantity": 5000,
                "unit": "pcs",
                "accessories": "flint stone",
                "quality_requirements": "ISO 9994",
                "unit_price": "USD 0.42",
                "notes": "Logo printing required",
            },
        ],
    },
    "zh": {
        "order_meta": {
            "customer": "广州明辉贸易有限公司",
            "contact": "张经理",
            "email": "zhang@minghui-trade.com",
            "po_number": "MH-20260518-001",
            "requested_delivery": "2026-07-15",
            "incoterms": "FOB 深圳",
            "destination": "广州黄埔港",
            "payment_terms": "见单后30天 T/T",
            "original_language": "zh",
            "notes": "Item 2 需丝印客户LOGO,稿件另发邮件",
        },
        "line_items": [
            {
                "sku": "LT-303 豪华款",
                "color": "金色 (Gold)",
                "quantity": 8000,
                "unit": "支",
                "accessories": "精钢打火轮, 燃气可视窗",
                "quality_requirements": "ISO 9994, 欧盟 REACH 合规",
                "unit_price": "CNY 3.80",
                "notes": None,
            },
            {
                "sku": "LT-101 经典款",
                "color": "蓝色 (Blue)",
                "quantity": 20000,
                "unit": "支",
                "accessories": "标准打火石",
                "quality_requirements": "ISO 9994",
                "unit_price": "CNY 2.20",
                "notes": "需丝印客户LOGO",
            },
        ],
    },
    "es": {
        "order_meta": {
            "customer": "Distribuidora Iberica S.L.",
            "contact": "Carlos Mendez",
            "email": "carlos.mendez@iberica-dist.es",
            "po_number": "ESP-2026-0042",
            "requested_delivery": "2026-08-25",
            "incoterms": "CIF Valencia",
            "destination": "Puerto de Valencia, España",
            "payment_terms": "Carta de crédito a 60 días",
            "original_language": "es",
            "notes": "Mercado UE: marca CR (Child Resistant) obligatoria",
        },
        "line_items": [
            {
                "sku": "LT-202 Slim",
                "color": "黑色 (Black / Negro)",
                "quantity": 15000,
                "unit": "unidades",
                "accessories": "piedra de chispa, gatillo de seguridad infantil",
                "quality_requirements": "ISO 9994, CE, CR (Child Resistant)",
                "unit_price": "EUR 0.38",
                "notes": None,
            },
            {
                "sku": "LT-101 Classic",
                "color": "绿色 (Green / Verde)",
                "quantity": 8000,
                "unit": "unidades",
                "accessories": "piedra de chispa estándar",
                "quality_requirements": "ISO 9994",
                "unit_price": "EUR 0.28",
                "notes": "Logo serigrafiado a 2 colores",
            },
        ],
    },
    "ja": {
        "order_meta": {
            "customer": "東京ライティング株式会社 (Tokyo Lighting Co., Ltd.)",
            "contact": "田中 健一 (Tanaka Ken'ichi)",
            "email": "tanaka@tokyo-lighting.co.jp",
            "po_number": "TL-2026-0518-A",
            "requested_delivery": "2026-08-10",
            "incoterms": "CIF 東京 (CIF Tokyo)",
            "destination": "東京港、日本 (Port of Tokyo, Japan)",
            "payment_terms": "L/C at sight (一覧払い信用状)",
            "original_language": "ja",
            "notes": "Item 2: 会社ロゴ2色シルク印刷, 入稿データ別途",
        },
        "line_items": [
            {
                "sku": "LT-505 プレミアム",
                "color": "银色 (Silver / シルバー)",
                "quantity": 12000,
                "unit": "本",
                "accessories": "高級フリント, 防風キャップ, ガス可視窓",
                "quality_requirements": "ISO 9994, PSC マーク (日本消費生活用製品安全法), JIS S 4801",
                "unit_price": "JPY 380",
                "notes": None,
            },
            {
                "sku": "LT-101 クラシック (Classic)",
                "color": "白色 (White / 白)",
                "quantity": 30000,
                "unit": "本",
                "accessories": "標準フリント",
                "quality_requirements": "ISO 9994, PSC マーク",
                "unit_price": "JPY 220",
                "notes": "会社ロゴ2色シルク印刷",
            },
        ],
    },
}


def _detect_demo_key(text: str) -> str:
    """Identify which sample the input matches by content keywords."""
    raw = text or ""
    t = raw.lower()
    if "東京ライティング" in raw or "tanaka" in t or "tl-2026-0518" in t or "発注書" in raw:
        return "ja"
    if "明辉" in raw or "广州明辉" in raw:
        return "zh"
    if "iberica" in t or "distribuidora" in t or "valencia" in t:
        return "es"
    if "acme" in t or "po-2026-0518" in t or "hamburg" in t:
        return "en"
    return "en"


# ---------------------------------------------------------------------------
# Real API path
# ---------------------------------------------------------------------------
def get_client() -> OpenAI:
    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        raise ValueError("DEEPSEEK_API_KEY is not set.")
    base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
    return OpenAI(api_key=api_key, base_url=base_url)


def parse_order_real(order_text: str, model: Optional[str] = None) -> dict:
    if not order_text or not order_text.strip():
        raise ValueError("Order text is empty.")
    client = get_client()
    model_name = model or os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
    response = client.chat.completions.create(
        model=model_name,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Parse the following order:\n\n{order_text}"},
        ],
        response_format={"type": "json_object"},
        temperature=0.1,
        max_tokens=4000,
    )
    return json.loads(response.choices[0].message.content or "{}")


# ---------------------------------------------------------------------------
# Demo path — looks like AI, no API call
# ---------------------------------------------------------------------------
def parse_order_demo(order_text: str = "", simulate_latency: bool = True) -> dict:
    """Return a pre-canned result that matches the sample text.

    Adds a small artificial delay so the spinner feels like real AI inference.
    """
    if simulate_latency:
        time.sleep(1.6)
    key = _detect_demo_key(order_text)
    return DEMO_RESULTS[key]


# ---------------------------------------------------------------------------
# Smart entry — auto chooses real vs demo
# ---------------------------------------------------------------------------
def parse_order(order_text: str, model: Optional[str] = None) -> dict:
    """Smart entry: real API if key is set, otherwise demo mode."""
    if os.getenv("DEEPSEEK_API_KEY"):
        return parse_order_real(order_text, model=model)
    return parse_order_demo(order_text)


def is_demo_mode() -> bool:
    """Whether the app is running without an API key (demo mode)."""
    return not os.getenv("DEEPSEEK_API_KEY")


# Back-compat alias kept for any existing imports
parse_order_mock = parse_order_demo
