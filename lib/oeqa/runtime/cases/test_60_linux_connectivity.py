#
# Copyright OpenEmbedded Contributors
#
# SPDX-License-Identifier: MIT
#

import signal
import time
from subprocess import PIPE, Popen
from time import sleep

from oeqa.core.decorator.depends import OETestDepends
from oeqa.core.decorator.oetimeout import OETimeout
from oeqa.core.exception import OEQATimeoutError
from oeqa.runtime.case import OERuntimeTestCase, run_network_serialdebug
from oeqa.runtime.decorator.package import OEHasPackage


class LinuxConnectivityTest(OERuntimeTestCase):

    @OETestDepends(
        ["test_00_linux_boot.LinuxBootTest.test_linux_boot"]
    )
    @OETimeout(30)
    def test_ping(self):
        output = ""
        count = 0
        self.assertNotEqual(
            len(self.target.ip), 0, msg="No target IP address set"
        )

        if self.target.ip.startswith("127.0.0.") or self.target.ip in (
            "localhost",
            "::1",
        ):
            print("runtime/ping: localhost detected, not pinging")
            return

        try:
            while count < 5:
                cmd = "ping -c 1 %s" % self.target.ip
                proc = Popen(cmd, shell=True, stdout=PIPE)
                output += proc.communicate()[0].decode("utf-8")
                if proc.poll() == 0:
                    count += 1
                else:
                    count = 0
                    sleep(1)
        except OEQATimeoutError:
            run_network_serialdebug(self.target.runner)
            self.fail(
                "Ping timeout error for address %s, count %s, output: %s"
                % (self.target.ip, count, output)
            )

        msg = (
            "Expected 5 consecutive, got %d.\n"
            "ping output is:\n%s" % (count, output)
        )
        self.assertEqual(count, 5, msg=msg)

    @OETestDepends(
        [
            "test_60_linux_connectivity."
            "LinuxConnectivityTest.test_ping"
        ]
    )
    @OEHasPackage(["dropbear", "openssh-sshd"])
    def test_ssh(self):
        for _ in range(5):
            status, output = self.target.run("uname -a", timeout=30)
            if status == 0:
                break
            if status == 255 or status == -signal.SIGTERM:
                time.sleep(5)
                continue

            run_network_serialdebug(self.target.runner)
            self.fail(
                'uname failed with "%s" (exit code %s)'
                % (output, status)
            )

        if status != 0:
            self.fail(
                'ssh failed with "%s" (exit code %s)'
                % (output, status)
            )
