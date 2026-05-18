"""Lighter Order Parser — Streamlit demo.

Run locally:
    streamlit run app.py
"""
import io
import json
import os
from pathlib import Path

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

from agents.order_parser import parse_order
from utils.file_loader import load_text_from_file
from utils.i18n import t

load_dotenv()


# ---------- Page config ----------
st.set_page_config(
    page_title="Lighter Order Parser",
    page_icon="🔥",
    layout="wide",
    initial_sidebar_state="collapsed",
)


# ---------- Sidebar: language ----------
_LANG_LABELS = {"zh": "中文", "en": "English", "ja": "日本語"}
_ABOUT_TEXT = {
    "zh": ("**关于**", "打火机厂商销售订单 AI 自动解析流水线 Demo。"),
    "en": ("**About**", "Demo of an AI-powered sales-order parsing pipeline for a lighter manufacturer."),
    "ja": ("**概要**", "ライターメーカー向け、注文書をAIで自動解析するパイプラインのデモです。"),
}
with st.sidebar:
    lang = st.radio(
        "🌐 Language / 语言 / 言語",
        options=["zh", "en", "ja"],
        format_func=lambda x: _LANG_LABELS[x],
        horizontal=True,
        index=0,
    )
    st.divider()
    _title, _body = _ABOUT_TEXT[lang]
    st.markdown(_title)
    st.caption(_body)


# ---------- Header ----------
st.title(t(lang, "title"))
st.caption(t(lang, "subtitle"))


# ---------- Tabs ----------
tab1, tab2, tab3, tab4 = st.tabs([
    t(lang, "tab_upload"),
    t(lang, "tab_shipping"),
    t(lang, "tab_production"),
    t(lang, "tab_exception"),
])


# ===== Tab 1: Order Import =====
with tab1:
    col_left, col_right = st.columns([1, 1], gap="large")

    # ----- Left: input -----
    with col_left:
        st.subheader(t(lang, "input_method"))
        method = st.radio(
            label="method",
            options=["upload", "paste", "sample"],
            format_func=lambda x: {
                "upload": t(lang, "method_upload"),
                "paste": t(lang, "method_paste"),
                "sample": t(lang, "method_sample"),
            }[x],
            label_visibility="collapsed",
            horizontal=True,
        )

        order_text = ""

        if method == "upload":
            uploaded = st.file_uploader(
                t(lang, "upload_label"),
                type=["pdf", "xlsx", "xls", "csv", "txt"],
            )
            if uploaded is not None:
                try:
                    order_text = load_text_from_file(uploaded)
                    with st.expander(t(lang, "preview_label"), expanded=False):
                        preview = order_text[:2000]
                        if len(order_text) > 2000:
                            preview += "\n...[truncated]"
                        st.code(preview)
                except Exception as e:
                    st.error(f"{t(lang, 'file_load_fail')}: {e}")

        elif method == "paste":
            order_text = st.text_area(
                t(lang, "paste_label"),
                height=380,
                placeholder="From: customer@example.com\nSubject: PO-12345\n...",
            )

        else:  # sample
            samples_dir = Path(__file__).parent / "samples"
            sample_files = sorted(samples_dir.glob("*.txt"))
            labels = {f.name: f for f in sample_files}
            chosen = st.selectbox(
                t(lang, "sample_label"),
                options=list(labels.keys()),
            )
            if chosen:
                order_text = labels[chosen].read_text(encoding="utf-8")
                with st.expander(t(lang, "preview_label"), expanded=True):
                    st.code(order_text)

        # ----- Action button -----
        do_parse = st.button(
            t(lang, "btn_parse"),
            type="primary",
            use_container_width=True,
            disabled=not order_text,
        )

    # ----- Right: parsing result -----
    with col_right:
        if do_parse and order_text:
            try:
                with st.spinner(t(lang, "parsing")):
                    result = parse_order(order_text)
                st.session_state["parse_result"] = result
                st.success(t(lang, "parse_success"))
            except Exception as e:
                st.session_state["parse_result"] = None
                st.error(f"{t(lang, 'parse_fail')}: {e}")

        result = st.session_state.get("parse_result")

        if not result:
            st.info(t(lang, "result_empty"))
        else:
            # ---- Order meta ----
            st.subheader(t(lang, "order_meta"))
            meta = result.get("order_meta") or {}
            mc1, mc2, mc3 = st.columns(3)
            with mc1:
                customer = st.text_input(t(lang, "field_customer"), value=meta.get("customer") or "")
                po = st.text_input(t(lang, "field_po"), value=meta.get("po_number") or "")
                payment = st.text_input(t(lang, "field_payment"), value=meta.get("payment_terms") or "")
            with mc2:
                contact = st.text_input(t(lang, "field_contact"), value=meta.get("contact") or "")
                delivery = st.text_input(t(lang, "field_delivery"), value=meta.get("requested_delivery") or "")
                destination = st.text_input(t(lang, "field_destination"), value=meta.get("destination") or "")
            with mc3:
                email = st.text_input(t(lang, "field_email"), value=meta.get("email") or "")
                incoterms = st.text_input(t(lang, "field_incoterms"), value=meta.get("incoterms") or "")
                notes = st.text_input(t(lang, "field_notes"), value=meta.get("notes") or "")

            # ---- Line items ----
            st.subheader(t(lang, "line_items"))
            lines = result.get("line_items") or []
            if lines:
                df = pd.DataFrame(lines)
            else:
                df = pd.DataFrame(
                    columns=["sku", "color", "quantity", "unit", "accessories",
                             "quality_requirements", "unit_price", "notes"]
                )

            edited = st.data_editor(
                df,
                use_container_width=True,
                num_rows="dynamic",
                key="line_editor",
            )

            # ---- Export ----
            final = {
                "order_meta": {
                    "customer": customer or None,
                    "contact": contact or None,
                    "email": email or None,
                    "po_number": po or None,
                    "requested_delivery": delivery or None,
                    "incoterms": incoterms or None,
                    "destination": destination or None,
                    "payment_terms": payment or None,
                    "notes": notes or None,
                    "original_language": meta.get("original_language"),
                },
                "line_items": edited.to_dict(orient="records"),
            }

            ec1, ec2 = st.columns(2)
            with ec1:
                st.download_button(
                    t(lang, "btn_export_json"),
                    data=json.dumps(final, ensure_ascii=False, indent=2).encode("utf-8"),
                    file_name="order_parsed.json",
                    mime="application/json",
                    use_container_width=True,
                )
            with ec2:
                buf = io.BytesIO()
                with pd.ExcelWriter(buf, engine="openpyxl") as writer:
                    pd.DataFrame([final["order_meta"]]).to_excel(writer, sheet_name="meta", index=False)
                    edited.to_excel(writer, sheet_name="line_items", index=False)
                st.download_button(
                    t(lang, "btn_export_excel"),
                    data=buf.getvalue(),
                    file_name="order_parsed.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True,
                )

            st.info(t(lang, "next_step_hint"))


