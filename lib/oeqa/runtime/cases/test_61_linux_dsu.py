#
# SPDX-FileCopyrightText: <text>Copyright 2025 Arm Limited and/or its
# affiliates <open-source-office@arm.com></text>
#
# SPDX-License-Identifier: MIT

from oeqa.core.decorator.depends import OETestDepends
from oeqa.runtime.case import OERuntimeTestCase


class LinuxDSUTest(OERuntimeTestCase):
    def setUp(self):
        super().setUp()
        self.timeout = int(
            self.td.get("TEST_FVP_LINUX_BOOT_TIMEOUT") or 900
        )
        self.console_name = self.target.DEFAULT_CONSOLE
        self.hostname = r"[\w\-]+"
        self.max_cluster_count = int(self.td.get("PC_CLUSTER_COUNT_MAX"))
        self.max_cpus_per_cluster = int(
            self.td.get("PC_CPUS_PER_CLUSTER_MAX")
        )
        self.pc_cpus_count = int(self.td.get("PC_CPUS_COUNT"))
        self.num_dsu_cluster = int(
            (self.pc_cpus_count + self.max_cpus_per_cluster - 1)
            / self.max_cpus_per_cluster
        )

    def check_dsu_l3_cache(self):
        num_of_cpus_per_dsu_cluster = []
        shared_cpu_list = []
        start_cpu_num = 0

        for _ in range(self.num_dsu_cluster):
            cluster_cpu_count = min(
                self.max_cluster_count, self.pc_cpus_count
            )
            num_of_cpus_per_dsu_cluster.append(cluster_cpu_count)
            end_cpu_num = start_cpu_num + cluster_cpu_count - 1
            if cluster_cpu_count > 1:
                shared_cpu_list.append(
                    f"{start_cpu_num}-{end_cpu_num}"
                )
            else:
                shared_cpu_list.append(str(start_cpu_num))
            self.pc_cpus_count -= cluster_cpu_count
            start_cpu_num += self.max_cluster_count

        for dsu_cluster_num in range(self.num_dsu_cluster):
            for cpu in range(
                num_of_cpus_per_dsu_cluster[dsu_cluster_num]
            ):
                cpu_id = (
                    dsu_cluster_num * self.max_cpus_per_cluster + cpu
                )

                status, output = self.target.run(
                    f"cat /sys/devices/system/cpu/cpu{cpu_id}/cache/"
                    "index3/size",
                    timeout=50,
                )
                self.assertEqual(status, 0)
                self.assertEqual(output, "4096K")

                status, output = self.target.run(
                    f"cat /sys/devices/system/cpu/cpu{cpu_id}/cache/"
                    "index3/shared_cpu_list",
                    timeout=50,
                )
                self.assertEqual(status, 0)
                self.assertEqual(
                    output, shared_cpu_list[dsu_cluster_num]
                )

    def check_dsu_pmu_counters(self):
        for dsu_cluster_num in range(self.num_dsu_cluster):
            # 0x002A counts L3 cache refills and 0x002B counts L3 cache
            # accesses issued to the SCU.
            events = ["event=0x002A", "event=0x002B"]

            for event_name in events:
                status, output = self.target.run(
                    rf"perf stat -e arm_dsu_{dsu_cluster_num}/"
                    rf"{event_name}/ -- ls",
                    timeout=500,
                )
                self.assertEqual(status, 0)
                self.assertRegex(
                    output,
                    rf"[0-9]+\s+arm_dsu_{dsu_cluster_num}/"
                    rf"{event_name}/",
                )

    @OETestDepends(
        [
            "test_60_linux_connectivity."
            "LinuxConnectivityTest.test_ssh"
        ]
    )
    def test_dsu_cluster(self):
        self.target.transition("linux", self.timeout)
        self.target.sendline(self.console_name, "root")
        self.target.expect(
            self.console_name,
            rf"root@{self.hostname}:~#",
            timeout=600,
        )

        self.check_dsu_l3_cache()
        self.check_dsu_pmu_counters()
