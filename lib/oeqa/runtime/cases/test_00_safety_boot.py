#
# SPDX-FileCopyrightText: <text>Copyright 2026 Arm Limited and/or its
# affiliates <open-source-office@arm.com></text>
#
# SPDX-License-Identifier: MIT

from oeqa.core.decorator.depends import OETestDepends
from oeqa.runtime.case import OERuntimeTestCase


class SafetyBootTest(OERuntimeTestCase):
    @OETestDepends(
        ["test_00_rse_boot.RseBootTest.test_normal_boot"]
    )
    def test_lbist(self):
        self.target.transition("off")
        self.target.transition("on")
        self.target.expect(
            "rse",
            r"\[INF\] BL2: SI LBIST happens here",
            timeout=60,
        )

    @OETestDepends(
        ["test_00_safety_boot.SafetyBootTest.test_lbist"]
    )
    def test_mbist(self):
        self.target.expect(
            "rse",
            r"\[INF\] BL2: SI MBIST happens here",
            timeout=60,
        )