# ===== Tab 2-4: placeholders =====
_PLACEHOLDER = {
    "tab_shipping": {
        "zh": "- 自动按客户要求交期、运输方式（海运/空运）排出未来 30 天发货计划\n"
              "- 考虑打火机危险品 (UN1057) 船期约束\n"
              "- 倒推每个订单行的最晚完工日",
        "en": "- Auto-generate a 30-day shipping plan from required delivery + mode (sea/air)\n"
              "- Account for dangerous-goods (UN1057) sailing constraints\n"
              "- Back-calculate latest completion date for each line",
        "ja": "- お客様の希望納期と輸送方法 (海運/空運) に基づき、今後30日間の出荷計画を自動生成\n"
              "- ライターは危険物 (UN1057) のため、船積み制約を考慮\n"
              "- 各注文明細の最遅完成日を逆算",
    },
    "tab_production": {
        "zh": "- 根据 SKU 查工艺路线 (BOM + Routing)\n"
              "- 按最晚完工日倒排到每道工序 (注塑→装配→充气→印刷→QC→包装)\n"
              "- 考虑产线产能、瓶颈工序、物料齐套",
        "en": "- Look up routing (BOM + work centers) by SKU\n"
              "- Back-schedule each operation (molding→assembly→gas-fill→printing→QC→packing)\n"
              "- Account for capacity, bottleneck work centers, material coverage",
        "ja": "- SKUごとに工程ルート (BOM + 工程) を参照\n"
              "- 最遅完成日から各工程 (成形→組立→ガス充填→印刷→検査→梱包) を逆スケジューリング\n"
              "- ライン能力、ボトルネック工程、部材手配状況を考慮",
    },
    "tab_exception": {
        "zh": "- 异常列表 (型号不存在 / 产能不足 / 物料缺料 / 交期不可达)\n"
              "- 一键起草客户邮件确认改型号或改交期",
        "en": "- Exception list (unknown SKU / capacity short / material short / unachievable date)\n"
              "- One-click email draft to the customer to reconfirm spec or date",
        "ja": "- 例外リスト (型番不明 / 能力不足 / 部材欠品 / 納期不可)\n"
              "- お客様への型番・納期再確認メールをワンクリックで起案",
    },
}

with tab2:
    st.info(t(lang, "tab_coming_soon"))
    st.markdown(_PLACEHOLDER["tab_shipping"][lang])

with tab3:
    st.info(t(lang, "tab_coming_soon"))
    st.markdown(_PLACEHOLDER["tab_production"][lang])

with tab4:
    st.info(t(lang, "tab_coming_soon"))
    st.markdown(_PLACEHOLDER["tab_exception"][lang])


# ---------- Footer ----------
st.divider()
st.caption(t(lang, "footer"))
