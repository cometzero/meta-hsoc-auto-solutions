#
# SPDX-FileCopyrightText: <text>Copyright 2025 Arm Limited and/or its
# affiliates <open-source-office@arm.com></text>
#
# SPDX-License-Identifier: MIT

import re
import shlex
from typing import Dict

from oeqa.core.decorator.depends import OETestDepends
from oeqa.runtime.case import OERuntimeTestCase
from oeqa.utils.arm_auto_solutions_config import ArmAutoSolutionsConfig
from oeqa.utils.apollo_crypto_validation import validate_crypto_samples
from oeqa.utils.linux_terminal_utils import LinuxTermUtils


class LinuxCryptoExtensionTest(OERuntimeTestCase):
    DEFAULT_TIMEOUT = 600
    WORK_DIR = "/tmp/apollo-oeqa-crypto"
    SAMPLE_COUNT = 3

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
        command = "sh -c " + shlex.quote(
            f"{cmd}; status=$?; cd /; exit $status"
        )
        status, output = self.lt_utils.run(command, timeout)
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
            f"cd {self.WORK_DIR} || exit; command -v setsid >/dev/null || exit; "
            "setsid sh -c 'while true; do dd if=/dev/urandom bs=1M "
            "count=10 2>/dev/null | openssl s_server "
            "-cert server-cert.pem -key server-key.pem -accept 4433 "
            "-quiet -naccept 1; done' > server.log 2>&1 & "
            "server_pid=$!; echo $server_pid > server.pid; "
            "awk '{print $22}' /proc/$(cat server.pid)/stat > server.start && "
            "for try in $(seq 1 20); do "
            "grep -qi ':1151' /proc/net/tcp /proc/net/tcp6 && exit 0; "
            "sleep 1; done; exit 1"
        )
        self.run_ok(server_cmd, msg="Failed to start SSL server")

    def _cleanup_server(self):
        identity_cmd = (
            f"test -s {self.WORK_DIR}/server.pid && "
            f"test -s {self.WORK_DIR}/server.start && "
            f"pid=$(cat {self.WORK_DIR}/server.pid) && "
            f"test \"$(awk '{{print $22}}' /proc/$pid/stat)\" = "
            f"\"$(cat {self.WORK_DIR}/server.start)\""
        )
        self.run_ok(identity_cmd, timeout=20, msg="SSL server identity changed")
        stop_cmd = (
            f"pid=$(cat {self.WORK_DIR}/server.pid) && "
            "kill -TERM -$pid && "
            "for try in $(seq 1 20); do "
            "kill -0 $pid 2>/dev/null || exit 0; sleep 1; done; exit 1"
        )
        self.run_ok(stop_cmd, timeout=30, msg="Failed to stop SSL server")

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
        self.run_ok(
            f"rm -rf {self.WORK_DIR} && test ! -e {self.WORK_DIR}",
            timeout=20,
            msg="Failed to remove crypto test files",
        )

    def _sample_downloads(self, enabled: bool):
        download = (
            self._download_with_crypto_extension
            if enabled
            else self._download_without_crypto_extension
        )
        return tuple(
            self._extract_time_from_output(download())
            for _ in range(self.SAMPLE_COUNT)
        )

    @OETestDepends(
        ["test_00_linux_boot.LinuxBootTest.test_linux_boot"]
    )
    def test_cryptographic_extension_performance(self):
        try:
            self._generate_certificate()
            self._start_ssl_server()

            with_crypto_samples = self._sample_downloads(enabled=True)
            without_crypto_samples = self._sample_downloads(enabled=False)

            try:
                validate_crypto_samples(
                    with_crypto_samples,
                    without_crypto_samples,
                )
            except ValueError as error:
                self.fail(f"Crypto extension timing validation failed: {error}")
        finally:
            try:
                self._cleanup_server()
            finally:
                self._cleanup_files()
