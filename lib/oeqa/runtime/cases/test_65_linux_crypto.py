#
# SPDX-FileCopyrightText: <text>Copyright 2025 Arm Limited and/or its
# affiliates <open-source-office@arm.com></text>
#
# SPDX-License-Identifier: MIT

import re
import time
from typing import Dict

from oeqa.core.decorator.depends import OETestDepends
from oeqa.runtime.case import OERuntimeTestCase
from oeqa.utils.arm_auto_solutions_config import ArmAutoSolutionsConfig
from oeqa.utils.linux_terminal_utils import LinuxTermUtils


class LinuxCryptoExtensionTest(OERuntimeTestCase):
    DEFAULT_TIMEOUT = 600
    WORK_DIR = "/tmp/apollo-oeqa-crypto"

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.prompt = ArmAutoSolutionsConfig.baremetal_prompt
        cls.linux_console = cls.tc.target._get_terminal("default")
        cls.lt_utils = LinuxTermUtils(
            cls.tc, cls.linux_console, cls.prompt
        )

    def run_ok(
        self, cmd: str, timeout: int = DEFAULT_TIMEOUT, msg: str = None
    ) -> str:
        status, output = self.lt_utils.run(cmd, timeout)
        self.assertEqual(
            status,
            0,
            msg or f"command failed rc={status}: {cmd}\n{output}",
        )
        return output.strip()

    def _generate_certificate(self):
        cert_cmd = (
            f"install -d {self.WORK_DIR} && cd {self.WORK_DIR} && "
            "openssl req -x509 -newkey rsa:2048 "
            "-keyout server-key.pem -out server-cert.pem "
            "-days 365 -nodes -subj "
            "'/C=AU/ST=Some-State/O=Internet Widgits Pty Ltd/"
            "CN=localhost'"
        )
        self.run_ok(
            cert_cmd,
            timeout=120,
            msg="Failed to generate certificate",
        )

    def _start_ssl_server(self):
        server_cmd = (
            f"sh -c 'cd {self.WORK_DIR} && (while true; "
            "do dd if=/dev/urandom bs=1M count=10 2>/dev/null | "
            "openssl s_server -cert server-cert.pem "
            "-key server-key.pem -accept 4433 "
            "-quiet -naccept 1; done) &'"
        )
        self.run_ok(server_cmd, msg="Failed to start SSL server")
        time.sleep(2)

    def _cleanup_server(self):
        try:
            self.run_ok(
                "fg",
                timeout=5,
                msg="Failed to bring server to foreground",
            )
        except AssertionError:
            try:
                self.run_ok(
                    "pkill -f 's_server'",
                    timeout=10,
                    msg="Failed to kill server processes",
                )
            except AssertionError:
                self.fail("Failed to cleanup server processes")

    def _extract_time_from_output(
        self, output: str
    ) -> Dict[str, float]:
        def parse_time(pattern: str, label: str) -> float:
            match = re.search(pattern, output)
            if not match:
                self.fail(
                    f"Could not extract {label} time from output: "
                    f"{output}"
                )
            minutes = int(match.group(1)) if match.group(1) else 0
            seconds = float(match.group(2))
            return minutes * 60 + seconds

        patterns = {
            "real": r"real\s+(?:(\d+)m)?(\d+(?:\.\d+)?)s",
            "user": r"user\s+(?:(\d+)m)?(\d+(?:\.\d+)?)s",
            "sys": r"sys\s+(?:(\d+)m)?(\d+(?:\.\d+)?)s",
        }
        return {
            key: parse_time(pattern, key)
            for key, pattern in patterns.items()
        }

    def _download_with_crypto_extension(self):
        download_cmd = (
            "time sh -c 'echo -e "
            '"GET / HTTP/1.1\\r\\nHost: localhost\\r\\n'
            'Connection: close\\r\\n\\r\\n" '
            "| openssl s_client -connect localhost:4433 "
            "-cipher AES256-GCM-SHA384 "
            "-servername localhost -quiet > /dev/null'"
        )
        return self.run_ok(
            download_cmd,
            msg=(
                "Failed to download file with crypto extension "
                "enabled"
            ),
        )

    def _download_without_crypto_extension(self):
        download_cmd = (
            "time sh -c 'echo -e "
            '"GET / HTTP/1.1\\r\\nHost: localhost\\r\\n'
            'Connection: close\\r\\n\\r\\n" '
            "| OPENSSL_armcap=0x0 openssl s_client "
            "-connect localhost:4433 "
            "-cipher AES256-GCM-SHA384 "
            "-servername localhost -quiet > /dev/null'"
        )
        return self.run_ok(
            download_cmd,
            msg=(
                "Failed to download file with crypto extension "
                "disabled"
            ),
        )

    def _cleanup_files(self):
        cleanup_cmds = [
            f"rm -f {self.WORK_DIR}/server-key.pem",
            f"rm -f {self.WORK_DIR}/server-cert.pem",
            f"rmdir {self.WORK_DIR}",
        ]
        for cmd in cleanup_cmds:
            try:
                self.run_ok(
                    cmd, timeout=10, msg=f"Failed to cleanup: {cmd}"
                )
            except AssertionError:
                self.fail(f"Failed to cleanup: {cmd}")

    @OETestDepends(
        ["test_00_linux_boot.LinuxBootTest.test_linux_boot"]
    )
    def test_cryptographic_extension_performance(self):
        try:
            self._generate_certificate()
            self._start_ssl_server()

            with_crypto_output = (
                self._download_with_crypto_extension()
            )
            with_crypto_times = self._extract_time_from_output(
                with_crypto_output
            )

            without_crypto_output = (
                self._download_without_crypto_extension()
            )
            without_crypto_times = self._extract_time_from_output(
                without_crypto_output
            )

            self.assertGreater(
                without_crypto_times.get("real", 0),
                with_crypto_times.get("real", 0),
                msg=(
                    "Crypto extension should provide better "
                    "performance (lower real time)"
                ),
            )
            self.assertGreater(
                without_crypto_times.get("user", 0),
                with_crypto_times.get("user", 0),
                msg=(
                    "Crypto extension should reduce CPU time "
                    "(lower user time)"
                ),
            )
        finally:
            try:
                self._cleanup_server()
            finally:
                self._cleanup_files()
