#
# SPDX-FileCopyrightText: <text>Copyright 2024-2026 Arm Limited and/or its
# affiliates <open-source-office@arm.com></text>
#
# SPDX-License-Identifier: MIT

from oeqa.core.decorator.depends import OETestDepends
from oeqa.runtime.case import OERuntimeTestCase


class UbootBootTest(OERuntimeTestCase):
    @OETestDepends(
        ["test_00_rse_boot.RseBootTest.test_normal_boot"]
    )
    def test_uboot_boot(self):
        console = self.target.DEFAULT_CONSOLE
        self.target.expect(console, r"U-Boot", timeout=120)
        self.target.expect(
            console,
            r"Hit any key to stop autoboot:",
            timeout=120,
        )
