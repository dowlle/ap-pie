"""Byte limits for Builder documents and their stored option values."""

MAX_BUILDER_YAML_BYTES = 1024 * 1024
MAX_OPTION_VALUES_BYTES = 1024 * 1024


def size_limit_message(label: str, size: int, limit: int) -> str:
    return f"{label} is {size:,} bytes. The limit is {limit:,} bytes."


def option_values_error(size: int | None) -> dict[str, str] | None:
    if size is None:
        return {"error": "These option values cannot be stored."}
    if size > MAX_OPTION_VALUES_BYTES:
        return {
            "error": size_limit_message("These option values", size, MAX_OPTION_VALUES_BYTES),
            "code": "option_values_too_large",
        }
    return None
