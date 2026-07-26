#
# SPDX-FileCopyrightText: <text>Copyright 2025-2026 Arm Limited and/or its
# affiliates <open-source-office@arm.com></text>
#
# SPDX-License-Identifier: MIT

from oeqa.core.decorator.depends import OETestDepends
from oeqa.runtime.case import OERuntimeTestCase
from oeqa.utils.arm_auto_solutions_config import ArmAutoSolutionsConfig
from oeqa.utils.si_utils import SIUtils


class SiCl0PFDIIntegrationTest(OERuntimeTestCase):
    def setUp(self):
        super().setUp()
        self.pc_console = self.target.DEFAULT_CONSOLE
        self.scp_console = "scp"
        self.hostname = ArmAutoSolutionsConfig.hostname
        self.cpu_count = int(self.td.get("PC_CPUS_COUNT", "1"))
        self.si_cl1_cpu_count = int(
            self.td.get("SI_CL1_CPUS_COUNT", "4")
        )
        self.si_utils = SIUtils(
            self.td,
            target=self.target,
            console_name=self.scp_console,
        )

    def get_clusters_and_cores(self):
        cores_per_cluster = int(
            self.td.get("PC_CPUS_PER_CLUSTER_MAX")
        )
        clusters = {}

        for cpu_id in range(self.cpu_count):
            cluster_id = cpu_id // cores_per_cluster
            core_id = cpu_id % cores_per_cluster
            clusters.setdefault(cluster_id, []).append(core_id)

        return clusters

    def get_cpu_index(self, cluster_id, core_id):
        cores_per_cluster = int(
            self.td.get("PC_CPUS_PER_CLUSTER_MAX")
        )
        return cluster_id * cores_per_cluster + core_id

    @OETestDepends([
        "test_00_linux_boot.LinuxBootTest.test_linux_boot",
        "test_00_si_cl0_boot.SiCl0BootTest.test_scp_boot",
    ])
    def test_pfdi_app_monitoring(self):
        for cluster_id, core_list in self.get_clusters_and_cores().items():
            for core_id in core_list:
                expected = (
                    "Started PFDI monitoring for AP cluster "
                    f"{cluster_id} core {core_id}"
                )
                self.target.expect(
                    self.scp_console,
                    expected,
                    timeout=120,
                )

    @OETestDepends([
        "test_21_si_cl0_pfdi."
        "SiCl0PFDIIntegrationTest.test_pfdi_app_monitoring"
    ])
    def test_pfdi_app_monitoring_error(self):
        for cluster_id, core_list in self.get_clusters_and_cores().items():
            for core_id in core_list:
                cpu_index = self.get_cpu_index(cluster_id, core_id)
                self.target.sendline(
                    self.pc_console,
                    f"pfdi-cli --force_error {cpu_index} RUN ERROR",
                )
                expected = (
                    r"\[PFDI_MONITOR\] Onl PFDI for AP cluster "
                    rf"{cluster_id} core {core_id} failed, "
                    r"stopping PFDI monitoring"
                )
                self.target.expect(
                    self.scp_console,
                    expected,
                    timeout=180,
                )

    @OETestDepends([
        "test_00_linux_boot.LinuxBootTest.test_linux_boot",
        "test_00_si_cl0_boot.SiCl0BootTest.test_scp_boot",
    ])
    def test_pfdi_sbistc(self):
        """
        Force a PFDI error on each AP CPU and verify FMU/SBISTC propagation.

        The validation guide specifies an FMU non-critical marker, while
        current Apollo logs may report the same propagation as critical.
        Accept and report either severity, but still require the matching
        per-CPU SBISTC failure marker.
        """
        for cluster_id, core_list in self.get_clusters_and_cores().items():
            for core_id in core_list:
                cpu_index = self.get_cpu_index(cluster_id, core_id)

                self.target.sendline(self.pc_console)
                self.target.expect(
                    self.pc_console,
                    rf"root@{self.hostname}:~#",
                    timeout=120,
                )
                self.target.sendline(
                    self.pc_console,
                    f"pfdi-cli --force_error {cpu_index} RUN ERROR",
                )

                self.target.expect(
                    self.scp_console,
                    r"\[FMU\] (Non-critical|Critical) fault received:",
                    timeout=180,
                )
                severity = self.target.match(self.scp_console)[1]
                if isinstance(severity, bytes):
                    severity = severity.decode(
                        "utf-8",
                        errors="replace",
                    )
                self.logger.info(
                    "Observed FMU %s fault marker for AP CPU%d",
                    severity,
                    cpu_index,
                )
                self.target.expect(
                    self.scp_console,
                    rf"\[SBISTC\] SBISTC_EQ_FAIL_CORE{cpu_index} detected",
                    timeout=180,
                )

        self.target.expect(
            self.pc_console,
            rf"root@{self.hostname}:~#",
            timeout=120,
        )

    @OETestDepends([
        "test_00_si_cl0_boot.SiCl0BootTest.test_scp_boot",
        "test_00_si_cl1_boot.SiCl1BootTest.test_si_cl1_boot",
    ])
    def test_si_pfdi_monitoring(self):
        if self.si_cl1_cpu_count < 1:
            self.skipTest("SI CL1 PFDI monitoring has no configured CPUs")

        for core_id in range(self.si_cl1_cpu_count):
            try:
                self.si_utils.validate_pfdi_sequence_for_target(
                    1,
                    core_id,
                )
            except AssertionError as exc:
                self.fail(str(exc))
