"""Search eligible text without returning source lines."""

import json

from cmf_dev_studio.tools.context import ToolContext


def search(context: ToolContext, query: str) -> str:
    hits = []
    for path in sorted(context.snapshot.files):
        value = context.snapshot.text(path)
        if value is None:
            continue
        for number, line in enumerate(value.splitlines(), 1):
            if query.casefold() in line.casefold():
                hits.append(f"{path}:{number}")
                if len(hits) >= 40:
                    return json.dumps(hits)
    return json.dumps(hits)
