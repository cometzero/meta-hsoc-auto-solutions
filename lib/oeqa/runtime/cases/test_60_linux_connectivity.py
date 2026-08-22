#
# Copyright OpenEmbedded Contributors
#
# SPDX-License-Identifier: MIT
#

import ipaddress
import shlex
import signal
import time
from subprocess import PIPE, Popen
from time import sleep
from typing import Protocol

from oeqa.core.decorator.depends import OETestDepends
from oeqa.core.decorator.oetimeout import OETimeout
from oeqa.core.exception import OEQATimeoutError
from oeqa.controllers.hsocfvp import FVPSerialBootError
from oeqa.runtime.case import OERuntimeTestCase
from oeqa.runtime.decorator.package import OEHasPackage
import pexpect


NETWORK_READY_TIMEOUT_SECONDS = 120
NETWORK_READY_POLL_SECONDS = 2
SERIAL_COMMAND_TIMEOUT_SECONDS = 15
CONNECTIVITY_TEST_TIMEOUT_SECONDS = 180
NETWORK_DIAGNOSTIC_COMMANDS = (
    "ip -4 addr",
    "ip route",
    "networkctl --no-pager --full",
)


class ConnectivityTarget(Protocol):
    ip: str
    server_ip: str

    def run_serial(
        self,
        command: str,
        timeout: int,
        boot_timeout: int | None = None,
    ) -> tuple[int, str]: ...

    def run(self, command: str, timeout: int) -> tuple[int, str]: ...


class LinuxConnectivityTest(OERuntimeTestCase):
    target: ConnectivityTarget

    def _network_addresses(self):
        target_value = self.target.ip
        server_value = self.target.server_ip
        if target_value.startswith("127.0.0.") or target_value in (
            "localhost",
            "::1",
        ):
            self.fail(
                "runtime/ping: localhost target is not valid for "
                "platform device validation"
            )
        try:
            target_ip = ipaddress.ip_address(target_value)
            server_ip = ipaddress.ip_address(server_value)
        except ValueError as error:
            self.fail(f"runtime/ping: target and server must be valid IPv4: {error}")
        if not isinstance(target_ip, ipaddress.IPv4Address) or not isinstance(
            server_ip,
            ipaddress.IPv4Address,
        ):
            self.fail("runtime/ping: target and server must be valid IPv4")
        return str(target_ip), str(server_ip)

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

    def _wait_for_guest_network(self):
        target_ip, server_ip = self._network_addresses()
        target_pattern = shlex.quote(f"inet {target_ip}/")
        server = shlex.quote(server_ip)
        command = (
            f"ip -o -4 addr show | grep -F {target_pattern} >/dev/null && "
            f"ip route get {server} >/dev/null 2>&1 && "
            f"ping -c 1 -W 2 {server}"
        )
        deadline = time.monotonic() + NETWORK_READY_TIMEOUT_SECONDS
        last_status = None
        last_output = "not attempted"
        while time.monotonic() < deadline:
            remaining = max(1, int(deadline - time.monotonic()))
            command_timeout = min(SERIAL_COMMAND_TIMEOUT_SECONDS, remaining)
            try:
                last_status, last_output = self.target.run_serial(
                    command,
                    timeout=command_timeout,
                    boot_timeout=remaining,
                )
            except FVPSerialBootError as error:
                self.fail(
                    "Guest Linux boot failed before network readiness; "
                    f"network diagnostics unavailable before shell login:\n{error}"
                )
            except pexpect.EOF as error:
                diagnostics = self._serial_diagnostics()
                self.fail(
                    "Guest serial console reached EOF before network readiness; "
                    f"network diagnostics follow:\n{error}\n{diagnostics}"
                )
            except pexpect.TIMEOUT as error:
                last_status = None
                last_output = f"{type(error).__name__}: {error}"
            if last_status == 0:
                return target_ip, server_ip
            delay = min(
                NETWORK_READY_POLL_SECONDS,
                max(0, deadline - time.monotonic()),
            )
            if delay:
                sleep(delay)
        diagnostics = self._serial_diagnostics()
        self.fail(
            f"Guest network readiness timeout after "
            f"{NETWORK_READY_TIMEOUT_SECONDS}s for target {target_ip} and "
            f"server {server_ip}; last status={last_status}, "
            f"last output={last_output}\n{diagnostics}"
        )

    @OETestDepends(
        ["test_00_linux_boot.LinuxBootTest.test_linux_boot"]
    )
    @OETimeout(CONNECTIVITY_TEST_TIMEOUT_SECONDS)
    def test_ping(self):
        output = ""
        count = 0
        self.assertNotEqual(
            len(self.target.ip), 0, msg="No target IP address set"
        )

        target_ip, _server_ip = self._wait_for_guest_network()

        try:
            while count < 5:
                proc = Popen(["ping", "-c", "1", target_ip], stdout=PIPE)
                output += proc.communicate()[0].decode("utf-8")
                if proc.poll() == 0:
                    count += 1
                else:
                    count = 0
                    sleep(1)
        except OEQATimeoutError:
            diagnostics = self._serial_diagnostics()
            self.fail(
                "Ping timeout error for address %s, count %s, output: %s\n%s"
                % (target_ip, count, output, diagnostics)
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
