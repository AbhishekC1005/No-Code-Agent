"""
Logic Nodes implementation (n8n-style):
- IF: splits items into true (port 0) and false (port 1) branches
- Switch: routes items across N outputs based on rules
- Merge: combines items from multiple incoming edges
- Loop Over Items: iterates items one-by-one or in batches, routing to loop (0) or done (1)
- Wait: delays execution
- Set: adds/updates fields on each item's JSON
- Stop and Error: halts execution with an error
"""

import asyncio
from typing import Any

from .expressions import ExpressionContext, evaluate_string, evaluate_value
from .models import make_item, ensure_item_list


async def execute_if_node(
    cfg: dict[str, Any],
    items: list[dict[str, Any]],
    node_context: dict[str, Any],
) -> dict[int | str, list[dict[str, Any]]]:
    """
    IF node: routes items to port 0 (True) or port 1 (False).
    Supports either direct expression string or condition rules.
    """
    true_items: list[dict[str, Any]] = []
    false_items: list[dict[str, Any]] = []

    expr = cfg.get("expression") or cfg.get("condition")

    for item in items:
        ctx = ExpressionContext(
            current_item=item,
            all_items=items,
            node_outputs=node_context,
        )

        is_true = False

        if expr:
            # If expression given e.g. "{{ $json.total > 100 }}"
            res = evaluate_string(expr, ctx) if isinstance(expr, str) else expr
            is_true = bool(res)
        else:
            # Check structured conditions: field1, operation, field2
            val1_raw = cfg.get("value1") or cfg.get("conditionField")
            op = cfg.get("operation", "equals")
            val2_raw = cfg.get("value2")

            val1 = evaluate_value(val1_raw, ctx) if val1_raw is not None else item.get("json", {}).get(str(val1_raw))
            val2 = evaluate_value(val2_raw, ctx) if val2_raw is not None else None

            if op in ("equals", "eq", "=="):
                is_true = (val1 == val2)
            elif op in ("notEquals", "ne", "!="):
                is_true = (val1 != val2)
            elif op in ("contains", "in"):
                is_true = (str(val2) in str(val1)) if val1 is not None and val2 is not None else False
            elif op in ("notContains", "not_in"):
                is_true = (str(val2) not in str(val1)) if val1 is not None and val2 is not None else False
            elif op in ("greaterThan", "gt", ">"):
                try:
                    is_true = float(val1) > float(val2)
                except Exception:
                    is_true = False
            elif op in ("lessThan", "lt", "<"):
                try:
                    is_true = float(val1) < float(val2)
                except Exception:
                    is_true = False
            elif op in ("isEmpty", "empty"):
                is_true = (val1 is None or val1 == "" or val1 == [] or val1 == {})
            elif op in ("isNotEmpty", "not_empty"):
                is_true = not (val1 is None or val1 == "" or val1 == [] or val1 == {})
            else:
                is_true = bool(val1)

        if is_true:
            true_items.append(item)
        else:
            false_items.append(item)

    return {0: true_items, 1: false_items}


async def execute_switch_node(
    cfg: dict[str, Any],
    items: list[dict[str, Any]],
    node_context: dict[str, Any],
) -> dict[int | str, list[dict[str, Any]]]:
    """
    Switch node: routes items across N outputs based on rules.
    rules: list of {"expression": "...", "output": 0}
    fallback: default port index (e.g. len(rules))
    """
    rules = cfg.get("rules", [])
    fallback_output = int(cfg.get("fallbackOutput", len(rules)))

    ports: dict[int | str, list[dict[str, Any]]] = {}
    for i in range(len(rules) + 1):
        ports[i] = []

    for item in items:
        ctx = ExpressionContext(
            current_item=item,
            all_items=items,
            node_outputs=node_context,
        )

        matched = False
        for idx, rule in enumerate(rules):
            expr = rule.get("expression") or rule.get("condition")
            if expr:
                res = evaluate_string(expr, ctx) if isinstance(expr, str) else expr
                if bool(res):
                    target_port = int(rule.get("output", idx))
                    ports.setdefault(target_port, []).append(item)
                    matched = True
                    break

        if not matched:
            ports.setdefault(fallback_output, []).append(item)

    return ports


