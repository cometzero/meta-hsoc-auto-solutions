#
# SPDX-FileCopyrightText: <text>Copyright 2025 Arm Limited and/or its
# affiliates <open-source-office@arm.com></text>
#
# SPDX-License-Identifier: MIT

from oeqa.core.decorator.depends import OETestDepends
from oeqa.runtime.case import OERuntimeTestCase


class TfaCpuTopologyTest(OERuntimeTestCase):
    @OETestDepends(
        [
            "test_00_tfa_secure_partition_boot."
            "TfaSecurePartitionBootTest.test_secure_partition_boot"
        ]
    )
    def test_configured_pc_cpus_in_tfa(self):
        pc_cpus_count = int(self.td.get("PC_CPUS_COUNT"))

        for cpu in range(1, pc_cpus_count):
            self.target.expect(
                "tf-a",
                rf"I/TC: Secondary CPU {cpu} "
                rf"switching to normal world boot",
                timeout=500,
            )
