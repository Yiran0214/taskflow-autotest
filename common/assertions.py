"""断言增强工具: HTTP 状态码断言 + 轻量 JSON Schema 结构校验

自研的轻量 schema 校验器, 免第三方依赖, 支持:
    - 字段类型校验 (str/int/float/bool/list/dict/None)
    - required / optional 字段
    - 列表元素 schema 递归校验
断言失败时输出"字段路径 + 期望 + 实际"的精确差异信息, 便于定位问题。
"""
from typing import Any


def assert_status(response, expected: int, context: str = "") -> None:
    """断言 HTTP 状态码, 失败时附带请求上下文与响应体摘要"""
    actual = response.status_code
    body = response.text[:300]
    assert actual == expected, (
        f"[{context}] 期望状态码 {expected}, 实际 {actual}\n响应体: {body}"
    )


class SchemaError(AssertionError):
    pass


def validate_schema(data: Any, schema: dict, path: str = "$") -> None:
    """递归校验 data 是否符合 schema 结构。

    schema 示例:
        {
            "type": "object",
            "required": ["id", "title"],
            "properties": {
                "id": {"type": "int"},
                "title": {"type": "str"},
                "tags": {"type": "list", "items": {"type": "str"}},
            },
        }
    """
    expected_type = schema.get("type")
    if expected_type is not None:
        _check_type(data, expected_type, path)
        if data is None:
            return

    if expected_type == "object":
        _check_required(data, schema.get("required", []), path)
        for field, sub_schema in schema.get("properties", {}).items():
            if field in data:
                validate_schema(data[field], sub_schema, f"{path}.{field}")
    elif expected_type == "list":
        item_schema = schema.get("items")
        if item_schema:
            for i, item in enumerate(data):
                validate_schema(item, item_schema, f"{path}[{i}]")


def _check_type(data: Any, expected: str, path: str) -> None:
    type_map = {
        "str": str, "int": int, "float": (int, float), "bool": bool,
        "list": list, "dict": dict, "object": dict, "none": type(None),
    }
    # 联合类型: "str|none" 表示允许字符串或 null
    if "|" in expected:
        for sub in expected.split("|"):
            try:
                _check_type(data, sub.strip(), path)
                return
            except SchemaError:
                continue
        raise SchemaError(f"{path}: 期望类型 {expected}, 实际 {type(data).__name__} (值: {data!r})")
    real_type = type_map.get(expected)
    if real_type is None:
        raise SchemaError(f"{path}: 未知类型期望 '{expected}'")
    if not isinstance(data, real_type) or (expected == "bool" and isinstance(data, int)):
        raise SchemaError(f"{path}: 期望类型 {expected}, 实际 {type(data).__name__} (值: {data!r})")


def _check_required(data: dict, required: list, path: str) -> None:
    for field in required:
        if field not in data:
            raise SchemaError(f"{path}: 缺少必填字段 '{field}', 实际字段: {sorted(data)}")


def assert_task_shape(task: dict) -> None:
    """TaskFlow 任务对象的通用结构断言 (接口返回结构的统一契约)"""
    validate_schema(task, {
        "type": "object",
        "required": ["id", "title", "description", "priority", "status",
                     "due_date", "created_at", "updated_at"],
        "properties": {
            "id": {"type": "int"},
            "title": {"type": "str"},
            "description": {"type": "str|none"},
            "priority": {"type": "str"},
            "status": {"type": "str"},
            "due_date": {"type": "str|none"},
            "created_at": {"type": "str"},
            "updated_at": {"type": "str"},
        },
    })
