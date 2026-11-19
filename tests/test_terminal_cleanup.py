"""Regression tests for terminal process-group cleanup."""

import asyncio
import signal
from unittest.mock import Mock, patch

from cmf_dev_studio.api.terminal import terminate_terminal_process


def test_cleanup_signals_group_even_after_leader_exits():
    """Children can survive the exit of their process-group leader."""
    process = Mock(pid=12345)
    process.wait.return_value = 0
    with patch("cmf_dev_studio.api.terminal.os.killpg") as kill:
        asyncio.run(terminate_terminal_process(process))
    assert [call.args for call in kill.call_args_list] == [
        (12345, signal.SIGHUP),
        (12345, signal.SIGKILL),
    ]


def test_cleanup_handles_missing_group():
    """An already terminated group does not cause a cleanup failure."""
    process = Mock(pid=12345)
    with patch("cmf_dev_studio.api.terminal.os.killpg", side_effect=ProcessLookupError):
        asyncio.run(terminate_terminal_process(process))
    process.wait.assert_called_once()
