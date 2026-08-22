#
# Copyright OpenEmbedded Contributors
#
# SPDX-License-Identifier: MIT
#

import signal
import time
from typing import Protocol

import pexpect

from oeqa.controllers.hsocfvp import FVPSerialBootError
from oeqa.core.decorator.depends import OETestDepends
from oeqa.runtime.case import OERuntimeTestCase
from oeqa.runtime.decorator.package import OEHasPackage


SERIAL_COMMAND_TIMEOUT_SECONDS = 15
NETWORK_DIAGNOSTIC_COMMANDS = (
    "ip -4 addr",
    "ip route",
    "networkctl --no-pager --full",
)


class ConnectivityTarget(Protocol):
    def run_serial(
        self,
        command: str,
        timeout: int,
        boot_timeout: int | None = None,
    ) -> tuple[int, str]: ...

    def run(self, command: str, timeout: int) -> tuple[int, str]: ...


class LinuxConnectivityTest(OERuntimeTestCase):
    target: ConnectivityTarget

    def _serial_diagnostics(self):
        diagnostics = []
        for command in NETWORK_DIAGNOSTIC_COMMANDS:
            try:
                status, output = self.target.run_serial(
                    command,
                    timeout=SERIAL_COMMAND_TIMEOUT_SECONDS,
                )
                diagnostics.append(f"$ {command}\nstatus={status}\n{output}")
            except (pexpect.TIMEOUT, pexpect.EOF, FVPSerialBootError) as error:
                diagnostics.append(
                    f"$ {command}\nserial-error={type(error).__name__}: {error}"
                )
        return "\n".join(diagnostics)

    @OETestDepends(["test_00_linux_boot.LinuxBootTest.test_linux_boot"])
    @OEHasPackage(["dropbear", "openssh-sshd"])
    def test_ssh(self):
        status = 255
        output = "not attempted"
        for _ in range(5):
            status, output = self.target.run("uname -a", timeout=30)
            if status == 0:
                break
            if status == 255 or status == -signal.SIGTERM:
                time.sleep(5)
                continue

            diagnostics = self._serial_diagnostics()
            self.fail(
                'uname failed with "%s" (exit code %s)\n%s'
                % (output, status, diagnostics)
            )

        if status != 0:
            diagnostics = self._serial_diagnostics()
            self.fail(
                'ssh failed with "%s" (exit code %s)\n%s'
                % (output, status, diagnostics)
            )
