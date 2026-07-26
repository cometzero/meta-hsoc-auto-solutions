#
# SPDX-FileCopyrightText: <text>Copyright 2026 Arm Limited and/or its
# affiliates <open-source-office@arm.com></text>
#
# SPDX-License-Identifier: MIT
#
# noqa: SIZE_OK - kept aligned with the upstream SI CL1 PFDI test sequence.
#

from oeqa.core.decorator.depends import OETestDepends
from oeqa.runtime.case import OERuntimeTestCase
from oeqa.utils.safety_island_cli_utils import SafetyIslandCLIUtils


class SafetyIslandTestBase(OERuntimeTestCase):

    def setUp(self):
        super().setUp()

        self.target.transition("on")

        self.si_console = "safety_island_c1"
        self.cpu_count = int(self.td.get("SI_CL1_CPUS_COUNT", "4"))
        self.cli = SafetyIslandCLIUtils(
            self.target,
            self.si_console,
            self.logger,
        )

    def _run_and_assert_invalid(self, cmd):
        out = self.cli.run(cmd, timeout=120)
        self.assertRegex(out, r"(invalid|error|argument)")

    def _run_and_assert_valid(self, cpu, cmd, expected_pattern):
        out = self.cli.run(cmd, timeout=120)

        self.assertRegex(out, r"rc=0")
        self.assertRegex(out, expected_pattern)

        self.assertRegex(
            out,
            (
                r"scheduled:\s*\d+,\s*"
                r"success:\s*\d+,\s*"
                r"skipped:\s*\d+"
            )
        )

    # --------------------------------------------------
    # Basic status
    # --------------------------------------------------

    @OETestDepends([
        'test_00_si_cl1_boot.SiCl1BootTest.test_si_cl1_boot'
    ])
    def test_01_pfdi_cluster_status(self):
        for cpu in range(self.cpu_count):
            with self.subTest(cpu=cpu):
                out = self.cli.get_status(cpu)
                self.assertRegex(
                    out,
                    rf"cpu{cpu}.*(running|stopped|disabled)",
                )

    # --------------------------------------------------
    # Block execution
    # --------------------------------------------------

    @OETestDepends([
        'test_30_si_cl1_pfdi.'
        'SafetyIslandTestBase.test_01_pfdi_cluster_status'
    ])
    def test_03_pfdi_run_block(self):
        for cpu in range(self.cpu_count):
            with self.subTest(cpu=cpu):

                # Invalid block
                out = self.cli.run(f"pfdi run {cpu} 0", timeout=120)
                self.assertRegex(out, r"(invalid|error|block id)")

                # Valid block
                out = self.cli.run(f"pfdi run {cpu} 1", timeout=120)
                self.assertRegex(out, r"rc=0")

    # Invalid cases
    @OETestDepends([
        'test_30_si_cl1_pfdi.'
        'SafetyIslandTestBase.test_01_pfdi_cluster_status'
    ])
    def test_04_pfdi_run_invalid_params(self):
        for cpu in range(self.cpu_count):
            with self.subTest(cpu=cpu):

                invalid_cmds = [
                    f"pfdi run {cpu} -2",
                    f"pfdi run {cpu} 1 -2 -1",
                    f"pfdi run {cpu} 1 -1 -2",
                    f"pfdi run {cpu} 1 2 1",
                    f"pfdi run {cpu} -1 1 2",
                ]

                for cmd in invalid_cmds:
                    self._run_and_assert_invalid(cmd)

    # Valid - block level
    @OETestDepends([
        'test_30_si_cl1_pfdi.'
        'SafetyIslandTestBase.test_01_pfdi_cluster_status'
    ])
    def test_05_pfdi_run_block_valid(self):
        for cpu in range(self.cpu_count):
            with self.subTest(cpu=cpu):

                self._run_and_assert_valid(
                    cpu,
                    f"pfdi run {cpu}",
                    rf"cpu{cpu}.*all blocks",
                )

                self._run_and_assert_valid(
                    cpu,
                    f"pfdi run {cpu} 1",
                    rf"cpu{cpu}.*block id\s+1.*all parts",
                )

    # Valid - range level
    @OETestDepends([
        'test_30_si_cl1_pfdi.'
        'SafetyIslandTestBase.test_01_pfdi_cluster_status'
    ])
    def test_06_pfdi_run_range_valid(self):
        for cpu in range(self.cpu_count):
            with self.subTest(cpu=cpu):

                self._run_and_assert_valid(
                    cpu,
                    f"pfdi run {cpu} 1 1 2",
                    r"block id\s+1.*part range:\s*1->2",
                )

    # --------------------------------------------------
    # CLI validation
    # --------------------------------------------------

    @OETestDepends([
        'test_30_si_cl1_pfdi.'
        'SafetyIslandTestBase.test_01_pfdi_cluster_status'
    ])
    def test_07_pfdi_invalid_cpu_value(self):
        out = self.cli.run("pfdi run all")
        self.assertRegex(out, r"invalid|error")

    @OETestDepends([
        'test_30_si_cl1_pfdi.'
        'SafetyIslandTestBase.test_01_pfdi_cluster_status'
    ])
    def test_08_pfdi_cpu_out_of_range(self):
        out = self.cli.run(f"pfdi run {self.cpu_count}")
        self.assertRegex(out, r"invalid|range|error")

    # --------------------------------------------------
    # Count APIs
    # --------------------------------------------------

    @OETestDepends([
        'test_30_si_cl1_pfdi.'
        'SafetyIslandTestBase.test_01_pfdi_cluster_status'
    ])
    def test_09_pfdi_count_blocks(self):
        for cpu in range(self.cpu_count):
            with self.subTest(cpu=cpu):
                out = self.cli.count(cpu)
                self.assertRegex(out, rf"cpu{cpu}.*\d+")

    @OETestDepends([
        'test_30_si_cl1_pfdi.'
        'SafetyIslandTestBase.test_01_pfdi_cluster_status'
    ])
    def test_10_pfdi_count_block_parts(self):
        for cpu in range(self.cpu_count):
            with self.subTest(cpu=cpu):
                out = self.cli.run(f"pfdi count {cpu} 1")
                self.assertRegex(out, rf"cpu{cpu}.*\d+")

    # --------------------------------------------------
    # Result validation
    # --------------------------------------------------

    @OETestDepends([
        'test_30_si_cl1_pfdi.'
        'SafetyIslandTestBase.test_01_pfdi_cluster_status'
    ])
    def test_11_pfdi_result(self):
        for cpu in range(self.cpu_count):
            with self.subTest(cpu=cpu):
                out = self.cli.result(cpu)
                self.assertRegex(
                    out,
                    rf"cpu{cpu}.*SUCCESS",
                )

    # --------------------------------------------------
    # State toggle
    # --------------------------------------------------
    @OETestDepends([
        'test_30_si_cl1_pfdi.'
        'SafetyIslandTestBase.test_01_pfdi_cluster_status'
    ])
    def test_12_pfdi_set_state_toggle(self):
        for cpu in range(self.cpu_count):
            with self.subTest(cpu=cpu):

                self.cli.set_state(cpu, 0)
                out = self.cli.get_status(cpu)
                self.assertRegex(out, r"(disabled|stopped)")

                self.cli.set_state(cpu, 1)
                out = self.cli.get_status(cpu)
                self.assertRegex(out, r"running")

    # --------------------------------------------------
    # Force error behavior
    # --------------------------------------------------

    @OETestDepends([
        'test_30_si_cl1_pfdi.'
        'SafetyIslandTestBase.test_01_pfdi_cluster_status'
    ])
    def test_13_pfdi_force_error_effect(self):
        for cpu in range(self.cpu_count):
            with self.subTest(cpu=cpu):

                out = self.cli.force_error(cpu, 1)
                self.assertRegex(out, r"forced|error-id")

                out = self.cli.result(cpu)
                self.assertRegex(out, r"FAILED")

    # --------------------------------------------------
    # Stability
    # --------------------------------------------------
    @OETestDepends([
        'test_30_si_cl1_pfdi.'
        'SafetyIslandTestBase.test_01_pfdi_cluster_status'
    ])
    def test_02_pfdi_run_all_tests(self):
        for cpu in range(self.cpu_count):
            with self.subTest(cpu=cpu):
                out = self.cli.run_tests(cpu)

                self.assertRegex(out, r"rc=0")
                self.assertRegex(
                    out,
                    r"scheduled:\s*\d+,\s*success:\s*\d+,\s*skipped:\s*\d+"
                )

    @OETestDepends([
        'test_30_si_cl1_pfdi.'
        'SafetyIslandTestBase.test_01_pfdi_cluster_status'
    ])
    def test_14_pfdi_multiple_runs_consistency_3x(self):
        for cpu in range(self.cpu_count):
            with self.subTest(cpu=cpu):

                for _ in range(3):
                    out = self.cli.run_tests(cpu)

                    self.assertRegex(out, r"rc=0")

                    self.assertRegex(
                        out,
                        r"scheduled:\s*\d+,\s*success:\s*\d+,\s*skipped:\s*\d+"
                    )

    @OETestDepends([
        'test_30_si_cl1_pfdi.'
        'SafetyIslandTestBase.test_01_pfdi_cluster_status'
    ])
    def test_15_pfdi_stress_5x(self):
        for cpu in range(self.cpu_count):
            with self.subTest(cpu=cpu):

                for _ in range(5):
                    out = self.cli.run_tests(cpu)

                    self.assertRegex(out, r"rc=0")

                    self.assertRegex(
                        out,
                        r"scheduled:\s*\d+,\s*success:\s*\d+,\s*skipped:\s*\d+"
                    )

    @OETestDepends([
        'test_30_si_cl1_pfdi.'
        'SafetyIslandTestBase.test_01_pfdi_cluster_status'
    ])
    def test_16_pfdi_info(self):
        out = self.cli.run("pfdi info 0")

        raw_value = self.td.get('SI_PFDI_DUMMY_TESTS', '')
        pfdi_dummy_tests = raw_value not in ("0", "1") or raw_value == "1"

        if pfdi_dummy_tests:
            self.assertRegex(
                out,
                r'pfdi: cpu0 firmware: stub implementation detected'
                r' \(no vendor library\)'
            )
        else:
            self.assertRegex(
                out,
                r"pfdi: cpu0 firmware: vendor=0x[0-9a-fA-F]+ "
                r"impl=0x[0-9a-fA-F]+ "
                r"version=\d+\.\d+"
            )
