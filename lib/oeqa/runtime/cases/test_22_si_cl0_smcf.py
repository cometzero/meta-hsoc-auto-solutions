#
# SPDX-FileCopyrightText: <text>Copyright 2026 Arm Limited and/or its
# affiliates <open-source-office@arm.com></text>
#
# SPDX-License-Identifier: MIT

import re
import time
import pexpect
from oeqa.core.decorator.depends import OETestDepends
from oeqa.runtime.case import OERuntimeTestCase
from oeqa.utils.scp_cli_utils import ScpCliUtils
from oeqa.utils.linux_terminal_utils import ConsoleDrainUtils


class SmcfTests(ScpCliUtils, ConsoleDrainUtils,
                OERuntimeTestCase):
    """
    SMCF tests using SCP Debugger CLI.
    Covers scenarios including client startup, integration test execution,
    stress testing, and sensor monitoring validation.
    """
    TEST_NAME = "smcf"
    TIMEOUT = 120
    SLEEP_INTERVAL = 60

    def setUp(self):
        super().setUp()
        self.console = "scp"
        try:
            self.target.transition("on")
        except Exception:
            raise AssertionError(
                "Target failed to power on before test execution."
            )

    def tearDown(self):
        try:
            self.target.transition("on")
        except Exception:
            raise AssertionError(
                "Target failed to reboot after test execution. "
                "Please check the target state."
            )
        super().tearDown()

    @OETestDepends([
        'test_00_si_cl0_boot.SiCl0BootTest.test_scp_boot'
    ])
    def test_01_smcf_client_start(self):
        """
        Verify that SMCF client has started successfully.
        """
        pattern = (
            r"\[SMCF_CLIENT\]\s+start data_sampling for MGI\[(?P<idx>\d+)\]"
        )
        time.sleep(self.SLEEP_INTERVAL)
        try:
            self.wait_for_pattern(self.target, self.console, pattern)
        except (pexpect.TIMEOUT, pexpect.EOF) as err:
            raise AssertionError(
                "SMCF client may not have started successfully."
            ) from err

    @OETestDepends([
        'test_22_si_cl0_smcf.SmcfTests.test_01_smcf_client_start'
    ])
    def test_02_execute_smcf_test(self):
        """
        Execute and validate SMCF integration test.
        """
        START = (
            rf"\[INTEGRATION_TEST\]\s+Start:\s*{re.escape(self.TEST_NAME)}"
        )
        END = (
            rf"\[INTEGRATION_TEST\]\s+End:\s*{re.escape(self.TEST_NAME)}"
        )
        SUMMARY_RE = (
            r"\s*(?P<tests>\d+)\s+Tests\s+0\s+Failures\s+0\s+Ignored"
        )
        self.enter_cli(self.target, self.console)
        self.target.sendline(self.console, f"test {self.TEST_NAME}")
        time.sleep(self.SLEEP_INTERVAL)
        self.exit_cli(self.target, self.console)
        time.sleep(self.SLEEP_INTERVAL)
        try:
            self.wait_for_pattern(self.target, self.console, START)
            self.wait_for_pattern(self.target, self.console, SUMMARY_RE)
            self.wait_for_pattern(self.target, self.console, END)
        except (pexpect.TIMEOUT, pexpect.EOF) as err:
            raise AssertionError(f"Failed to execute {self.TEST_NAME}:"
                                 ) from err

    @OETestDepends([
        'test_22_si_cl0_smcf.SmcfTests.test_02_execute_smcf_test'
    ])
    def test_03_run_smcf_3x(self):
        """
        Run SMCF test command three times to ensure stability.
        """
        for _ in range(3):
            self.drain_console_to_tail(self.target, self.console)
            self.test_02_execute_smcf_test()

    @OETestDepends([
        'test_22_si_cl0_smcf.SmcfTests.test_03_run_smcf_3x'
    ])
    def test_04_smcf_client_sensor_monitor(self):
        """Run SMCF client sensor monitor test"""
        pattern = (
            r"\[SMCF_CLIENT\]\s+Values for MGI\s+"
            r"(?P<mgi_name>[\w_]+)\s+(?P<type>\w+)\s+"
            r"(?P<index>\d+)\s+\((?P<desc>\w+)\)"
        )
        self.enter_cli(self.target, self.console)
        self.target.sendline(self.console, f"test {self.TEST_NAME}")
        time.sleep(self.SLEEP_INTERVAL)
        self.exit_cli(self.target, self.console)
        time.sleep(self.SLEEP_INTERVAL)
        try:
            self.wait_for_pattern(self.target, self.console,
                                  "INTEGRATION_TEST")
            self.wait_for_pattern(self.target, self.console, pattern)
        except (pexpect.TIMEOUT, pexpect.EOF) as err:
            raise AssertionError(
                f"Pattern '{pattern}' not found in SCP logs. "
                "SMCF client may not have started to read sensors."
            ) from err
