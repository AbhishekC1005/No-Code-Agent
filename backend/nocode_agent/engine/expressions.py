"""
Safe Expression Evaluator for No-Code Agent (n8n-style).
Evaluates {{ $json.field }}, {{ $node["Label"].json.field }}, {{ $input.all() }}, {{ $env.VAR }}, etc.
STRICTLY NO eval() or exec() — uses AST validation and safe attribute/subscript resolution.
"""

import ast
import os
import re
from typing import Any


class SafeExpressionError(Exception):
    """Raised when an expression is invalid or violates safety rules."""
    pass


class ExpressionContext:
    """Holds variables available during expression evaluation."""

    def __init__(
        self,
        current_item: dict[str, Any] | None = None,
        all_items: list[dict[str, Any]] | None = None,
        node_outputs: dict[str, Any] | None = None,
        env_vars: dict[str, str] | None = None,
    ):
        self.current_item = current_item or {}
        self.all_items = all_items or ([self.current_item] if current_item else [])
        self.node_outputs = node_outputs or {}
        self.env_vars = env_vars if env_vars is not None else os.environ

    def get_json(self) -> dict[str, Any]:
        """Returns the current item's 'json' dict."""
        if "json" in self.current_item and isinstance(self.current_item["json"], dict):
            return self.current_item["json"]
        return self.current_item

    def get_input(self) -> "InputProxy":
        """Returns an InputProxy supporting .all(), .first(), .item."""
        return InputProxy(self.all_items, self.get_json())

    def get_node(self) -> "NodeOutputProxy":
        """Returns a proxy to access upstream node outputs by name or ID."""
        return NodeOutputProxy(self.node_outputs)

    def get_env(self) -> "EnvProxy":
        """Returns a proxy to access environment variables."""
        return EnvProxy(self.env_vars)


class InputProxy:
    """Proxy object for $input: supports $input.all(), $input.first(), $input.item."""

    def __init__(self, items: list[dict[str, Any]], current_json: dict[str, Any]):
        self._items = items
        self.item = current_json

    def all(self) -> list[Any]:
        """Return all items' json data."""
        res = []
        for it in self._items:
            if isinstance(it, dict) and "json" in it:
                res.append(it["json"])
            else:
                res.append(it)
        return res

    def first(self) -> Any:
        """Return the first item's json data or empty dict."""
        all_res = self.all()
        return all_res[0] if all_res else {}

    def __len__(self) -> int:
        return len(self._items)

    def __getitem__(self, idx: int) -> Any:
        all_res = self.all()
        return all_res[idx]


class NodeOutputProxy:
    """Proxy object for $node['Label'].json.field."""

    def __init__(self, node_outputs: dict[str, Any]):
        # node_outputs can map node_id -> items and node_label -> items
        self._outputs = node_outputs

    def __getitem__(self, key: str) -> "SingleNodeProxy":
        data = self._outputs.get(key)
        if data is None:
            # Try case-insensitive or stripped
            for k, v in self._outputs.items():
                if k.lower() == key.lower():
                    data = v
                    break
        return SingleNodeProxy(data or [])

    def get(self, key: str, default: Any = None) -> Any:
        try:
            return self[key]
        except Exception:
            return default


class SingleNodeProxy:
    """Proxy for a specific node's output: $node['Name'].json or $node['Name'].all()."""

    def __init__(self, items: list[dict[str, Any]]):
        self._items = items if isinstance(items, list) else [items]

    @property
    def json(self) -> dict[str, Any]:
        """First item's JSON."""
        if self._items and isinstance(self._items[0], dict):
            return self._items[0].get("json", self._items[0])
        return {}

    def all(self) -> list[Any]:
        res = []
        for it in self._items:
            if isinstance(it, dict) and "json" in it:
                res.append(it["json"])
            else:
                res.append(it)
        return res

    def first(self) -> Any:
        return self.json


class EnvProxy:
    """Proxy for $env: e.g. $env.OPENAI_API_KEY or $env['PORT']."""

    def __init__(self, env_dict: Any):
        self._env = env_dict

    def __getattr__(self, name: str) -> str:
        if name.startswith("_"):
            raise AttributeError(name)
        return self._env.get(name, "")

    def __getitem__(self, key: str) -> str:
        return self._env.get(key, "")

    def get(self, key: str, default: str = "") -> str:
        return self._env.get(key, default)


# ── AST-based Safe Evaluator ────────────────────────────────────────────────

