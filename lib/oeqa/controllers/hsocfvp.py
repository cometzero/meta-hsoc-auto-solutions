# SPDX-License-Identifier: MIT

from __future__ import annotations

from pathlib import Path
import re
from threading import Lock
import time

from oeqa.controllers.fvp import OEFVPTarget, OEFVPTargetState
from oeqa.controllers.hsocfvp_config import (
    RuntimeConfigRequest,
    prepare_runtime_config,
)
import pexpect


TERMINAL_STATUS_QUERY_RE = re.compile(br"\x1b\[6n")
TERMINAL_STATUS_RESPONSE = b"\x1b[32766;32766R"
LOGIN_PROMPT_NUDGE = b"\r"
LOGIN_PROMPT_NUDGE_INTERVAL_S = 15.0
LOGIN_PROMPT_NUDGE_MARKERS = (
    b" login:",
    b"Login Prompts",
    b"Multi-User System",
    b"root@",
    b"systemd[1]:",
)
ROOT_SHELL_PROMPT_RE = r"root@[^:\r\n]+:~#"
BSP_READY_RE = r"NEXIOS_BSP_INITRAMFS_READY machine=apollo-(?:fvp|qvp)"
BSP_SHELL_PROMPT_RE = r"nexios-bsp# "
def _is_login_prompt_pattern(pattern) -> bool:
    text = getattr(pattern, "pattern", pattern)
    if isinstance(text, bytes):
        return b"login" in text
    if isinstance(text, str):
        return "login" in text
    return False


def _should_nudge_login_prompt(terminal_session) -> bool:
    before = getattr(terminal_session, "before", b"")
    if isinstance(before, str):
        before = before.encode()
    return any(marker in before for marker in LOGIN_PROMPT_NUDGE_MARKERS)


class HSOCOEFVPTarget(OEFVPTarget):
    def transition(self, state, timeout=10 * 60):
        current_state = self.__dict__.get("state", OEFVPTargetState.OFF)
        if state == OEFVPTargetState.ON and state != current_state:
            if current_state != OEFVPTargetState.OFF:
                super().transition(OEFVPTargetState.OFF, timeout)
            self._reset_writable_flash()
        return super().transition(state, timeout)

    def _reset_writable_flash(self) -> None:
        source_fvpconf = self.__dict__.get("_hsoc_source_fvpconf", self.fvpconf)
        self._hsoc_source_fvpconf = source_fvpconf
        bootlog = self.bootlog
        if bootlog is None:
            raise ValueError("FVP runtime boot log path is required")
        self.fvpconf = prepare_runtime_config(
            RuntimeConfigRequest(
                source=source_fvpconf,
                bootlog=Path(bootlog),
                logger=self.logger,
            )
        )

    def expect(self, terminal, patterns, *args, **kwargs):
        terminal_session = self.terminals[terminal]
        pexpect_args = list(args)
        if pexpect_args:
            timeout = pexpect_args.pop(0)
        else:
            timeout = kwargs.pop("timeout", -1)
        pattern_list = (
            list(patterns)
            if isinstance(patterns, (list, tuple))
            else [patterns]
        )
        login_prompt_wait = any(
            _is_login_prompt_pattern(pattern) for pattern in pattern_list
        )
        augmented_patterns = [*pattern_list, TERMINAL_STATUS_QUERY_RE]
        query_index = len(pattern_list)
        deadline = (
            None
            if timeout is None or timeout < 0
            else time.monotonic() + timeout
        )

        while True:
            current_timeout = timeout
            if deadline is not None:
                current_timeout = max(0, deadline - time.monotonic())
            if login_prompt_wait:
                if current_timeout is None or current_timeout < 0:
                    current_timeout = LOGIN_PROMPT_NUDGE_INTERVAL_S
                else:
                    current_timeout = min(
                        current_timeout,
                        LOGIN_PROMPT_NUDGE_INTERVAL_S,
                    )

            self.logger.debug(
                "Calling expect on %s : with arguments -> %s  :  %s",
                terminal,
                patterns,
                {"timeout": current_timeout, **kwargs},
            )
            start_time = time.monotonic()
            try:
                result = terminal_session.expect(
                    augmented_patterns,
                    *pexpect_args,
                    timeout=current_timeout,
                    **kwargs,
                )
            except pexpect.TIMEOUT:
                if (
                    login_prompt_wait
                    and (deadline is None or time.monotonic() < deadline)
                ):
                    action = "without nudge"
                    if _should_nudge_login_prompt(terminal_session):
                        terminal_session.send(LOGIN_PROMPT_NUDGE)
                        action = "after nudge"
                    self.logger.debug(
                        "Retrying login prompt wait on %s %s",
                        terminal,
                        action,
                    )
                    continue
                raise
            elapsed_time = time.monotonic() - start_time
            self.logger.debug(
                "Execution time for result: [ %s ] - elapsed_time: %s seconds",
                result,
                elapsed_time,
            )

            if result != query_index:
                return result

            self.logger.debug("Answering terminal status query on %s", terminal)
            terminal_session.send(TERMINAL_STATUS_RESPONSE)


