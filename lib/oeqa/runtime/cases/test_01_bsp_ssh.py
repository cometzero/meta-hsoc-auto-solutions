# SPDX-License-Identifier: MIT

import signal
import time
from typing import Protocol

from oeqa.core.decorator.depends import OETestDepends
from oeqa.runtime.case import OERuntimeTestCase
from oeqa.runtime.decorator.package import OEHasPackage


class BspSshTarget(Protocol):
    def run_ssh(
        self,
        command: str,
        timeout: int | None = None,
    ) -> tuple[int, str]: ...


class BspSshTest(OERuntimeTestCase):
    target: BspSshTarget

    @OETestDepends(["test_00_bsp_boot.BspBootTest.test_bsp_boot"])
    @OEHasPackage(["dropbear"])
    def test_bsp_ssh(self):
        status = 255
        output = "not attempted"
        for _attempt in range(5):
            status, output = self.target.run_ssh("uname -a", timeout=30)
            if status == 0:
                break
            if status in (255, -signal.SIGTERM):
                time.sleep(5)
                continue
            self.fail(f'BSP SSH uname failed with "{output}" (exit code {status})')

        self.assertEqual(status, 0, msg=f'BSP SSH failed with "{output}"')
        self.assertIn("Linux", output)
