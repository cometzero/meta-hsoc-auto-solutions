#
# SPDX-FileCopyrightText: <text>Copyright 2023-2026 Arm Limited and/or its
# affiliates <open-source-office@arm.com></text>
#
# SPDX-License-Identifier: MIT

from oeqa.runtime.case import OERuntimeTestCase
from oeqa.core.decorator.depends import OETestDepends
import pexpect


class PowerSCMITest(OERuntimeTestCase):
    def setUp(self):
        super().setUp()
        self.rse_console = 'rse'
        self.tfa_console = 'tf-a'
        self.linux_console = self.target.DEFAULT_CONSOLE
        self.platform = self.td.get('MACHINE')
        self.timeout = int(self.td.get('TEST_FVP_LINUX_BOOT_TIMEOUT') or 900)
        self.linux_provider = self.td.get('PREFERRED_PROVIDER_virtual/kernel')

    @OETestDepends([
        'test_00_rse_boot.RseBootTest.test_normal_boot',
        'test_00_linux_boot.LinuxBootTest.test_linux_boot',
    ])
    def test_scmi_poweroff(self):
        # Switch to Linux terminal
        self.target.transition('linux')

        # Login to Linux
        self.target.sendline(self.linux_console, 'root')
        self.target.expect(self.linux_console,
                           rf'root@{self.platform}:~#',
                           self.timeout)

        # Perform poweroff command
        self.target.sendline(self.linux_console, 'poweroff')
        self.target.expect(self.linux_console,
                           r'reboot: Power down',
                           timeout=180)

        # Check if RSE has received SCMI shutdown notification
        self.target.expect(self.rse_console,
                           r'\[NOT\]\[SCMI\] System shutdown complete',
                           timeout=180)

        # Check if FVP has closed
        self.target.expect(self.rse_console, pexpect.EOF, timeout=60)

        # Turn off FVP to leave the system in the correct state
        self.target.transition('off')

    @OETestDepends([
        'test_00_rse_boot.RseBootTest.test_normal_boot',
        'test_00_linux_boot.LinuxBootTest.test_linux_boot',
    ])
    def test_scmi_reboot(self):
        # Activate FVP and login to Linux
        self.target.transition('linux', timeout=self.timeout)
        self.target.sendline(self.linux_console, 'root')
        self.target.expect(self.linux_console,
                           rf'root@{self.platform}:~#',
                           self.timeout)

        # Perform reboot command
        self.target.sendline(self.linux_console, 'reboot')
        # On demos, a reboot banner may or may not appear
        # sometimes the console jumps straight back
        # to the login prompt. Try briefly for a banner
        # if not seen, continue with the RSE/TF-A checks below.
        try:
            self.target.expect(self.linux_console,
                               r'reboot: Restarting system',
                               timeout=180)
        except (pexpect.exceptions.TIMEOUT, pexpect.exceptions.EOF):
            pass

        # Check if RSE has received SCMI reset notification
        self.target.expect(self.rse_console,
                           r'\[NOT\]\[SCMI\] Resetting system',
                           timeout=180)

        # Check if RSE has reset
        self.target.expect(self.rse_console,
                           r'\[INF\] Starting TF-M BL1_1',
                           timeout=180)

        # Check if TF-A has restarted. We should see an SCMI
        # log message.
        self.target.expect(self.tfa_console,
                           r'INFO:    SCMI driver initialized',
                           timeout=180)

        # Check if Linux has rebooted
        self.target.expect(self.linux_console,
                           rf'{self.platform} login:',
                           timeout=self.timeout)

        self.target.sendline(self.linux_console, 'root')
        self.target.expect(self.linux_console,
                           rf'root@{self.platform}:~#',
                           self.timeout)

        # Turn off FVP to leave the system in the correct state
        self.target.transition('off')
