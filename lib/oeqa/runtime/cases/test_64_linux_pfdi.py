#
# SPDX-FileCopyrightText: <text>Copyright 2025-2026 Arm Limited and/or its
# affiliates <open-source-office@arm.com></text>
#
# SPDX-License-Identifier: MIT

import re

from oeqa.core.decorator.depends import OETestDepends
from oeqa.runtime.case import OERuntimeTestCase
from oeqa.utils.arm_auto_solutions_config import ArmAutoSolutionsConfig


class LinuxPFDITest(OERuntimeTestCase):
    def setUp(self):
        super().setUp()
        self.pc_console = self.target.DEFAULT_CONSOLE
        self.hostname = ArmAutoSolutionsConfig.hostname
        self.cpu_count = int(self.td.get("PC_CPUS_COUNT", "1"))

    @staticmethod
    def check_error_messages(messages):
        error_lines = []
        msg_regex = re.compile(r"(?i)(\[error\])")
        for line in messages.splitlines():
            if msg_regex.search(line):
                error_lines.append(line.strip())
        return error_lines

    @OETestDepends(
        ["test_00_linux_boot.LinuxBootTest.test_linux_boot"]
    )
    def test_init_systemd_service(self):
        status, _ = self.target.run("systemctl status pfdi-app -l")
        self.assertEqual(
            status,
            0,
            msg="systemctl status pfdi-app.service failed",
        )

        self.target.sendline(
            self.pc_console, "journalctl -u pfdi-app"
        )
        self.target.expect(
            self.pc_console,
            rf"Loading config V1.0: running "
            rf"{self.cpu_count} tasks every 60 ms",
            timeout=120,
        )
        self.target.expect(
            self.pc_console,
            rf"root@{self.hostname}:~#",
            timeout=120,
        )

        status, command_output = self.target.run(
            "journalctl -u pfdi-app -l"
        )
        self.assertEqual(status, 0)
        if isinstance(command_output, bytes):
            command_output = command_output.decode(
                "utf-8", errors="replace"
            )
        errors = self.check_error_messages(command_output)
        self.assertListEqual(
            errors,
            [],
            msg=(
                "pfdi-app journal contains error entries:\n"
                + "\n".join(errors)
            ),
        )

    @OETestDepends(
        [
            "test_64_linux_pfdi."
            "LinuxPFDITest.test_init_systemd_service"
        ]
    )
    def test_pfdi_app(self):
        test_start_range = 0
        test_end_range = 40
        time_in_millisecond = 60
        number_of_config_files = 1
        output_directory = "."

        generate_cmd = (
            f"pfdi-tool generate {test_start_range} {test_end_range} "
            f"{time_in_millisecond} {number_of_config_files} "
            f"{self.cpu_count} {output_directory}"
        )
        self.target.sendline(self.pc_console, generate_cmd)
        self.target.expect(
            self.pc_console,
            r"Generated .*pfdi_test_config_0\.yaml with range",
            timeout=120,
        )
        self.target.expect(
            self.pc_console,
            rf"root@{self.hostname}:~#",
            timeout=120,
        )

        pack_cmd = f"pfdi-tool pack {output_directory}"
        self.target.sendline(self.pc_console, pack_cmd)
        self.target.expect(
            self.pc_console,
            r"Validation passed\. Proceeding with packing\.",
            timeout=120,
        )
        self.target.expect(
            self.pc_console,
            r"Binary file written: .*\.pack",
            timeout=120,
        )
        self.target.expect(
            self.pc_console,
            rf"root@{self.hostname}:~#",
            timeout=120,
        )

        self.target.sendline(
            self.pc_console,
            "pfdi-sample-app -ivc pfdi_test_config_0.pack -m single",
        )
        expected_cpus = set(range(self.cpu_count))
        while expected_cpus:
            self.target.expect(
                self.pc_console,
                rf"CPU(\d+): PFDI Online \(OnL\) test "
                rf"\({test_start_range} - {test_end_range}\) OK",
                timeout=120,
            )
            matched_core_id = int(
                self.target.match(self.pc_console)[1]
            )
            self.assertIn(
                matched_core_id,
                expected_cpus,
                msg=(
                    "Duplicate or unknown CPU ID: "
                    f"{matched_core_id}"
                ),
            )
            expected_cpus.remove(matched_core_id)

        self.target.expect(
            self.pc_console,
            rf"root@{self.hostname}:~#",
            timeout=120,
        )

    @OETestDepends(
        ["test_64_linux_pfdi.LinuxPFDITest.test_pfdi_app"]
    )
    def test_pfdi_cli(self):
        self.target.sendline(self.pc_console, "pfdi-cli --info")
        self.target.expect(
            self.pc_console, r"libPFDI version: 1.0", timeout=120
        )

        self.target.sendline(
            self.pc_console, "pfdi-cli --pfdi_info 0"
        )
        raw_value = self.td.get("PFDI_DUMMY_TESTS", "")
        if raw_value not in ("0", "1"):
            pfdi_dummy_tests = True
        else:
            pfdi_dummy_tests = raw_value == "1"

        if pfdi_dummy_tests:
            self.target.expect(
                self.pc_console,
                r"Stub firmware detected - No real diagnostics "
                r"will be executed",
                timeout=120,
            )
        else:
            self.target.expect(
                self.pc_console,
                r"PFDI firmware version "
                r"\((?:vendorId-libId|vendor-lib)-major\.minor\):\s*"
                r"\d+(?:-\d+)?-\d+\.\d+",
                timeout=120,
            )

        self.target.expect(
            self.pc_console,
            rf"root@{self.hostname}:~#",
            timeout=120,
        )

        self.target.sendline(
            self.pc_console, "pfdi-cli --count 0"
        )
        self.target.expect(
            self.pc_console,
            r"CPU0: Firmware reports 41 available diagnostic tests",
            timeout=120,
        )
        self.target.expect(
            self.pc_console,
            rf"root@{self.hostname}:~#",
            timeout=120,
        )

        for core_id in range(self.cpu_count):
            self.target.sendline(
                self.pc_console, f"pfdi-cli --result {core_id}"
            )
            self.target.expect(
                self.pc_console,
                rf"CPU{core_id}: Out of Reset \(OoR\) test OK",
                timeout=300,
            )
            self.target.expect(
                self.pc_console,
                rf"root@{self.hostname}:~#",
                timeout=120,
            )

    @OETestDepends(
        ["test_64_linux_pfdi.LinuxPFDITest.test_pfdi_cli"]
    )
    def test_pfdi_cli_force_error(self):
        self.target.sendline(
            self.pc_console, "pfdi-cli -e 0 RUN ERROR"
        )
        self.target.expect(
            self.pc_console,
            r"CPU0: injected force error.*",
            timeout=120,
        )
        self.target.sendline(
            self.pc_console, "journalctl -u pfdi-app | grep CPU0"
        )
        self.target.expect(
            self.pc_console,
            r"CPU0: PFDI Online \(OnL\) test failed: "
            r"Input/output error \(errno=5\)",
            timeout=120,
        )
        self.target.expect(
            self.pc_console,
            rf"root@{self.hostname}:~#",
            timeout=120,
        )
