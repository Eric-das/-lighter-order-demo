# -*- coding: utf-8 -*-
"""Process-level production scheduler (rough-cut capacity planning).

Model: each order flows through the process route (焊接→翻板→加气→试火→质检→包装).
Per (process, model, day) there is a daily capacity pool shared by all orders;
orders are allocated greedily in EDD (earliest due date) order. A unit can pass
through at most one process per day (conservative one-day transfer batching).

Capacity semantics:
- capacity numbers come from data/capacity.json (units per 8h day, conservative)
- a missing/zero capacity entry means NO DATA for that (model, process) —
  treated as unconstrained, reported as a warning, NOT as infeasible
- unknown model: order is not scheduled, reported as an error
- overtime_factor scales all capacities (1.5 = 12h days, etc.)
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path

DEFAULT_CAPACITY_JSON = Path(__file__).resolve().parent.parent / "data" / "capacity.json"


def load_capacity(path: Path | str = DEFAULT_CAPACITY_JSON) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


@dataclass
class OrderInput:
    order_id: str
    model: str
    quantity: int
    due_date: date


@dataclass
class OrderResult:
    order_id: str
    model: str
    quantity: int
    due_date: date
    completion_date: date | None  # None => not finished within horizon
    status: str                   # ok / late / unfinished / unknown_model
    warnings: list[str] = field(default_factory=list)


@dataclass
class ScheduleResult:
    orders: list[OrderResult]
    plan: list[dict]         # {date, process, model, order_id, qty}
    load: dict               # {(process, day_index): {"used": x, "cap": y}}
    horizon_days: int
    start_date: date


def schedule(
    orders: list[OrderInput],
    capacity_data: dict,
    start_date: date,
    horizon_days: int = 30,
    overtime_factor: float = 1.0,
    rest_weekday: int | None = None,  # e.g. 6 = no work on Sundays
) -> ScheduleResult:
    route: list[str] = capacity_data["meta"]["route"]
    capacity: dict = capacity_data["capacity"]
    universal_packing = float(capacity_data.get("universal_packing_pool", 0))

    days = [start_date + timedelta(days=i) for i in range(horizon_days)]
    workday = [rest_weekday is None or d.weekday() != rest_weekday for d in days]

    # remaining capacity pools, filled lazily per (process, model)
    remaining: dict[tuple, list[float]] = {}
    # 包装 has a shared pool of universal machines on top of dedicated ones
    universal_pool = [
        universal_packing * overtime_factor if workday[i] else 0.0
        for i in range(horizon_days)
    ]
    # aggregated load for the utilization view (per process/day over ALL models)
    load: dict[tuple, dict] = {}

    def get_pool(process: str, model: str) -> list[float] | None:
        """Daily remaining dedicated capacity; None => unconstrained (no data)."""
        cap = capacity.get(model, {}).get(process, 0)
        if not cap:
            return None
        key = (process, model)
        if key not in remaining:
            remaining[key] = [
                cap * overtime_factor if workday[i] else 0.0
                for i in range(horizon_days)
            ]
        return remaining[key]

    results: list[OrderResult] = []
    plan: list[dict] = []

    for order in sorted(orders, key=lambda o: (o.due_date, o.order_id)):
        if order.model not in capacity:
            results.append(OrderResult(
                order.order_id, order.model, order.quantity, order.due_date,
                None, "unknown_model",
                [f"型号 {order.model} 不在产能主数据中"],
            ))
            continue

        warnings = []
        # cum_avail[d] = units that have finished the previous process by end of day d
        cum_avail = [float(order.quantity)] * horizon_days
        first_constrained = True

        for process in route:
            pool = get_pool(process, order.model)
            shared = universal_pool if process == "包装" and universal_packing else None
            if pool is None and shared is None:
                warnings.append(f"{process}: 无产能数据,按无约束处理")
                # data gap: pass through instantly (cum_avail unchanged)
                continue
            if pool is None and process == "包装":
                warnings.append("包装: 无专用机台,使用通用包装池")
            cum_done = 0.0
            new_cum = [0.0] * horizon_days
            for i in range(horizon_days):
                if first_constrained:
                    upstream = cum_avail[i]
                else:
                    # transfer batching: today we can only process what the
                    # previous process finished by END of YESTERDAY
                    upstream = cum_avail[i - 1] if i > 0 else 0.0
                avail = upstream - cum_done
                cap_today = (pool[i] if pool is not None else 0.0) + \
                    (shared[i] if shared is not None else 0.0)
                do = min(avail, cap_today)
                if do > 0:
                    # consume dedicated machines first, then the shared pool
                    from_dedicated = min(do, pool[i]) if pool is not None else 0.0
                    if pool is not None:
                        pool[i] -= from_dedicated
                    if shared is not None:
                        shared[i] -= do - from_dedicated
                    cum_done += do
                    plan.append({
                        "date": days[i], "process": process,
                        "model": order.model, "order_id": order.order_id,
                        "qty": int(round(do)),
                    })
                    lkey = (process, i)
                    load.setdefault(lkey, {"used": 0.0, "cap": 0.0})
                    load[lkey]["used"] += do
                new_cum[i] = cum_done
            cum_avail = new_cum
            first_constrained = False

        finished = cum_avail[-1] >= order.quantity - 0.5
        completion = None
        if finished:
            for i in range(horizon_days):
                if cum_avail[i] >= order.quantity - 0.5:
                    completion = days[i]
                    break
        if not finished:
            status = "unfinished"
        elif completion and completion > order.due_date:
            status = "late"
        else:
            status = "ok"
        results.append(OrderResult(
            order.order_id, order.model, order.quantity, order.due_date,
            completion, status, warnings,
        ))

    # attach daily cap to load view (sum of pools actually used that day)
    for (process, i), entry in load.items():
        total_cap = 0.0
        for (p, model), pool in remaining.items():
            if p == process:
                total_cap += capacity[model][process] * overtime_factor if workday[i] else 0.0
        entry["cap"] = total_cap

    return ScheduleResult(results, plan, load, horizon_days, start_date)
