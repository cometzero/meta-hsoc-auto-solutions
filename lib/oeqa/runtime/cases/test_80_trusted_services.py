#
# SPDX-License-Identifier: MIT
#

from oeqa.core.decorator.depends import OETestDepends
from oeqa.runtime.case import OERuntimeTestCase
from oeqa.runtime.decorator.package import OEHasPackage


class TrustedServicesTest(OERuntimeTestCase):
    def run_test_tool(
        self, cmd, expected_status=0, expected_output=None
    ):
        status, output = self.target.run(cmd)
        self.assertEqual(
            status, expected_status, msg="\n".join([cmd, output])
        )
        if expected_output is not None:
            self.assertEqual(
                output,
                expected_output,
                msg="\n".join([cmd, output]),
            )

    @OEHasPackage(["ts-psa-crypto-api-test"])
    @OETestDepends(
        [
            "test_60_linux_connectivity."
            "LinuxConnectivityTest.test_ssh"
        ]
    )
    def test_03_psa_crypto_api_test(self):
        self.run_test_tool("psa-crypto-api-test")

    @OEHasPackage(["ts-psa-ps-api-test"])
    @OETestDepends(
        [
            "test_60_linux_connectivity."
            "LinuxConnectivityTest.test_ssh"
        ]
    )
    def test_05_psa_ps_api_test(self):
        self.run_test_tool("psa-ps-api-test")

    @OEHasPackage(["ts-psa-its-api-test"])
    @OETestDepends(
        [
            "test_60_linux_connectivity."
            "LinuxConnectivityTest.test_ssh"
        ]
    )
    def test_04_psa_its_api_test(self):
        self.run_test_tool("psa-its-api-test")

    @OEHasPackage(["ts-psa-iat-api-test"])
    @OETestDepends(
        [
            "test_60_linux_connectivity."
            "LinuxConnectivityTest.test_ssh"
        ]
    )
    def test_06_psa_iat_api_test(self):
        self.run_test_tool("psa-iat-api-test")
