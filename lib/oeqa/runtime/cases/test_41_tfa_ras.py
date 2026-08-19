# SPDX-FileCopyrightText: <text>Copyright 2026 Arm Limited and/or its
# affiliates <open-source-office@arm.com></text>
#
# SPDX-License-Identifier: MIT
#
# noqa: SIZE_OK - kept aligned with the upstream cross-console RAS harness.
#
# cspell:ignore printk ratelimit

from __future__ import annotations

import base64
import re
import time
from dataclasses import dataclass

import pexpect
from oeqa.core.decorator.depends import OETestDepends
from oeqa.runtime.case import OERuntimeTestCase
from oeqa.utils.arm_auto_solutions_config import ArmAutoSolutionsConfig


RAS_ESTATUS_CACHE_WINDOW_S = 10


# -------------------------
# Configuration containers
# -------------------------
@dataclass(frozen=True)
class RasTimeouts:
    boot_timeout: int
    inject_timeout: int
    post_inject_timeout: int
    post_inject_settle_s: int


@dataclass(frozen=True)
class RasHarnessCfg:
    console: str
    tfa_console: str
    scp_console: str
    hostname: str
    timeouts: RasTimeouts


# -------------------------
# Prompt / login helper
# -------------------------
class RasPrompt:
    ANSI = r"(?:\x1b\[[0-?]*[ -/]*[@-~]|\x1b[@-Z\\-_]|\x1b7|\x1b8)*"

    def __init__(self, test: OERuntimeTestCase, cfg: RasHarnessCfg) -> None:
        self._t = test
        self._cfg = cfg

    def root_prompt_re(self) -> str:
        ansi = self.ANSI
        return rf"{ansi}\s*root@[\w\-\.\:]+:[^\r\n]*#\s*"

    def _login_re(self) -> str:
        return rf"{self.ANSI}.*login:\s*"

    def _ps2_re(self) -> str:
        return r"(?m)^\s*>\s*$"

    def _prompt_patterns(self) -> list[str]:
        return [self.root_prompt_re(), self._login_re(), self._ps2_re()]

    def _recover_from_ps2(self) -> None:
        self._t.target.send(self._cfg.console, "\x03")
        self._t.target.sendline(self._cfg.console, "")

    def _expect_prompt_once(self, timeout: int) -> int:
        try:
            return self._t.target.expect(
                self._cfg.console,
                self._prompt_patterns(),
                timeout=timeout,
            )
        except pexpect.TIMEOUT:
            return -1

    def _handle_prompt_idx(self, idx: int) -> bool:
        if idx == 0:
            return True
        if idx == 1:
            self._t.target.sendline(self._cfg.console, "root")
            return False
        self._recover_from_ps2()
        return False

    def _tickle_console(self) -> None:
        self._t.target.sendline(self._cfg.console, "")

    def _timeout_fail(self) -> None:
        self._t.fail("Timed out waiting for root prompt")

    def _remaining_or_fail(self, deadline: float) -> int:
        remaining = int(deadline - time.monotonic())
        if remaining <= 0:
            self._timeout_fail()
        return remaining

    def _tickle_on_timeout(self) -> None:
        self._t.target.send(self._cfg.console, "\r")

    def _step_to_root(self, deadline: float) -> bool:
        remaining = self._remaining_or_fail(deadline)
        idx = self._expect_prompt_once(timeout=min(10, remaining))
        if idx == -1:
            self._tickle_on_timeout()
            return False
        return self._handle_prompt_idx(idx)

    def expect_root_prompt(self, timeout: int = 60) -> None:
        deadline = time.monotonic() + timeout
        self._tickle_console()
        while not self._step_to_root(deadline):
            pass

    def to_linux_and_login_root(self) -> None:
        self._t.target.transition("linux", self._cfg.timeouts.boot_timeout)

        self._t.target.sendline(self._cfg.console, "")
        idx = self._t.target.expect(
            self._cfg.console,
            [self.root_prompt_re(), self._login_re()],
            timeout=600,
        )
        if idx == 1:
            self._t.target.sendline(self._cfg.console, "root")
            self.expect_root_prompt(timeout=600)