ALLOWED_OPERATORS = {
    ast.Add: lambda a, b: a + b,
    ast.Sub: lambda a, b: a - b,
    ast.Mult: lambda a, b: a * b,
    ast.Div: lambda a, b: a / b if b != 0 else 0,
    ast.FloorDiv: lambda a, b: a // b if b != 0 else 0,
    ast.Mod: lambda a, b: a % b if b != 0 else 0,
    ast.Pow: lambda a, b: a ** b if b < 1000 else 0,
    ast.USub: lambda a: -a,
    ast.UAdd: lambda a: +a,
    ast.Not: lambda a: not a,
    ast.Eq: lambda a, b: a == b,
    ast.NotEq: lambda a, b: a != b,
    ast.Lt: lambda a, b: a < b,
    ast.LtE: lambda a, b: a <= b,
    ast.Gt: lambda a, b: a > b,
    ast.GtE: lambda a, b: a >= b,
    ast.In: lambda a, b: a in b,
    ast.NotIn: lambda a, b: a not in b,
    ast.Is: lambda a, b: a is b,
    ast.IsNot: lambda a, b: a is not b,
}

ALLOWED_METHOD_NAMES = {
    "all", "first", "get", "lower", "upper", "strip", "lstrip", "rstrip",
    "split", "join", "replace", "startswith", "endswith", "keys", "values",
    "items", "count", "index",
}


def _safe_resolve_attr(obj: Any, attr_name: str) -> Any:
    """Safely get an attribute or dictionary key without accessing dunder methods."""
    if attr_name.startswith("_"):
        raise SafeExpressionError(f"Access to private attribute '{attr_name}' is forbidden.")

    # If dict-like:
    if isinstance(obj, dict):
        if attr_name in obj:
            return obj[attr_name]
        return getattr(obj, attr_name, None)

    # If object:
    if hasattr(obj, attr_name):
        return getattr(obj, attr_name)

    return None


def _eval_ast_node(node: ast.AST, scope: dict[str, Any]) -> Any:
    """Recursively evaluate an AST expression node in a restricted sandbox."""
    if isinstance(node, ast.Constant):
        return node.value

    # Variable lookup: $json, $item, $input, $node, $env, etc.
    if isinstance(node, ast.Name):
        var_name = node.id
        if var_name.startswith("__"):
            raise SafeExpressionError(f"Forbidden variable access: {var_name}")
        return scope.get(var_name, None)

    # Attribute access: $json.foo or $env.BAR
    if isinstance(node, ast.Attribute):
        target = _eval_ast_node(node.value, scope)
        if target is None:
            return None
        return _safe_resolve_attr(target, node.attr)

    # Subscript: $json["foo"] or $node["MyNode"] or arr[0]
    if isinstance(node, ast.Subscript):
        target = _eval_ast_node(node.value, scope)
        if target is None:
            return None
        index_val = _eval_ast_node(node.slice, scope)
        try:
            return target[index_val]
        except (KeyError, IndexError, TypeError):
            return None

    # Unary operations: -x, +x, not x
    if isinstance(node, ast.UnaryOp):
        op_func = ALLOWED_OPERATORS.get(type(node.op))
        if not op_func:
            raise SafeExpressionError(f"Unsupported unary operator: {type(node.op).__name__}")
        operand = _eval_ast_node(node.operand, scope)
        return op_func(operand)

    # Binary operations: a + b, a * b
    if isinstance(node, ast.BinOp):
        op_func = ALLOWED_OPERATORS.get(type(node.op))
        if not op_func:
            raise SafeExpressionError(f"Unsupported binary operator: {type(node.op).__name__}")
        left = _eval_ast_node(node.left, scope)
        right = _eval_ast_node(node.right, scope)
        return op_func(left, right)

    # Comparison operations: a == b, a > b
    if isinstance(node, ast.Compare):
        left = _eval_ast_node(node.left, scope)
        for op, comparator in zip(node.ops, node.comparators):
            op_func = ALLOWED_OPERATORS.get(type(op))
            if not op_func:
                raise SafeExpressionError(f"Unsupported comparator: {type(op).__name__}")
            right = _eval_ast_node(comparator, scope)
            if not op_func(left, right):
                return False
            left = right
        return True

    # Boolean operations: a and b, a or b
    if isinstance(node, ast.BoolOp):
        if isinstance(node.op, ast.And):
            for val_node in node.values:
                val = _eval_ast_node(val_node, scope)
                if not val:
                    return val
            return val
        elif isinstance(node.op, ast.Or):
            for val_node in node.values:
                val = _eval_ast_node(val_node, scope)
                if val:
                    return val
            return val

    # Method / function calls: e.g. $input.all(), str.lower()
    if isinstance(node, ast.Call):
        if isinstance(node.func, ast.Attribute):
            method_name = node.func.attr
            if method_name not in ALLOWED_METHOD_NAMES or method_name.startswith("_"):
                raise SafeExpressionError(f"Method '{method_name}' is not allowed in expressions.")
            target = _eval_ast_node(node.func.value, scope)
            if target is None:
                return None
            method = getattr(target, method_name, None)
            if not callable(method):
                return None
            args = [_eval_ast_node(a, scope) for a in node.args]
            return method(*args)
        elif isinstance(node.func, ast.Name):
            func_name = node.func.id
            # Whitelist basic global helpers
            safe_globals = {
                "len": len,
                "str": str,
                "int": lambda x: int(x) if x is not None else 0,
                "float": lambda x: float(x) if x is not None else 0.0,
                "bool": bool,
            }
            if func_name in safe_globals:
                args = [_eval_ast_node(a, scope) for a in node.args]
                return safe_globals[func_name](*args)
            raise SafeExpressionError(f"Global function '{func_name}' is not allowed.")

    # List literal: [1, 2, 3]
    if isinstance(node, ast.List):
        return [_eval_ast_node(elt, scope) for elt in node.elts]

    # Dict literal: {"a": 1}
    if isinstance(node, ast.Dict):
        return {
            _eval_ast_node(k, scope): _eval_ast_node(v, scope)
            for k, v in zip(node.keys, node.values)
            if k is not None
        }

    # IfExp: a if cond else b
    if isinstance(node, ast.IfExp):
        cond = _eval_ast_node(node.test, scope)
        if cond:
            return _eval_ast_node(node.body, scope)
        return _eval_ast_node(node.orelse, scope)

    raise SafeExpressionError(f"Unsupported AST node type: {type(node).__name__}")


