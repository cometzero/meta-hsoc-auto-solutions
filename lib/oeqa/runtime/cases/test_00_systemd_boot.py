#
# SPDX-FileCopyrightText: <text>Copyright 2025-2026 Arm Limited and/or its
# affiliates <open-source-office@arm.com></text>
#
# SPDX-License-Identifier: MIT

from oeqa.core.decorator.depends import OETestDepends
from oeqa.runtime.case import OERuntimeTestCase


class SystemdBootTest(OERuntimeTestCase):
    @OETestDepends(
        ["test_00_uboot_boot.UbootBootTest.test_uboot_boot"]
    )
    def test_systemd_boot(self):
        console = self.target.DEFAULT_CONSOLE
        self.target.expect(console, r"Boot in ", timeout=120)
        self.target.expect(
            console,
            r"Booting Linux on physical CPU",
            timeout=120,
        )
