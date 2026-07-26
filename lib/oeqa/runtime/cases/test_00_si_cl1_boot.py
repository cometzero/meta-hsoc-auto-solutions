#
# SPDX-FileCopyrightText: <text>Copyright 2023-2026 Arm Limited and/or its
# affiliates <open-source-office@arm.com></text>
#
# SPDX-License-Identifier: MIT

from oeqa.core.decorator.data import skipIfDataVar
from oeqa.core.decorator.depends import OETestDepends
from oeqa.runtime.case import OERuntimeTestCase


class SiCl1BootTest(OERuntimeTestCase):
    @skipIfDataVar(
        "RD_ASPEN_VARIANT",
        "cfg1",
        "requires RD_ASPEN_VARIANT=cfg2 (CL1 present)",
    )
    @OETestDepends(
        ["test_00_si_cl0_boot.SiCl0BootTest.test_scp_boot"]
    )
    def test_si_cl1_boot(self):
        self.target.expect("safety_island_c1", r"Hello World", timeout=120)

    @skipIfDataVar(
        "RD_ASPEN_VARIANT",
        "cfg1",
        "requires RD_ASPEN_VARIANT=cfg2 (CL1 present)",
    )
    @OETestDepends(
        ["test_00_si_cl1_boot.SiCl1BootTest.test_si_cl1_boot"]
    )
    def test_secondary_cores(self):
        for cpu in range(1, 4):
            self.target.expect(
                "safety_island_c1",
                rf"Secondary CPU core {cpu} "
                rf"\(MPID:0x10{cpu}00\) is up",
                timeout=120,
            )