# -------------------------
# dmesg helper
# -------------------------
class RasDmesg:
    def __init__(
        self,
        test: OERuntimeTestCase,
        cfg: RasHarnessCfg,
        prompt: RasPrompt,
    ) -> None:
        self._t = test
        self._cfg = cfg
        self._prompt = prompt

    def clear_dmesg(self) -> None:
        self._t.target.sendline(
            self._cfg.console,
            "dmesg -c >/dev/null 2>&1; echo DMESG_CLEARED",
        )
        self._t.target.expect(self._cfg.console, r"DMESG_CLEARED", timeout=30)
        self._prompt.expect_root_prompt(timeout=60)

    def disable_kernel_log_ratelimit(self) -> None:
        # cspell:ignore-next-line
        self._t.target.sendline(
            self._cfg.console,
            "echo 0 > /proc/sys/kernel/printk_ratelimit || true",
        )
        self._prompt.expect_root_prompt(timeout=60)

        # cspell:ignore-next-line
        self._t.target.sendline(
            self._cfg.console,
            "echo 0 > /proc/sys/kernel/printk_ratelimit_burst || true",
        )
        self._prompt.expect_root_prompt(timeout=60)

    def _needle_to_b64(self, needle: str) -> str:
        return base64.b64encode(needle.encode("utf-8")).decode("ascii")

    def _poll_cmd(self, needle_b64: str) -> str:
        return (
            f'PAT="$(echo {needle_b64} | base64 -d)"; '
            'dmesg | grep -qF "$PAT" '
            "&& printf 'RAS_%s\\n' SEEN || printf 'RAS_%s\\n' WAIT"
        )

    def _expect_seen_wait_ps2(self, timeout: int) -> int:
        return self._t.target.expect(
            self._cfg.console,
            [r"\bRAS_SEEN\b", r"\bRAS_WAIT\b", r"(?m)^\s*>\s*$"],
            timeout=timeout,
        )

    def _dump_dmesg_tail_and_fail(self, needle: str) -> None:
        self._t.target.sendline(
            self._cfg.console,
            "dmesg | tail -n 120; echo DMESG_TAIL_DONE",
        )
        self._t.target.expect(
            self._cfg.console,
            r"DMESG_TAIL_DONE",
            timeout=60,
        )
        self._prompt.expect_root_prompt(timeout=60)
        self._t.fail(f"Timed out waiting for dmesg to contain: {needle!r}")

    def _ps2_recover_and_pause(self) -> None:
        self._t.target.send(self._cfg.console, "\x03")
        self._t.target.sendline(self._cfg.console, "")
        self._prompt.expect_root_prompt(timeout=60)
        time.sleep(1)

    def _wait_sleep(self) -> None:
        time.sleep(2)

    def _remaining_or_timeout(self, deadline: float, needle: str) -> int:
        remaining = int(deadline - time.monotonic())
        if remaining <= 0:
            self._dump_dmesg_tail_and_fail(needle)
        return remaining

    def poll_dmesg_has(self, needle: str, timeout: int) -> None:
        needle_b64 = self._needle_to_b64(needle)
        deadline = time.monotonic() + timeout

        while True:
            remaining = self._remaining_or_timeout(deadline, needle)
            self._t.target.sendline(
                self._cfg.console,
                self._poll_cmd(needle_b64),
            )
            idx = self._expect_seen_wait_ps2(timeout=min(30, remaining))

            if idx == 2:
                self._ps2_recover_and_pause()
                continue

            self._prompt.expect_root_prompt(timeout=60)
            if idx == 0:
                return

            self._wait_sleep()

    def poll_markers(self, severity: str, timeout: int) -> None:
        self.poll_dmesg_has(f"event severity: {severity}", timeout)
        self.poll_dmesg_has("processor context not corrupted", timeout)

        try:
            self.poll_dmesg_has("the error has been corrected", 20)
        except Exception:
            self.poll_dmesg_has("the error has not been corrected", 20)

        self.poll_dmesg_has("Context info structure 0", timeout)
        self.poll_dmesg_has("Context info structure 1", timeout)
        self.clear_dmesg()


# -------------------------
# Injection helper
# -------------------------
class RasInject:
    def __init__(self, test: OERuntimeTestCase, cfg: RasHarnessCfg) -> None:
        self._t = test
        self._cfg = cfg

    def inject_error(self, error_name: str) -> None:
        self._t.target.sendline(
            self._cfg.console,
            f"ts-ras-inject {error_name}")

        self._t.target.expect(
            self._cfg.console,
            rf"Calling ras service to inject {re.escape(error_name)}",
            timeout=self._cfg.timeouts.inject_timeout,
        )
        self._t.target.expect(
            self._cfg.console,
            r"Call to ras service finished with status: Success",
            timeout=self._cfg.timeouts.inject_timeout,
        )
        self._t.target.expect(
            self._cfg.tfa_console,
            r"CPU RAS: Interrupt Received",
            timeout=self._cfg.timeouts.inject_timeout,
        )


