#
# SPDX-FileCopyrightText: <text>Copyright 2025-2026 Arm Limited and/or its
# affiliates <open-source-office@arm.com></text>
#
# SPDX-License-Identifier: MIT
#
# noqa: SIZE_OK - kept aligned with the upstream cpufreq validation sequence.

from oeqa.core.decorator.depends import OETestDepends
from oeqa.runtime.case import OERuntimeTestCase
from oeqa.utils.arm_auto_solutions_config import ArmAutoSolutionsConfig
from oeqa.utils.linux_terminal_utils import LinuxTermUtils

import posixpath as p
import time
from typing import Dict, List, Union
import re


class CPUFrequencyTest(OERuntimeTestCase):
    """OEQA runtime tests for validating CPU frequency sysfs state.

    This class contains tests for CPU frequency scaling governors,
    policies, and frequency management functionality.
    """

    CPU_FREQUENCY_SYSFS = "/sys/devices/system/cpu/cpufreq"
    DEFAULT_TIMEOUT = 120
    MAX_FREQ_EXPECTED = 2500000
    MIN_FREQ_EXPECTED = 1800000

    GOVERNORS = ["ondemand", "performance", "powersave", "schedutil"]

    # Test frequency values for min/max tests
    TEST_FREQUENCIES_EXPECTED = [1800000, 2000000, 2500000]
    POLICIES: Dict[str, str] = {}

    @classmethod
    def setUpClass(cls):
        """Set up test environment and verify CPU frequency support."""
        super(CPUFrequencyTest, cls).setUpClass()
        cls.prompt = ArmAutoSolutionsConfig.baremetal_prompt
        cls.linux_console = cls.tc.target._get_terminal("default")
        cls.lt_utils = LinuxTermUtils(cls.tc, cls.linux_console, cls.prompt)

    def run_ok(self, cmd: str, timeout: int = DEFAULT_TIMEOUT,
               msg: str = None) -> str:
        """
        Run a command on the target and assert rc == 0.
        retry for 3 times if rc == 1
        """
        retries = 3
        for _ in range(retries):
            status, out = self.lt_utils.run(cmd, timeout)
            if status == 1:
                time.sleep(2)
            else:
                break
        self.assertEqual(
            status, 0,
            msg or f"command failed rc={status}: {cmd}\n{out}"
        )
        return out.strip()

    def cat(self, path: str, timeout: int = DEFAULT_TIMEOUT,
            msg: str = None) -> str:
        """Read file content using cat command."""
        return self.run_ok(f"cat {path}", timeout,  msg)

    def write(self, path: str, value: Union[str, int],
              timeout: int = None, msg: str = None):
        """Write value to file using shell redirection.
        Args:
            path: File path to write to
            value: Value to write
            timeout: Command timeout in seconds
            msg: Custom error message
        """
        # Use sh for redirection; assumes tests run as root
        cmd = f"echo {value} > {path}"
        return self.run_ok(cmd, timeout,  msg)

    def try_write(self, path: str, value: Union[str, int],
                  timeout: int = DEFAULT_TIMEOUT):
        return self.lt_utils.run(f"echo {value} > {path}", timeout)

    def _list_policy_dirs(self, root_dir: str) -> Dict[str, str]:
        """List CPU frequency policy directories."""
        base = self.CPU_FREQUENCY_SYSFS
        # List policy directories robustly
        cmd = (f"for d in {root_dir}; "
               f"do [ -d \"$d\" ] && basename \"$d\"; done")
        out = self.run_ok(cmd)
        for line in out.splitlines():
            name = line.strip()
            if name:
                self.POLICIES[name] = p.join(base, name)
        return False if self.POLICIES == {} else True

    def _list_supported_frequencies(self, policy_dir: str) -> List[int]:
        """Get list of supported frequencies for a policy."""
        freq_path = p.join(policy_dir, "scaling_available_frequencies")
        freqs = self.cat(freq_path)
        return [int(f) for f in freqs.split()]

    # Parse the online CPUs string, e.g., "0-3,5,7-8"
    def _cpu_cluster_map(self, s: str) -> set:
        """
        Get the actual CPU cores online from the linux sysfs via command
        cat /sys/devices/system/cpu/online.
        Example o/p of above command: '0-3,5,7-8' is expanded as
        {0,1,2,3,5,7,8} and count how many clusters are represented.
        Here we are assuming 4 CPUs per cluster.
        """
        cpus = set()
        for a, b in re.compile(r'(\d+)(?:-(\d+))?').findall(s):
            start = int(a)
            end = int(b) if b else start
            cpus.update(range(start, end + 1))
        groups = [
            set(range(0, 4)),
            set(range(4, 8)),
            set(range(8, 12)),
            set(range(12, 16)),
        ]
        return sum(1 for g in groups if cpus & g)

    def _list_affected_cpus(self, policy: str) -> List[int]:
        """List all CPUs affected by a given policy."""
        cmd = f"cat {self.CPU_FREQUENCY_SYSFS}/{policy}/affected_cpus"
        out = self.run_ok(cmd)
        return sorted([int(x) for x in out.split()])

    def _get_policy_path(self, policy: str, filename: str) -> str:
        """Get full path to a policy file."""
        return p.join(self.CPU_FREQUENCY_SYSFS, policy, filename)

    def _read_governor(self, policy_dir: str) -> str:
        """Read current governor for a policy."""
        return self.cat(p.join(policy_dir, "scaling_governor"))

    def _write_governor(self, policy_dir: str, governor: str):
        """Write governor for a policy."""
        path = p.join(policy_dir, "scaling_governor")
        self.write(path, governor)

    def _restore_governor(self, policy_dirs: Dict[str, str],
                          policy: str, default_governor: str):
        """Restore default governor for a policy."""
        self._write_governor(policy_dirs[policy], default_governor)

    @OETestDepends([
        'test_00_linux_boot.LinuxBootTest.test_linux_boot'
    ])
    def test_cpu_frequency_policy(self):
        """Validate policies are available for all online cores."""
        self.assertTrue(self._list_policy_dirs(
            p.join(self.CPU_FREQUENCY_SYSFS, "policy*")),
            'CPUfreq (DVFS) framework is not enabled')

        expected_cpus_online = int(self.td.get('PC_CPUS_COUNT'))
        actual_online_cpus = int(self.run_ok("nproc --all"))
        self.assertEqual(
            actual_online_cpus,
            expected_cpus_online,
            f"Expected {expected_cpus_online} online CPUs,"
            f" got {actual_online_cpus}"
        )
        # Get the list of actual online CPU cores
        online_cpus = self.run_ok("cat /sys/devices/system/cpu/online")
        # Count CPU clusters based on online CPUs
        cluster_count = self._cpu_cluster_map(online_cpus)
        policy_count = len(self.POLICIES.keys())
        self.assertEqual(
            policy_count,
            cluster_count,
            f"Expected {cluster_count} policies for {cluster_count} CPU "
            f"clusters, got {policy_count} policies"
        )

        """
        Verify available CPUFreq governors per
        performance domain (policy per domain)
        """
        for policy in self.POLICIES.keys():
            # Read available governors
            available_path = p.join(
                self.POLICIES[policy],
                "scaling_available_governors"
            )

            available_governors = self.cat(available_path).split()

            # Sort both lists for comparison
            available_sorted = sorted(available_governors)
            expected_sorted = sorted(self.GOVERNORS)

            self.assertEqual(
                available_sorted,
                expected_sorted,
                f"Available governors {available_sorted} do not match "
                f"expected {expected_sorted} for policy {policy}"
            )

    @OETestDepends([
        'test_72_power_cpufreq.CPUFrequencyTest.test_cpu_frequency_policy'
    ])
    def test_cpufreq_default_governors(self):
        """Verify default governor is 'schedutil' for all policies."""
        for policy in self.POLICIES.keys():
            governor = self._read_governor(self.POLICIES[policy])
            self.assertEqual(
                governor,
                "schedutil",
                f"Default governor is '{governor}', expected 'schedutil' "
                f"for policy {policy}"
            )

    @OETestDepends([
        'test_72_power_cpufreq.CPUFrequencyTest.test_cpu_frequency_policy'
    ])
    def test_cpufreq_set_governors(self):
        """Verify CPU frequency governors can be set for all policies."""
        for policy in self.POLICIES.keys():
            default_governor = self._read_governor(self.POLICIES[policy])

            for governor in self.GOVERNORS:
                with self.subTest(governor=governor, policy=policy):
                    try:
                        # Set governor
                        self.write(
                            p.join(self.POLICIES[policy], "scaling_governor"),
                            governor
                        )
                        # Verify governor was set
                        current_governor = self.cat(
                            p.join(self.POLICIES[policy], "scaling_governor")
                        )
                        self.assertEqual(
                            current_governor,
                            governor,
                            f"Failed to set governor '{governor}' for policy "
                            f"{policy}. Current: '{current_governor}'"
                        )
                    except AssertionError as e:
                        self.fail(f"Failed to set governor '{governor}' "
                                  f"for policy {policy}: {e}")
            # Cleanup: restore default governor after each subTest
            self._restore_governor(self.POLICIES,
                                   policy,
                                   default_governor)

    @OETestDepends([
        'test_72_power_cpufreq.CPUFrequencyTest.test_cpu_frequency_policy'
    ])
    def test_cpufreq_scaling_driver(self):
        """Verify CPU frequency scaling driver is present for all policies."""
        for policy in self.POLICIES.keys():
            driver_path = p.join(self.POLICIES[policy], "scaling_driver")
            driver = self.cat(driver_path)
            self.assertEqual(
                driver,
                "scmi",
                f"Expected 'scmi' scaling driver, got '{driver}' "
                f"for policy {policy}"
            )

    @OETestDepends([
        'test_72_power_cpufreq.CPUFrequencyTest.test_cpu_frequency_policy'
    ])
    def test_current_frequency_per_governor(self):
        """Verify current frequency is reported correctly for each governor."""
        for policy in self.POLICIES.keys():
            policy_path = self.POLICIES[policy]
            default_governor = self._read_governor(policy_path)

            for governor in self.GOVERNORS:
                with self.subTest(governor=governor, policy=policy):
                    current_governor = self._read_governor(policy_path)
                    if current_governor != governor:
                        # Set the governor
                        self._write_governor(policy_path, governor)

                    # Read current frequency
                    freq_path = p.join(policy_path, "scaling_cur_freq")
                    current_freq = int(self.cat(freq_path))
                    self.assertIn(
                        current_freq,
                        self.TEST_FREQUENCIES_EXPECTED,
                        (
                            f"{current_freq} is not in expected frequencies "
                            f"{self.TEST_FREQUENCIES_EXPECTED} for governor "
                            f"{governor} of policy {policy}"
                        )
                    )
            # Restore default governor
            self._restore_governor(self.POLICIES, policy, default_governor)

    @OETestDepends([
        'test_72_power_cpufreq.CPUFrequencyTest.test_cpu_frequency_policy'
    ])
    def test_cpufreq_affected_cpus_per_policy(self):
        """
        Verify CPU frequency changes apply to affected CPU's
        within the performance domain.
        """
        for policy in self.POLICIES.keys():
            affected_cpus = self._list_affected_cpus(policy)

            # Extract policy number and calculate expected CPU range
            # Assumes policy names like 'policy0', 'policy1', etc.
            policy_num = int(policy.replace('policy', ''))
            expected_cpus = list(range(policy_num, (policy_num + 4)))

            self.assertTrue(
                set(affected_cpus).issubset(set(expected_cpus)),
                f"Affected CPUs {affected_cpus} do not match expected "
                f"{expected_cpus} for policy {policy}"
            )

    @OETestDepends([
        'test_72_power_cpufreq.CPUFrequencyTest.test_cpu_frequency_policy'
    ])
    def test_update_invalid_governor(self):
        """Verify setting invalid governor fails gracefully."""
        for policy in self.POLICIES.keys():
            current_governor = self._read_governor(self.POLICIES[policy])

            try:
                invalid_governor = "invalid_governor"
                self._write_governor(self.POLICIES[policy], invalid_governor)
            except AssertionError:
                updated_governor = self._read_governor(self.POLICIES[policy])
                self.assertEqual(
                    updated_governor,
                    current_governor,
                    f"Invalid governor '{invalid_governor}' was incorrectly "
                    f"accepted for policy {policy}"
                )
            else:
                self.fail(
                    f"Writing invalid governor '{invalid_governor}' "
                    f"unexpectedly succeeded for policy {policy}"
                )
            finally:
                # Restore original governor
                self._restore_governor(self.POLICIES, policy, current_governor)

    @OETestDepends([
        'test_72_power_cpufreq.CPUFrequencyTest.test_cpu_frequency_policy'
    ])
    def test_update_scaling_min_frequencies(self):
        """Verify CPU frequency scaling minimum frequencies can be updated."""
        for policy in self.POLICIES.keys():
            min_freq_path = p.join(self.POLICIES[policy], "scaling_min_freq")
            max_freq_path = p.join(self.POLICIES[policy], "scaling_max_freq")

            original_min_freq = int(self.cat(min_freq_path))
            max_freq = int(self.cat(max_freq_path))

            for frequency in self.TEST_FREQUENCIES_EXPECTED:
                if frequency != original_min_freq and frequency <= max_freq:
                    # Set minimum frequency
                    self.write(min_freq_path, frequency)

                    # Verify it was set
                    updated_min_freq = int(self.cat(min_freq_path))
                    self.assertEqual(
                        updated_min_freq,
                        frequency,
                        f"Failed to set minimum frequency {frequency} "
                        f"for policy {policy}"
                    )
            # Restore original minimum frequency
            self.write(min_freq_path, original_min_freq)

    @OETestDepends([
        'test_72_power_cpufreq.CPUFrequencyTest.test_cpu_frequency_policy'
    ])
    def test_update_scaling_max_frequencies(self):
        """Verify CPU frequency scaling maximum frequencies can be updated."""
        for policy in self.POLICIES.keys():
            min_freq_path = p.join(self.POLICIES[policy], "scaling_min_freq")
            max_freq_path = p.join(self.POLICIES[policy], "scaling_max_freq")

            min_freq = int(self.cat(min_freq_path))
            original_max_freq = int(self.cat(max_freq_path))

            for frequency in self.TEST_FREQUENCIES_EXPECTED:
                if frequency != original_max_freq and frequency >= min_freq:
                    # Set maximum frequency
                    self.write(max_freq_path, frequency)
                    # Verify it was set
                    updated_max_freq = int(self.cat(max_freq_path))
                    self.assertEqual(
                        updated_max_freq,
                        frequency,
                        f"Failed to set maximum frequency {frequency} "
                        f"for policy {policy}"
                    )

            # Restore original maximum frequency
            self.write(max_freq_path, original_max_freq)

    @OETestDepends([
        'test_72_power_cpufreq.CPUFrequencyTest.test_cpu_frequency_policy'
    ])
    def test_update_min_max_scaling_frequencies_negative(self):
        """Verify invalid min/max frequency settings are rejected.

        Test that minimum frequency cannot be set higher than maximum
        frequency and vice versa for all policies.
        """
        for policy in self.POLICIES.keys():
            min_freq_path = p.join(self.POLICIES[policy], "scaling_min_freq")
            max_freq_path = p.join(self.POLICIES[policy], "scaling_max_freq")

            original_min_freq = self.cat(min_freq_path)
            original_max_freq = self.cat(max_freq_path)

            try:
                invalid_min_freq = str(int(original_max_freq) + 100000)
                status, _ = self.try_write(min_freq_path, invalid_min_freq)
                if status == 0:
                    updated_min_freq = int(self.cat(min_freq_path))
                    current_max_freq = int(self.cat(max_freq_path))
                    self.assertLessEqual(
                        updated_min_freq,
                        current_max_freq,
                        f"Invalid min frequency {invalid_min_freq} was "
                        f"incorrectly accepted for policy {policy}"
                    )
            finally:
                self.write(min_freq_path, original_min_freq)
                self.write(max_freq_path, original_max_freq)

            try:
                invalid_max_freq = str(int(original_min_freq) - 100000)
                status, _ = self.try_write(max_freq_path, invalid_max_freq)
                if status == 0:
                    updated_max_freq = int(self.cat(max_freq_path))
                    current_min_freq = int(self.cat(min_freq_path))
                    self.assertGreaterEqual(
                        updated_max_freq,
                        current_min_freq,
                        f"Invalid max frequency {invalid_max_freq} was "
                        f"incorrectly accepted for policy {policy}"
                    )
            finally:
                self.write(max_freq_path, original_max_freq)
                self.write(min_freq_path, original_min_freq)
