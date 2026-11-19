"""Read an eligible file into approved context."""

from cmf_dev_studio.tools.context import MAX_READ_BYTES, ToolContext


def read(context: ToolContext, query: str) -> str:
    value = context.snapshot.text(query)
    if value is None:
        return "File unavailable or excluded."
    if query not in context.approved:
        size = len(value.encode())
        if context.spent + size > MAX_READ_BYTES:
            return "Read budget exhausted."
        context.spent += size
        context.approved[query] = value
    return value
