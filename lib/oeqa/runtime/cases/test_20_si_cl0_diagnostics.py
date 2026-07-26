#
# SPDX-FileCopyrightText: <text>Copyright 2025-2026 Arm Limited and/or its
# affiliates <open-source-office@arm.com></text>
#
# SPDX-License-Identifier: MIT

from oeqa.runtime.case import OERuntimeTestCase
from oeqa.core.decorator.depends import OETestDepends
from oeqa.utils.scp_cli_utils import ScpCliUtils, ScpTestUtils
from oeqa.utils.linux_terminal_utils import ConsoleDrainUtils


class SafetyDiagnosticsTestSSUFMU(
        ScpCliUtils,
        ConsoleDrainUtils,
        ScpTestUtils,
        OERuntimeTestCase):
    """
    SSU and FMU integration tests using the SCP Debugger CLI.
    """

    # Matches: "X Tests Y Failures Z Ignored"
    SUMMARY_RE = (
        r"(?P<total>\d+)\s+Tests\s+"
        r"(?P<failures>\d+)\s+Failures\s+"
        r"(?P<ignored>\d+)\s+Ignored"
    )

    def setUp(self):
        super().setUp()
        self.console = "scp"
        self.pc_console = "default"

    @OETestDepends([
        'test_00_si_cl0_boot.SiCl0BootTest.test_scp_boot'
    ])
    def test_safety_island_ssu(self):
        self.run_test("ssu")

    @OETestDepends([
        'test_20_si_cl0_diagnostics.'
        'SafetyDiagnosticsTestSSUFMU.test_safety_island_ssu'
    ])
    def test_safety_island_fmu(self):
        """Run and validate FMU integration tests."""
        self.run_test("fmu")
