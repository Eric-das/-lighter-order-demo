# -*- coding: utf-8 -*-
"""Parse factory capacity Excel files into normalized capacity master data.

Source files (E:\\项目\\Demo\\排产数据\\排产软件, provided by the factory 2026-07-08):

    加气产能.xlsx   gas-filling carts, one sheet per cart
    试火.xlsx       flame-test machines (流量机/明火机/无调火/手工试火)
    机检产能.xlsx   machine-inspection stations (检验机 only)
    手检产能.xlsx   manual inspection, per-model rates (9-person team)
    翻板产能.xlsx   flip-board lines
    包装产能.xlsx   packing machines (left table, units/8h)
    焊接产量.xls    welding shop, model × sub-operation

Output: data/capacity.json with per-machine records + per-(model, process)
aggregated daily capacity (conservative: lower bound of ranges).

Injection molding (注塑*.xlsx) is skipped — the workbooks are empty templates.

CLI:  python -m utils.capacity_loader [source_dir] [output_json]
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pandas as pd

DEFAULT_SOURCE = Path(r"E:\项目\Demo\排产数据\排产软件")
DEFAULT_OUTPUT = Path(__file__).resolve().parent.parent / "data" / "capacity.json"

# Process route in real production order (confirmed by the factory 2026-07-11):
# 焊接→加气→调火(试火)→翻板/组装→机检/手检→包装. 注塑 makes components on
# separate work orders and feeds the workshops, so it is not part of this route.
# 质检 pools 机检 + 手检; 翻板 covers 翻板/组装 (which one depends on product).
ROUTE = ["焊接", "加气", "试火", "翻板", "质检", "包装"]

_MODEL_RE = re.compile(r"^(\d{3,4})")


def normalize_model(token: str) -> str | None:
    """'908加长'→'908', '916B'→'916', '920铁'→'920'; None if not a model."""
    token = re.sub(r"[（(].*?[)）]", "", str(token)).strip()
    m = _MODEL_RE.match(token)
    return m.group(1) if m else None


def split_models(cell: str) -> list[str]:
    """'906&916' / '906/916' / '128/604' → ['906','916'] etc."""
    out = []
    for part in re.split(r"[/&、,，]", str(cell)):
        model = normalize_model(part)
        if model:
            out.append(model)
    return out


def parse_capacity_value(raw) -> tuple[float, float] | None:
    """'15000-18000'→(15000,18000); '80000'→(80000,80000); '20000+'→(20000,20000).

    Handles the '3-40000' typo pattern (low missing zeros) by scaling the low
    bound up to the high bound's magnitude: → (30000, 40000).
    """
    if raw is None or (isinstance(raw, float) and pd.isna(raw)):
        return None
    if isinstance(raw, (int, float)):
        return (float(raw), float(raw))
    s = str(raw).replace(",", "").replace("+", "").strip()
    s = re.sub(r"^合计", "", s)
    m = re.match(r"^(\d+(?:\.\d+)?)\s*[-~—]\s*(\d+(?:\.\d+)?)$", s)
    if m:
        low, high = float(m.group(1)), float(m.group(2))
        if 0 < low < high / 100:  # '3-40000' style typo: pad to same magnitude
            while len(str(int(low))) < len(str(int(high))):
                low *= 10
        return (low, high)
    m = re.match(r"^(\d+(?:\.\d+)?)$", s)
    if m:
        v = float(m.group(1))
        return (v, v)
    return None


def _record(process, machine, model, cap, staff=None, note=None):
    low, high = cap
    return {
        "process": process,
        "machine": str(machine).strip(),
        "model": model,
        "cap_low": low,
        "cap_high": high,
        "staff": staff,
        "note": note,
    }


# ---------------------------------------------------------------- 加气
def parse_gas(path: Path) -> list[dict]:
    records = []
    xls = pd.ExcelFile(path)
    for sheet in xls.sheet_names:
        df = pd.read_excel(xls, sheet_name=sheet, header=None)
        if sheet == "手工加气":
            # two side-by-side tables: cols (0,1) and (3,4)
            for c_model, c_cap, machine in ((0, 1, "16/17号车"), (3, 4, "18号车")):
                for _, row in df.iterrows():
                    model = normalize_model(row.get(c_model, ""))
                    cap = parse_capacity_value(row.get(c_cap))
                    if model and cap:
                        records.append(_record("加气", f"手工加气{machine}", model, cap, staff=1))
            continue
        for _, row in df.iterrows():
            model = normalize_model(row.get(0, ""))
            cap = parse_capacity_value(row.get(2))
            if model and cap:
                staff = row.get(3)
                records.append(_record("加气", sheet, model, cap,
                                       staff=int(staff) if pd.notna(staff) else None))
    return records


# ---------------------------------------------------------------- 试火
_FLAME_MACHINE_RE = re.compile(r"^(流量机|明火机|无调火|手工试火)")


def parse_flame(path: Path) -> list[dict]:
    records = []
    df = pd.read_excel(path, sheet_name=0, header=None)
    machine, cap = None, None
    for _, row in df.iterrows():
        cell0 = str(row.get(0)).strip() if pd.notna(row.get(0)) else ""
        if cell0 and not _FLAME_MACHINE_RE.match(cell0) and cell0 not in ("·", ""):
            # left a supported section (干检/打头/看表面/日期...) — reset
            machine, cap = None, None
        if _FLAME_MACHINE_RE.match(cell0):
            machine = cell0
            cap = parse_capacity_value(row.get(1)) or cap
        if machine is None:
            continue
        model = normalize_model(row.get(2, ""))
        if model and cap:
            note = str(row.get(3)).strip() if pd.notna(row.get(3)) else None
            records.append(_record("试火", machine, model, cap, note=note))
    return records


# ---------------------------------------------------------------- 机检
def parse_machine_inspect(path: Path) -> list[dict]:
    records = []
    df = pd.read_excel(path, sheet_name=0, header=None)
    for _, row in df.iterrows():
        machine = str(row.get(0)).strip() if pd.notna(row.get(0)) else ""
        if "检验机" not in machine:
            continue
        cap = parse_capacity_value(row.get(2))
        if not cap:
            continue
        for model in split_models(row.get(1, "")):
            records.append(_record("质检", machine, model, cap, note="机检"))
    return records


# ---------------------------------------------------------------- 手检
def parse_manual_inspect(path: Path) -> list[dict]:
    records = []
    df = pd.read_excel(path, sheet_name=0, header=None)
    best: dict[str, tuple[float, float]] = {}
    for _, row in df.iterrows():
        model = normalize_model(row.get(0, ""))
        cap = parse_capacity_value(row.get(3))  # 抽检产能（9人）
        if not (model and cap):
            continue
        # variants (919A-D, 720轻/重) map to one model: keep the conservative min
        if model not in best or cap[0] < best[model][0]:
            best[model] = cap
    for model, cap in best.items():
        records.append(_record("质检", "手检(9人)", model, cap, staff=9, note="手检"))
    return records


# ---------------------------------------------------------------- 翻板
def parse_flip(path: Path) -> list[dict]:
    records = []
    df = pd.read_excel(path, sheet_name=0, header=None)
    line = None
    for _, row in df.iterrows():
        cell0 = str(row.get(0)).strip() if pd.notna(row.get(0)) else ""
        if cell0 == "穿弹簧机器":
            break  # sub-tables below are component ops, out of scope
        if cell0:
            line = cell0
        raw_model = str(row.get(1)).strip() if pd.notna(row.get(1)) else ""
        if raw_model.endswith("壳") or raw_model in ("备用", "型号", ""):
            continue  # component-only or header rows
        model = normalize_model(raw_model)
        cap = parse_capacity_value(row.get(3))
        if model and cap and line:
            note = str(row.get(4)).strip() if pd.notna(row.get(4)) else None
            records.append(_record("翻板", line, model, cap, staff=4, note=note))
    return records


# ---------------------------------------------------------------- 包装
def parse_packing(path: Path) -> list[dict]:
    records = []
    df = pd.read_excel(path, sheet_name=0, header=None)
    machine = None
    for _, row in df.iterrows():
        cell0 = str(row.get(0)).strip() if pd.notna(row.get(0)) else ""
        if cell0 and cell0 not in ("·", "机台"):
            machine = cell0
        if machine is None or machine == "点珠机":
            continue
        raw_model = str(row.get(1)).strip() if pd.notna(row.get(1)) else ""
        cap_raw = row.get(2)
        if isinstance(cap_raw, str) and "/" in cap_raw:
            # '45000/35000' (3人/2人 modes) → conservative min
            parts = [parse_capacity_value(p) for p in cap_raw.split("/")]
            parts = [p for p in parts if p]
            cap = min(parts, key=lambda c: c[0]) if parts else None
        else:
            cap = parse_capacity_value(cap_raw)
        if not cap:
            continue
        if raw_model == "通用":
            records.append(_record("包装", machine, "通用", cap, note="通用机台池"))
            continue
        model = normalize_model(raw_model)
        if model:
            staff_m = re.search(r"\d+", str(row.get(3, "")))
            records.append(_record("包装", machine, model, cap,
                                   staff=int(staff_m.group()) if staff_m else None))
    return records


# ---------------------------------------------------------------- 焊接
def parse_welding(path: Path) -> list[dict]:
    df = pd.read_excel(path, sheet_name=0, header=None)
    # bottleneck per model = min capacity across that model's sub-operations
    bottleneck: dict[str, tuple[float, str]] = {}
    for _, row in df.iterrows():
        name = str(row.get(0)).strip() if pd.notna(row.get(0)) else ""
        cap = parse_capacity_value(row.get(1))
        if not name or not cap or "灭烛器" in name:  # accessory, not the lighter
            continue
        models = split_models(name)
        if not models:
            continue
        for model in models:
            if model not in bottleneck or cap[0] < bottleneck[model][0]:
                bottleneck[model] = (cap[0], name)
    return [
        _record("焊接", op_name, model, (low, low), note="瓶颈子工序")
        for model, (low, op_name) in bottleneck.items()
    ]


# ---------------------------------------------------------------- aggregate
def build_capacity(source_dir: Path) -> dict:
    records = []
    records += parse_gas(source_dir / "加气产能.xlsx")
    records += parse_flame(source_dir / "试火.xlsx")
    records += parse_machine_inspect(source_dir / "机检产能.xlsx")
    records += parse_manual_inspect(source_dir / "手检产能.xlsx")
    records += parse_flip(source_dir / "翻板产能.xlsx")
    records += parse_packing(source_dir / "包装产能.xlsx")
    records += parse_welding(source_dir / "焊接产量.xls")

    # one machine may appear with several modes/rows for the same model —
    # dedupe on (process, machine, model) keeping the conservative min
    deduped: dict[tuple, float] = {}
    for r in records:
        key = (r["process"], r["machine"], r["model"])
        if key not in deduped or r["cap_low"] < deduped[key]:
            deduped[key] = r["cap_low"]

    capacity: dict[str, dict[str, float]] = {}
    universal_packing = 0.0
    for (process, _machine, model), cap_low in deduped.items():
        if model == "通用":
            universal_packing += cap_low
            continue
        capacity.setdefault(model, {})
        capacity[model][process] = capacity[model].get(process, 0.0) + cap_low

    return {
        "meta": {
            "source": str(source_dir),
            "workday_hours": 8,
            "route": ROUTE,
            "caveats": [
                "产能取区间下限(保守)",
                "工序级汇总: 同一台机器登记的多个型号按各自可用产能计入,未建模跨型号争用",
                "注塑为空模板未纳入; 打头/穿弹簧/干检等子工序未纳入",
                "包装'通用'机台单列为 universal_packing_pool,型号无专用包装机时可用",
            ],
        },
        "records": records,
        "capacity": capacity,
        "universal_packing_pool": universal_packing,
    }


def main():
    source = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_SOURCE
    output = Path(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_OUTPUT
    data = build_capacity(source)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    models = sorted(data["capacity"])
    print(f"models: {len(models)} -> {output}")
    header = ["model"] + ROUTE
    print(" | ".join(f"{h:>8}" for h in header))
    for model in models:
        row = [model] + [
            str(int(data["capacity"][model].get(p, 0))) for p in ROUTE
        ]
        print(" | ".join(f"{v:>8}" for v in row))
    print(f"universal packing pool: {int(data['universal_packing_pool'])}")


if __name__ == "__main__":
    main()
