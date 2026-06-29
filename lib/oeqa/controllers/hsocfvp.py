# SPDX-License-Identifier: MIT

from __future__ import annotations

import json
from pathlib import Path
import re
import shutil
import time

from oeqa.controllers.fvp import OEFVPTarget, OEFVPTargetState
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
FVP_WRITABLE_FLASH_PAIRS = (
    (
        "css.smb.rseil.rse_flashloader.fname",
        "css.smb.rseil.rse_flashloader.fnameWrite",
    ),
    ("ros.flash_loader.fname", "ros.flash_loader.fnameWrite"),
)
FVP_WRITABLE_IMAGE_KEYS = (
    "css.smb.rseil.rse.lcm_nvm.raw_image",
)


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
        with open(source_fvpconf, encoding="utf-8") as stream:
            config = json.load(stream)
        parameters = config.get("parameters", {})
        runtime_fvpconf = None
        writable_dir = None

        for read_key, write_key in FVP_WRITABLE_FLASH_PAIRS:
            read_image = parameters.get(read_key)
            write_image = parameters.get(write_key)
            if not read_image or not write_image:
                continue

            read_path = self._fvpconf_path(read_image)
            write_path = self._fvpconf_path(write_image)
            if read_path == write_path:
                continue

            write_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(read_path, write_path)
            parameters[write_key] = str(write_path)
            writable_dir = write_path.parent
            self.logger.debug(
                "Reset writable FVP flash %s from %s",
                write_path,
                read_path,
            )

        for key in FVP_WRITABLE_IMAGE_KEYS:
            image = parameters.get(key)
            if not image:
                continue

            read_path = self._fvpconf_path(image)
            if writable_dir is None:
                writable_dir = read_path.parent / "hsoc-oeqa-writable"
            write_path = writable_dir / read_path.name
            write_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(read_path, write_path)
            parameters[key] = str(write_path)
            self.logger.debug(
                "Reset writable FVP image %s from %s",
                write_path,
                read_path,
            )

        if writable_dir is not None:
            runtime_fvpconf = writable_dir / (
                f"{source_fvpconf.stem}.hsoc-oeqa.fvpconf"
            )

        if runtime_fvpconf is not None:
            runtime_fvpconf.write_text(
                json.dumps(config),
                encoding="utf-8",
            )
            self.fvpconf = runtime_fvpconf

    def _fvpconf_path(self, value: str) -> Path:
        path = Path(value)
        if path.is_absolute():
            return path
        return self.fvpconf.parent / path

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
