from __future__ import annotations

import re


def run_serial_command(target, command, timeout, begin, end, prompt):
    if not command or any(marker in command for marker in ("\0", "\r", "\n")):
        raise ValueError("FVP serial command must be a non-empty single-line string")
    if timeout <= 0:
        raise ValueError("FVP serial command timeout must be positive")
    wrapped = (
        f"printf '\\n{begin}\\n'; {{ {command}; }}; rc=$?; "
        f"printf '\\n{end}=%s\\n' \"$rc\""
    )
    target.sendline(target.DEFAULT_CONSOLE, wrapped)
    target.expect(target.DEFAULT_CONSOLE, re.escape(begin), timeout=timeout)
    target.expect(
        target.DEFAULT_CONSOLE,
        re.compile(rf"{re.escape(end)}=(\d+)"),
        timeout=timeout,
    )
    output = target.before(target.DEFAULT_CONSOLE)
    match = target.match(target.DEFAULT_CONSOLE)
    target.expect(target.DEFAULT_CONSOLE, prompt, timeout=timeout)
    if isinstance(output, bytes):
        output = output.decode("utf-8", errors="replace")
    raw_status = match.group(1)
    if isinstance(raw_status, bytes):
        raw_status = raw_status.decode("ascii")
    return int(raw_status), output.strip("\r\n")


def serial_console_tail(target):
    terminals = target.__dict__.get("terminals", {})
    terminal = terminals.get(target.DEFAULT_CONSOLE)
    before = getattr(terminal, "before", b"") if terminal is not None else b""
    if isinstance(before, bytes):
        before = before.decode("utf-8", errors="replace")
    return "\n".join(str(before).splitlines()[-200:])


class FVPSerialBootError(RuntimeError):
    def __init__(self, reason, console):
        self.reason = reason
        self.console = console
        detail = f"{reason}\nconsole tail:\n{console}" if console else reason
        super().__init__(detail)