async def execute_merge_node(
    cfg: dict[str, Any],
    input_item_groups: list[list[dict[str, Any]]],
) -> dict[int | str, list[dict[str, Any]]]:
    """
    Merge node: combines multiple incoming edge outputs.
    Modes:
      - 'append': concatenates all incoming items
      - 'combine': merges matching index items by merging their JSON dicts
      - 'pass_through': only takes the first non-empty input
    """
    mode = cfg.get("mode", "append")

    if not input_item_groups:
        return {0: [make_item({})]}

    if mode == "combine":
        merged: list[dict[str, Any]] = []
        max_len = max(len(grp) for grp in input_item_groups)
        for i in range(max_len):
            combined_json: dict[str, Any] = {}
            for grp in input_item_groups:
                if i < len(grp):
                    combined_json.update(grp[i].get("json", {}))
            merged.append(make_item(combined_json))
        return {0: merged}

    elif mode == "pass_through":
        for grp in input_item_groups:
            if grp:
                return {0: grp}
        return {0: [make_item({})]}

    else:
        # Default: append / concatenate
        all_items = []
        for grp in input_item_groups:
            all_items.extend(grp)
        return {0: all_items if all_items else [make_item({})]}


async def execute_loop_node(
    cfg: dict[str, Any],
    items: list[dict[str, Any]],
    loop_state: dict[str, Any],
) -> dict[int | str, list[dict[str, Any]]]:
    """
    Loop Over Items node:
    Iterates items in batches (default batchSize=1).
    Port 0: loop branch (batch of items to process)
    Port 1: done branch (emitted when all items finished)
    """
    batch_size = max(1, int(cfg.get("batchSize", 1)))
    current_index = loop_state.get("index", 0)

    if current_index < len(items):
        batch = items[current_index : current_index + batch_size]
        loop_state["index"] = current_index + batch_size
        return {0: batch, 1: []}
    else:
        # Reset for future runs and emit to done port
        loop_state["index"] = 0
        return {0: [], 1: items}


async def execute_wait_node(
    cfg: dict[str, Any],
    items: list[dict[str, Any]],
) -> dict[int | str, list[dict[str, Any]]]:
    """Wait node: delays execution for specified amount of time."""
    amount = float(cfg.get("amount", 1))
    unit = cfg.get("unit", "seconds").lower()

    if unit in ("ms", "milliseconds"):
        seconds = amount / 1000.0
    elif unit in ("minutes", "mins", "m"):
        seconds = amount * 60.0
    else:
        seconds = amount

    # Cap wait time to prevent unbounded hangs
    seconds = max(0.0, min(seconds, 300.0))
    if seconds > 0:
        await asyncio.sleep(seconds)

    return {0: items}


async def execute_set_node(
    cfg: dict[str, Any],
    items: list[dict[str, Any]],
    node_context: dict[str, Any],
) -> dict[int | str, list[dict[str, Any]]]:
    """
    Set (Edit Fields) node:
    Adds, updates, or replaces fields in each item's JSON.
    Values can use {{ $json.x }} expressions.
    keepOnlySet: if True, removes all fields not explicitly configured.
    """
    fields_spec = cfg.get("fields") or cfg.get("values") or {}
    keep_only_set = bool(cfg.get("keepOnlySet", False))

    output_items: list[dict[str, Any]] = []

    for item in items:
        ctx = ExpressionContext(
            current_item=item,
            all_items=items,
            node_outputs=node_context,
        )

        base_json = {} if keep_only_set else dict(item.get("json", {}))

        if isinstance(fields_spec, dict):
            for k, v in fields_spec.items():
                evaluated_val = evaluate_value(v, ctx)
                base_json[k] = evaluated_val
        elif isinstance(fields_spec, list):
            # List of {"name": "foo", "value": "bar"}
            for entry in fields_spec:
                if isinstance(entry, dict) and "name" in entry:
                    name = str(evaluate_value(entry["name"], ctx))
                    val = evaluate_value(entry.get("value"), ctx)
                    base_json[name] = val

        output_items.append(make_item(base_json))

    return {0: output_items}


async def execute_stop_and_error_node(
    cfg: dict[str, Any],
    items: list[dict[str, Any]],
    node_context: dict[str, Any],
):
    """Stop and Error node: halts execution and throws a configured error."""
    ctx = ExpressionContext(
        current_item=items[0] if items else make_item({}),
        all_items=items,
        node_outputs=node_context,
    )
    raw_msg = cfg.get("errorMessage") or cfg.get("message") or "Workflow explicitly stopped by Stop and Error node."
    msg = evaluate_string(str(raw_msg), ctx)
    raise RuntimeError(msg)
