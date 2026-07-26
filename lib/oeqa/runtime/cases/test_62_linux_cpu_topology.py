#
# SPDX-FileCopyrightText: <text>Copyright 2025 Arm Limited and/or its
# affiliates <open-source-office@arm.com></text>
#
# SPDX-License-Identifier: MIT

from oeqa.core.decorator.depends import OETestDepends
from oeqa.runtime.case import OERuntimeTestCase


class LinuxCPUTopologyTest(OERuntimeTestCase):
    def setUp(self):
        super().setUp()
        self.timeout = int(
            self.td.get("TEST_FVP_LINUX_BOOT_TIMEOUT") or 900
        )
        self.console_name = self.target.DEFAULT_CONSOLE
        self.hostname = r"[\w\-]+"
        self.pc_cpus_count = int(self.td.get("PC_CPUS_COUNT"))

    @OETestDepends(
        [
            "test_60_linux_connectivity."
            "LinuxConnectivityTest.test_ssh"
        ]
    )
    def test_configured_pc_cpus_in_linux(self):
        self.target.transition("linux", self.timeout)
        self.target.sendline(self.console_name, "root")
        self.target.expect(
            self.console_name,
            rf"root@{self.hostname}:~#",
            timeout=600,
        )

        status, output = self.target.run(
            "find /sys/firmware/devicetree/base/cpus/ "
            '-maxdepth 1 -name "cpu@*" | wc -l',
            timeout=500,
        )
        self.assertEqual(status, 0)

        try:
            count_cpus = int(output)
        except ValueError:
            self.fail(
                f"Expected number of CPUs, but found this:\n{output}"
            )

        self.assertEqual(count_cpus, self.pc_cpus_count)

        status, output = self.target.run("nproc --all", timeout=500)
        self.assertEqual(status, 0)
        self.assertEqual(int(output), self.pc_cpus_count)