# -------------------------
# Harness composition
# (kept tiny to satisfy method-count rules)
# -------------------------
class RasHarness:
    def __init__(self, test: OERuntimeTestCase, cfg: RasHarnessCfg) -> None:
        self.cfg = cfg
        self.prompt = RasPrompt(test, cfg)
        self.dmesg = RasDmesg(test, cfg, self.prompt)
        self.inject = RasInject(test, cfg)


# -------------------------
# Tests
# -------------------------
class RasInjectTests(OERuntimeTestCase):
    """
    RAS CPU CLI tests on RD-Aspen.
    """

    def setUp(self) -> None:
        super().setUp()

        cfg = RasHarnessCfg(
            console=self.target.DEFAULT_CONSOLE,
            tfa_console="tf-a",
            scp_console="scp",
            hostname=ArmAutoSolutionsConfig.hostname,
            timeouts=RasTimeouts(
                boot_timeout=int(
                    self.td.get("TEST_FVP_LINUX_BOOT_TIMEOUT") or 900),
                inject_timeout=int(
                    self.td.get("RAS_INJECT_TIMEOUT") or 60),
                post_inject_timeout=int(
                    self.td.get("RAS_POST_INJECT_TIMEOUT") or 120),
                post_inject_settle_s=int(
                    self.td.get("RAS_POST_INJECT_SETTLE_S") or 3),
            ),
        )

        self.h = RasHarness(self, cfg)

    # ------
    # Tests
    # ------
    @OETestDepends(
        [
            "test_40_tfa_cpu_topology."
            "TfaCpuTopologyTest.test_configured_pc_cpus_in_tfa",
            "test_00_linux_boot.LinuxBootTest.test_linux_boot",
        ]
    )
    def test_01_ts_ras_inject_list(self) -> None:
        self.h.prompt.to_linux_and_login_root()
        self.target.sendline(self.h.cfg.console, "ts-ras-inject --list")
        self.target.expect(
            self.h.cfg.console,
            r"CorrectableCpuError UncorrectableFatalCpuError DeferredCpuError",
            timeout=60,
        )
        self.h.prompt.expect_root_prompt(timeout=60)

    @OETestDepends(
        [
            "test_41_tfa_ras."
            "RasInjectTests.test_01_ts_ras_inject_list"
        ]
    )
    def test_02_ts_ras_inject_invalid_cpu_error(self) -> None:
        self.h.prompt.to_linux_and_login_root()
        self.target.sendline(
            self.h.cfg.console,
            "ts-ras-inject InvalidErrorType")
        self.target.expect(
            self.h.cfg.console,
            r"Unknown error type: InvalidErrorType",
            timeout=60,
        )
        self.h.prompt.expect_root_prompt(timeout=60)

    @OETestDepends(
        [
            "test_41_tfa_ras."
            "RasInjectTests.test_02_ts_ras_inject_invalid_cpu_error"
        ]
    )
    def test_03_ts_ras_inject_usage(self) -> None:
        self.h.prompt.to_linux_and_login_root()
        self.target.sendline(self.h.cfg.console, "ts-ras-inject")
        self.target.expect(
            self.h.cfg.console,
            r"ErrorName is one of: CorrectableCpuError "
            r"UncorrectableFatalCpuError DeferredCpuError",
            timeout=60,
        )
        self.h.prompt.expect_root_prompt(timeout=60)

    @OETestDepends(
        [
            "test_41_tfa_ras."
            "RasInjectTests.test_03_ts_ras_inject_usage"
        ]
    )
    def test_04_ts_ras_inject_correctable_cpu_error(self) -> None:
        self.h.prompt.to_linux_and_login_root()
        self.h.dmesg.clear_dmesg()

        self.h.inject.inject_error("CorrectableCpuError")
        time.sleep(self.h.cfg.timeouts.post_inject_settle_s)
        self.h.dmesg.poll_markers(
            "corrected",
            self.h.cfg.timeouts.post_inject_timeout,
        )

    @OETestDepends(
        [
            "test_41_tfa_ras."
            "RasInjectTests.test_04_ts_ras_inject_correctable_cpu_error"
        ]
    )
    def test_05_ts_ras_inject_deferred_cpu_error(self) -> None:
        self.h.prompt.to_linux_and_login_root()
        self.h.dmesg.clear_dmesg()

        self.h.inject.inject_error("DeferredCpuError")
        time.sleep(self.h.cfg.timeouts.post_inject_settle_s)
        self.h.dmesg.poll_markers(
            "recoverable",
            self.h.cfg.timeouts.post_inject_timeout,
        )

    @OETestDepends(
        [
            "test_41_tfa_ras."
            "RasInjectTests.test_05_ts_ras_inject_deferred_cpu_error"
        ]
    )
    def test_06_ts_ras_inject_correctable_cpu_error_10x(self) -> None:
        """
        Run 'ts-ras-inject CorrectableCpuError' 10 times.
        Each iteration must return to the Linux prompt.
        """
        self.h.prompt.to_linux_and_login_root()
        self.h.dmesg.disable_kernel_log_ratelimit()
        previous_id: int | None = None
        repeat_settle_s = max(
            self.h.cfg.timeouts.post_inject_settle_s,
            RAS_ESTATUS_CACHE_WINDOW_S + 1,
        )

        for iteration in range(1, 11):
            self.h.dmesg.clear_dmesg()
            self.h.inject.inject_error("CorrectableCpuError")
            self.h.prompt.expect_root_prompt(timeout=60)
            time.sleep(repeat_settle_s)
            self.h.dmesg.poll_dmesg_has(
                "event severity: corrected",
                self.h.cfg.timeouts.post_inject_timeout,
            )

            self.target.sendline(
                self.h.cfg.console,
                r"dmesg | sed -nE 's/.*\{([0-9]+)\}"
                r"\[Hardware Error\]: event severity: corrected.*/"
                r"RAS_CPER_ID=\1/p'",
            )
            self.target.expect(
                self.h.cfg.console,
                r"RAS_CPER_ID=([0-9]+)",
                timeout=self.h.cfg.timeouts.post_inject_timeout,
            )
            current_id = int(self.target.match(self.h.cfg.console).group(1))
            self.h.prompt.expect_root_prompt(timeout=60)
            if previous_id is not None:
                self.assertEqual(
                    current_id,
                    previous_id + 1,
                    f"iteration {iteration}: non-consecutive CPER event ID",
                )
            previous_id = current_id
            self.h.dmesg.poll_markers(
                "corrected",
                self.h.cfg.timeouts.post_inject_timeout,
            )

    @OETestDepends(
        [
            "test_41_tfa_ras."
            "RasInjectTests.test_07_ts_ras_inject_uncorrectable_cpu_error"
        ]
    )
    def test_08_ts_ras_inject_correctable_deferred_cpu_error(self) -> None:
        self.h.prompt.to_linux_and_login_root()
        self.h.dmesg.clear_dmesg()

        self.h.inject.inject_error("CorrectableCpuError")
        time.sleep(self.h.cfg.timeouts.post_inject_settle_s)
        self.h.dmesg.poll_markers(
            "corrected",
            self.h.cfg.timeouts.post_inject_timeout,
        )

        self.h.inject.inject_error("DeferredCpuError")
        time.sleep(self.h.cfg.timeouts.post_inject_settle_s)
        self.h.dmesg.poll_markers(
            "recoverable",
            self.h.cfg.timeouts.post_inject_timeout,
        )

    @OETestDepends(
        [
            "test_41_tfa_ras."
            "RasInjectTests."
            "test_08_ts_ras_inject_correctable_deferred_cpu_error"
        ]
    )
    def test_09_journalctl_service(self) -> None:
        self.h.prompt.to_linux_and_login_root()

        status, output = self.target.run(
            "journalctl -u rasdaemon.service --no-pager",
            timeout=120,
        )
        self.assertEqual(status, 0, output)
        self.assertIn(
            "rasdaemon: ras:arm_event event enabled",
            output,
        )
        self.assertNotIn(
            "Error: can't get a proper CPU affinity.",
            output,
        )
        self.assertNotRegex(output, r"affinity:\s*-1")

    @OETestDepends(
        [
            "test_41_tfa_ras."
            "RasInjectTests."
            "test_06_ts_ras_inject_correctable_cpu_error_10x"
        ]
    )
    def test_07_ts_ras_inject_uncorrectable_cpu_error(self) -> None:
        self.h.prompt.to_linux_and_login_root()

        self.target.sendline(
            self.h.cfg.console,
            "ts-ras-inject UncorrectableFatalCpuError",
        )
        self.target.expect(
            self.h.cfg.scp_console,
            r"Faulty CPU Identified",
            timeout=120,
        )
        self.target.expect(
            self.h.cfg.scp_console,
            r"Fault Type = Uncontainable Error",
            timeout=120,
        )
        self.target.expect(
            self.h.cfg.scp_console,
            r"Setting SSU FSM to: ERRC",
            timeout=120,
        )

        self.target.transition("off")
        self.target.transition("on")
        self.h.prompt.to_linux_and_login_root()
