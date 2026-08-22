#
# SPDX-License-Identifier: MIT
#

from oeqa.runtime.case import OERuntimeTestCase
from oeqa.runtime.decorator.package import OEHasPackage
from oeqa.core.decorator.depends import OETestDepends
from oeqa.utils.arm_auto_solutions_config import ArmAutoSolutionsConfig
from oeqa.utils.apollo_psa_validation import parse_psa_summary
from oeqa.utils.linux_terminal_utils import LinuxTermUtils


class TrustedServicesTest(OERuntimeTestCase):
    SECURE_FAILURE_MARKERS = ("E/TC", "FF-A: error", "FF-A: failed")

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.linux_console = cls.tc.target._get_terminal("default")
        cls.linux_terminal = LinuxTermUtils(
            cls.tc,
            cls.linux_console,
            ArmAutoSolutionsConfig.baremetal_prompt,
        )

    def run_test_tool(self, cmd):
        status, output = self.linux_terminal.run(cmd, timeout=1200)
        self.assertEqual(
            status, 0, msg="\n".join([cmd, output])
        )
        self.assertTrue(output.strip(), msg=f"{cmd} produced empty output")
        try:
            parse_psa_summary(output)
        except ValueError as error:
            self.fail(f"{cmd} invalid PSA summary: {error}\n{output}")
        secure_output = self.target.before("tf-a")
        if isinstance(secure_output, bytes):
            secure_output = secure_output.decode("utf-8", errors="replace")
        self.assertFalse(
            any(marker in secure_output for marker in self.SECURE_FAILURE_MARKERS),
            msg=f"secure console error while running {cmd}:\n{secure_output}",
        )

    @OEHasPackage(["ts-psa-crypto-api-test"])
    @OETestDepends(
        [
            "test_00_linux_boot.LinuxBootTest.test_linux_boot"
        ]
    )
    def test_03_psa_crypto_api_test(self):
        self.run_test_tool("psa-crypto-api-test")

    @OEHasPackage(["ts-psa-ps-api-test"])
    @OETestDepends(
        [
            "test_00_linux_boot.LinuxBootTest.test_linux_boot"
        ]
    )
    def test_05_psa_ps_api_test(self):
        self.run_test_tool("psa-ps-api-test")

    @OEHasPackage(["ts-psa-its-api-test"])
    @OETestDepends(
        [
            "test_00_linux_boot.LinuxBootTest.test_linux_boot"
        ]
    )
    def test_04_psa_its_api_test(self):
        self.run_test_tool("psa-its-api-test")

    @OEHasPackage(["ts-psa-iat-api-test"])
    @OETestDepends(
        [
            "test_00_linux_boot.LinuxBootTest.test_linux_boot"
        ]
    )
    def test_06_psa_iat_api_test(self):
        self.run_test_tool("psa-iat-api-test")
