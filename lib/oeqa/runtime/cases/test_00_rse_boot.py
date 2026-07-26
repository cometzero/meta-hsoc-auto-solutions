#
# SPDX-FileCopyrightText: <text>Copyright 2023-2026 Arm Limited and/or its
# affiliates <open-source-office@arm.com></text>
#
# SPDX-License-Identifier: MIT

from oeqa.core.decorator.depends import OETestDepends
from oeqa.runtime.case import OERuntimeTestCase


class RseBootTest(OERuntimeTestCase):
    def setUp(self):
        super().setUp()
        self.rse_console = "rse"

    def test_normal_boot(self):
        self.target.transition("on")

        for expected, failure_message in (
            (
                "SI CL0 is released out of reset",
                "Failed to release SI CL0 out of reset",
            ),
            (
                "Init SCMI comm to SCP succeeded",
                "init SCMI comm to SCP failed",
            ),
            (
                "RSE to SCP SCMI power on AP succeeded",
                "RSE to SCP SCMI power on AP failed",
            ),
        ):
            result = self.target.expect(
                self.rse_console, expected, timeout=60
            )
            self.assertEqual(result, 0, failure_message)

        self.target.expect(
            self.rse_console,
            r"Jumping to the first image slot",
            timeout=60,
        )
        self.assertNotIn(b"[ERR]", self.target.before(self.rse_console))

        result = self.target.expect(
            self.rse_console,
            r"SCMI Comms subscribed to power state notifications",
            timeout=60,
        )
        self.assertEqual(
            result,
            0,
            "SCMI Comms failed to subscribe to power state notifications",
        )

    @OETestDepends(
        ["test_00_rse_boot.RseBootTest.test_normal_boot"]
    )
    def test_measured_boot(self):
        self.target.transition("off")
        self.target.transition("on")

        sw_types = ["BL1_2", "BL2"]
        if self.td.get("RD_ASPEN_VARIANT", "cfg2") != "cfg1":
            sw_types.append("SI_CL1")
        sw_types.extend(
            [
                "SI_CL0",
                "AP_BL2",
                "RT_0",
                "FW_CONFIG",
                "SECURE_RT_EL3",
                "HW_CONFIG",
                "SECURE_RT_EL1_SPMD",
                "BL_33",
            ]
        )

        for sw_type in sw_types:
            self.target.expect(
                self.rse_console,
                rf"MeasuredBoot: Extending measurement for sw_type: "
                rf"{sw_type}",
                timeout=60,
            )

        self.assertNotIn(b"[ERR]", self.target.before(self.rse_console))
