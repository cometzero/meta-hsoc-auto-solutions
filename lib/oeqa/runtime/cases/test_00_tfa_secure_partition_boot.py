#
# SPDX-FileCopyrightText: <text>Copyright 2023-2025 Arm Limited and/or its
# affiliates <open-source-office@arm.com></text>
#
# SPDX-License-Identifier: MIT

from oeqa.core.decorator.depends import OETestDepends
from oeqa.runtime.case import OERuntimeTestCase


class TfaSecurePartitionBootTest(OERuntimeTestCase):
    @OETestDepends(
        ["test_00_rse_boot.RseBootTest.test_normal_boot"]
    )
    def test_secure_partition_boot(self):
        self.target.transition("on")

        for marker in (
            r"Loading SP: SE Proxy",
            r"Loading SP: SMM Gateway",
            r"I/TC: Primary CPU switching to normal world boot",
        ):
            self.target.expect("tf-a", marker, timeout=60)

        self.assertNotIn(b"E/TC", self.target.before("tf-a"))
