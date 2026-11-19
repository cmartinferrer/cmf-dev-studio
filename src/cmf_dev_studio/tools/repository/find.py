"""Find eligible repository paths."""

import fnmatch
import json

from cmf_dev_studio.tools.context import ToolContext


def find(context: ToolContext, query: str) -> str:
    return json.dumps(
        [
            path
            for path in sorted(context.snapshot.files)
            if context.snapshot.eligible(path)
            and (
                fnmatch.fnmatch(path.lower(), query.lower())
                or query.lower() in path.lower()
            )
        ][:40]
    )
