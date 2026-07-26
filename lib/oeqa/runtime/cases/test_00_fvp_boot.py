# SPDX-License-Identifier: MIT

import pexpect

from oeqa.runtime.case import OERuntimeTestCase


class FVPBootTest(OERuntimeTestCase):
    def test_fvp_boot(self):
        self.target.transition("off")
        timeout = int(self.td.get("TEST_FVP_LINUX_BOOT_TIMEOUT") or 10 * 60)
        self.target.transition("linux", timeout)

        for console in self.target.config["consoles"]:
            match = self.target.expect(
                console,
                [br"(\[ERR\]|\[ERROR\]|ERROR\:)", pexpect.TIMEOUT],
                timeout=0,
            )
            self.assertEqual(match, 1)
