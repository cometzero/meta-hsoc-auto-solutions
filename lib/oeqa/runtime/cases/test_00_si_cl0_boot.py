#
# SPDX-FileCopyrightText: <text>Copyright 2024-2026 Arm Limited and/or its
# affiliates <open-source-office@arm.com></text>
#
# SPDX-License-Identifier: MIT

from oeqa.runtime.case import OERuntimeTestCase


class SiCl0BootTest(OERuntimeTestCase):
    def test_scp_boot(self):
        self.target.transition("on")

        for marker in (
            r"SSU initialized",
            r"\[CMN_CYPRUS\] Done",
            r"\[SI0_PLATFORM\] SCP started",
            r"\[FWK\] Module initialization complete!",
        ):
            self.target.expect("scp", marker, timeout=120)