class HSOCSingleSessionFVPTarget(HSOCOEFVPTarget):
    """Keep functional OEQA tests on the FVP instance that reached Linux."""

    def transition(self, state, timeout=10 * 60):
        current_state = self.__dict__.get("state", OEFVPTargetState.OFF)
        if state == OEFVPTargetState.ON and current_state == OEFVPTargetState.LINUX:
            self.logger.info("Keeping the running Linux FVP session")
            return
        if state == OEFVPTargetState.OFF:
            self.__dict__.pop("_hsoc_linux_shell_ready", None)
        result = super().transition(state, timeout)
        if state == OEFVPTargetState.LINUX and not self.__dict__.get(
            "_hsoc_linux_shell_ready", False
        ):
            self.sendline(self.DEFAULT_CONSOLE, "root")
            self.expect(
                self.DEFAULT_CONSOLE,
                ROOT_SHELL_PROMPT_RE,
                timeout=timeout,
            )
            self._hsoc_linux_shell_ready = True
            self.logger.info("Linux root shell is ready on the running FVP session")
        return result


class HSOCBSPFVPTarget(HSOCOEFVPTarget):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._hsoc_bsp_command_lock = Lock()
        self._hsoc_bsp_command_index = 0

    def transition(self, state, timeout=10 * 60):
        current_state = self.__dict__.get("state", OEFVPTargetState.OFF)
        if state == OEFVPTargetState.ON and current_state == OEFVPTargetState.LINUX:
            self.logger.info("Keeping the running BSP FVP session")
            return None
        if state != OEFVPTargetState.LINUX:
            return super().transition(state, timeout)
        if current_state == OEFVPTargetState.LINUX:
            return None
        super().transition(OEFVPTargetState.ON, timeout)
        self.expect(self.DEFAULT_CONSOLE, BSP_READY_RE, timeout=timeout)
        self.expect(self.DEFAULT_CONSOLE, BSP_SHELL_PROMPT_RE, timeout=timeout)
        self.state = OEFVPTargetState.LINUX
        self.logger.info("BSP root shell is ready on the running FVP session")
        return None

    def run(self, cmd, timeout=None, ignore_status=True, raw=False):
        del ignore_status, raw
        command_timeout = self.timeout if timeout is None else timeout
        with self._hsoc_bsp_command_lock:
            self.transition(OEFVPTargetState.LINUX, timeout=command_timeout)
            self._hsoc_bsp_command_index += 1
            token = f"{self._hsoc_bsp_command_index:08x}"
            begin = f"__OEQA_BSP_BEGIN_{token}__"
            end = f"__OEQA_BSP_END_{token}__"
            wrapped = (
                f"printf '\\n{begin}\\n'; {{ {cmd}; }}; rc=$?; "
                f"printf '\\n{end}=%s\\n' \"$rc\""
            )
            self.sendline(self.DEFAULT_CONSOLE, wrapped)
            self.expect(self.DEFAULT_CONSOLE, re.escape(begin), timeout=command_timeout)
            self.expect(
                self.DEFAULT_CONSOLE,
                re.compile(rf"{re.escape(end)}=(\d+)"),
                timeout=command_timeout,
            )
            output = self.before(self.DEFAULT_CONSOLE)
            match = self.match(self.DEFAULT_CONSOLE)
            self.expect(
                self.DEFAULT_CONSOLE,
                BSP_SHELL_PROMPT_RE,
                timeout=command_timeout,
            )
        if isinstance(output, bytes):
            output = output.decode("utf-8", errors="replace")
        raw_status = match.group(1)
        if isinstance(raw_status, bytes):
            raw_status = raw_status.decode("ascii")
        return int(raw_status), output.strip("\r\n")