def evaluate_single_expression(expr_str: str, context: ExpressionContext) -> Any:
    """
    Safely evaluate a single expression string without enclosing braces.
    Normalizes $ variables so Python AST parser accepts them:
      $json -> _var_json
      $node -> _var_node
      $input -> _var_input
      $env -> _var_env
      $item -> _var_item
    """
    clean_expr = expr_str.strip()

    # Pre-process $ variable prefixes to valid Python identifiers
    var_map = {
        "$json": "_var_json",
        "$node": "_var_node",
        "$input": "_var_input",
        "$env": "_var_env",
        "$item": "_var_json",
    }
    transformed_expr = clean_expr
    for dollar_var, py_var in var_map.items():
        # Match dollar_var not preceded by word char or dollar
        pattern = r"(?<![\w\$])" + re.escape(dollar_var) + r"(?![\w\$])"
        transformed_expr = re.sub(pattern, py_var, transformed_expr)

    try:
        parsed_ast = ast.parse(transformed_expr, mode="eval")
    except SyntaxError as e:
        raise SafeExpressionError(f"Syntax error in expression '{expr_str}': {e}")

    scope = {
        "_var_json": context.get_json(),
        "_var_node": context.get_node(),
        "_var_input": context.get_input(),
        "_var_env": context.get_env(),
    }

    return _eval_ast_node(parsed_ast.body, scope)


EXPRESSION_REGEX = re.compile(r"\{\{\s*(.*?)\s*\}\}")


def evaluate_string(text: str, context: ExpressionContext) -> Any:
    """
    Evaluate expressions within a string.
    - If string is EXACTLY `{{ expr }}`, returns the evaluated Python value directly (preserving type).
    - If string contains text around `{{ expr }}`, interpolates evaluated values into string.
    """
    if not isinstance(text, str):
        return text

    stripped = text.strip()
    match = EXPRESSION_REGEX.fullmatch(stripped)
    if match:
        expr = match.group(1)
        try:
            return evaluate_single_expression(expr, context)
        except Exception:
            return None

    def replacer(m: re.Match) -> str:
        expr = m.group(1)
        try:
            val = evaluate_single_expression(expr, context)
            return "" if val is None else str(val)
        except Exception:
            return ""

    return EXPRESSION_REGEX.sub(replacer, text)


def evaluate_value(val: Any, context: ExpressionContext) -> Any:
    """Recursively evaluates expressions across dicts, lists, and strings."""
    if isinstance(val, str):
        return evaluate_string(val, context)
    elif isinstance(val, dict):
        return {k: evaluate_value(v, context) for k, v in val.items()}
    elif isinstance(val, list):
        return [evaluate_value(item, context) for item in val]
    return val
