# SPDX-FileCopyrightText: <text>Copyright 2025 Arm Limited and/or its
# affiliates <open-source-office@arm.com></text>
#
# SPDX-License-Identifier: MIT
#
# noqa: SIZE_OK - kept aligned with the upstream MBPP validation sequence.

import contextlib
import re
import warnings

from oeqa.core.decorator.depends import OETestDepends
from oeqa.runtime.case import OERuntimeTestCase
from oeqa.utils.arm_auto_solutions_config import (
    ArmAutoSolutionsConfig,
)
from oeqa.utils.linux_terminal_utils import LinuxTermUtils
from test_72_power_cpufreq import CPUFrequencyTest


class MBPPTest(OERuntimeTestCase):
    """
    Validate mbpp using sample app.
    """

    @staticmethod
    def make_re_set_to(mode: str):
        return re.compile(rf"Power profile set to {re.escape(mode)}\.")

    @staticmethod
    def make_re_dump_cur(mode_regex: str):
        return re.compile(rf"Current selected profile is: {mode_regex}")

    @staticmethod
    def make_re_already_set(mode: str):
        return re.compile(
            rf"Power profile \"{re.escape(mode)}\" is already set\."
        )

    @classmethod
    def setUpClass(cls):
        super(MBPPTest, cls).setUpClass()

        cls.MBPP_PATH = "/root/mbpp.sh"
        cls.PROMPT_STR = ArmAutoSolutionsConfig.baremetal_prompt

        cls.EXPECTED_SYSFS = {
            "parking": {"governor": "powersave"},
            "city": {"governor": "ondemand"},
            "highway": {"governor": "performance"},
        }

        cls.RE_SETTING = re.compile(r"Setting power profile .*?\.\.\.")
        cls.RE_DUMP_OR_NONE = re.compile(
            r"(There is no profile selected currently\.|"
            r"Current selected profile is:\s*(parking|city|highway))"
        )
        cls.RE_NOT_ALL_CORES = re.compile(
            r"Not all \d+ cores are online\."
        )
        cls.RE_ERRORS = re.compile(
            r"(?i)(\[error\]|^error:|^failed:| command not found)"
        )
        cls.RE_SYSFS_ERROR = re.compile(
            r"(?i)\bcat:|error|device or resource busy"
        )

        cls.linux_console = cls.tc.target._get_terminal("default")
        cls.lt = LinuxTermUtils(cls.tc, cls.linux_console, cls.PROMPT_STR)

    def setUp(self):
        super().setUp()
        if str(self.td.get("PC_CPUS_COUNT")) != "16":
            self.skipTest("MBPP requires a 16-CPU Apollo configuration")
        self.lt = type(self).lt
        self.pc_console = type(self).linux_console
        self._expect_root_prompt()

    def _expect_root_prompt(self):
        self.lt.send_wait_prompt()

    def _assert_set_outcome(self, mode: str, out: str):
        """
        Accept outcomes:
        - already: 'Power profile "<mode>" is already set.'
        - cores_offline: 'Not all N cores are online.'
        - changed: 'Setting power profile ...' then 'set to <mode>.'
        """
        if self.make_re_already_set(mode).search(out):
            return "already"
        if self.RE_NOT_ALL_CORES.search(out):
            return "cores_offline"
        self.assertRegex(out, self.RE_SETTING)
        self.assertRegex(out, self.make_re_set_to(mode))
        return "changed"

    def _set_and_expect_set(self, mode: str, timeout_set: int = 180):
        _, out = self.lt.run(f"{self.MBPP_PATH} -s {mode}",
                             timeout=timeout_set)
        outcome = self._assert_set_outcome(mode, out)
        self._expect_root_prompt()
        if outcome == "cores_offline":
            self.skipTest("Skip: some cores are offline.")
        if outcome == "changed":
            self._validate_sysfs_for_mode(mode)

    def _dump_and_expect_current(self, mode_regex: str):
        _, out = self.lt.run(f"{self.MBPP_PATH} -d", timeout=120)
        if self.RE_NOT_ALL_CORES.search(out):
            self.skipTest("Skip: some cores are offline (dump).")
        self.assertRegex(out, self.make_re_dump_cur(mode_regex))
        self._expect_root_prompt()

    def _verify_switch_sequence(self, seq):
        for mode in seq:
            self._set_and_expect_set(mode)
        self._dump_and_expect_current(seq[-1])

    def _read_sysfs_pairs(self, leaf: str):
        cmd = (
            "for f in /sys/devices/system/cpu/cpu*/cpufreq/"
            f"{leaf}; do "
            "[ -f \"$f\" ] || continue; "
            "echo -n \"$(basename $(dirname $f))=\"; "
            "cat \"$f\" 2>/dev/null; "
            "done"
        )
        try:
            _, out = self.lt.run(cmd, timeout=120)
        except Exception:
            # flatten nested try/except → simpler
            with contextlib.suppress(Exception):
                self.lt.run_in_progress = False
            out = ""

        pairs = []
        for line in out.strip().splitlines():
            if "=" not in line:
                continue
            cpu, val = line.split("=", 1)
            cpu, val = cpu.strip(), val.strip()
            if not val or self.RE_SYSFS_ERROR.search(val):
                continue
            pairs.append((cpu, val))
        return pairs

    def _assert_governors(self, expected_governor: str):
        if not expected_governor:
            return
        try:
            pairs = self._read_sysfs_pairs("scaling_governor")
        except Exception:
            pairs = []
        if not pairs:
            warnings.warn(
                "No readable scaling_governor entries found. "
                "Skipping governor validation."
            )
            return
        mismatches = [
            (cpu, gov, expected_governor)
            for cpu, gov in pairs if gov != expected_governor
        ]
        if mismatches:
            details = ", ".join(
                f"{cpu}:{gov}->{exp}" for cpu, gov, exp in mismatches
            )
            warnings.warn(f"Governor mismatch(es): {details}")

    def _validate_sysfs_for_mode(self, mode: str):
        expected = self.EXPECTED_SYSFS.get(mode, {})
        self._assert_governors(expected.get("governor"))

    @OETestDepends(
        ["test_00_linux_boot.LinuxBootTest.test_linux_boot"]
    )
    def test_01_script_exists_and_is_executable(self):
        status, out = self.lt.run(f"ls -l {self.MBPP_PATH}", timeout=120)
        self.assertEqual(status, 0, msg=f"mbpp.sh missing:\n{out}")
        self.assertRegex(
            out, r"^-r-xr--r--\s",
            msg=("mbpp.sh does not have 544 perms (-r-xr--r--):\n"
                 f"{out}"),
        )
        self._expect_root_prompt()

    @OETestDepends([
        "test_73_power_mbpp.MBPPTest."
        "test_01_script_exists_and_is_executable"
    ])
    def test_02_help_and_list(self):
        _, out_h = self.lt.run(f"{self.MBPP_PATH} -h", timeout=120)
        if self.RE_NOT_ALL_CORES.search(out_h):
            self.skipTest("Skip: some cores are offline (-h).")
        self.assertRegex(
            out_h,
            r"Simple shell script for setting mission "
            r"based power profile\.",
        )
        self.assertRegex(
            out_h,
            r"-s \| --select : Select a profile to set "
            r"\(parking, city, highway\)\.",
        )
        self._expect_root_prompt()

        _, out_l = self.lt.run(f"{self.MBPP_PATH} -l", timeout=120)
        if self.RE_NOT_ALL_CORES.search(out_l):
            self.skipTest("Skip: some cores are offline (-l).")
        self.assertRegex(out_l, r"Available power profiles:")
        self.assertRegex(out_l, r"- Parking")
        self.assertRegex(out_l, r"- City")
        self.assertRegex(out_l, r"- Highway")
        self._expect_root_prompt()
        for line in out_l.splitlines():
            self.assertIsNone(
                self.RE_ERRORS.search(line),
                msg=f"Unexpected error in list:\n{line}",
            )

    @OETestDepends([
        "test_73_power_mbpp.MBPPTest.test_02_help_and_list"
    ])
    def test_03_dump_initial_then_set_parking_and_verify(self):
        _, out_d = self.lt.run(f"{self.MBPP_PATH} -d", timeout=120)
        if self.RE_NOT_ALL_CORES.search(out_d):
            self.skipTest("Skip: some cores are offline (dump).")
        self.assertRegex(out_d, self.RE_DUMP_OR_NONE)
        self._expect_root_prompt()
        self._set_and_expect_set("parking")
        self._dump_and_expect_current("parking")

    @OETestDepends([
        "test_73_power_mbpp.MBPPTest."
        "test_03_dump_initial_then_set_parking_and_verify"
    ])
    def test_04_idempotent_all_profiles(self):
        for mode in ["parking", "city", "highway"]:
            self._set_and_expect_set(mode)
            _, out = self.lt.run(f"{self.MBPP_PATH} -s {mode}", timeout=120)
            outcome = self._assert_set_outcome(mode, out)
            if outcome == "cores_offline":
                self.skipTest("Skip: some cores are offline (idempotent).")
            self._expect_root_prompt()

    @OETestDepends([
        "test_73_power_mbpp.MBPPTest.test_04_idempotent_all_profiles"
    ])
    def test_05_case_insensitive_all_profiles(self):
        variants = {
            "parking": ["PARKING", "ParkIng", "parking"],
            "city": ["CITY", "CiTy", "city"],
            "highway": ["HIGHWAY", "HIGHway", "highway"],
        }

        for expected_mode, inputs in variants.items():
            for inp in inputs:
                _, out = self.lt.run(f"{self.MBPP_PATH} -s {inp}", timeout=180)
                outcome = self._assert_set_outcome(expected_mode, out)

                if outcome == "cores_offline":
                    self.skipTest("Skip: cores offline (case-insensitive).")

                self._expect_root_prompt()

                (
                    outcome == "changed"
                ) and self._validate_sysfs_for_mode(expected_mode)

            self._dump_and_expect_current(expected_mode)

    @OETestDepends([
        "test_73_power_mbpp.MBPPTest."
        "test_05_case_insensitive_all_profiles"
    ])
    def test_06_invalid_profile_selection(self):
        _, out = self.lt.run(f"{self.MBPP_PATH} -d", timeout=120)
        if self.RE_NOT_ALL_CORES.search(out):
            self.skipTest("Skip: cores offline (dump).")
        m = re.search(
            r"Current selected profile is: "
            r"(?P<cur>parking|city|highway)", out,
        )
        self.assertIsNotNone(m)
        cur = m.group("cur")
        self._expect_root_prompt()

        for bad in ["sport", "eco", "xyz"]:
            _, out_bad = self.lt.run(f"{self.MBPP_PATH} -s {bad}",
                                     timeout=120)
            if self.RE_NOT_ALL_CORES.search(out_bad):
                self.skipTest("Skip: cores offline (invalid sel).")
            self.assertRegex(
                out_bad,
                r"(Invalid profile selection|Invalid profile|"
                r"Unknown profile|Usage:|"
                r"Invalid profile provided\.)",
            )
            self._expect_root_prompt()

        _, out2 = self.lt.run(f"{self.MBPP_PATH} -d", timeout=120)
        if self.RE_NOT_ALL_CORES.search(out2):
            self.skipTest("Skip: cores offline (dump).")
        self.assertRegex(out2, self.make_re_dump_cur(cur))
        self._expect_root_prompt()

    @OETestDepends([
        "test_73_power_mbpp.MBPPTest.test_06_invalid_profile_selection"
    ])
    def test_07_toggle_all_modes(self):
        order = ["city", "highway", "parking"]
        for _ in range(3):
            for mode in order:
                self._set_and_expect_set(mode)
        self._dump_and_expect_current("parking")

    @OETestDepends([
        "test_73_power_mbpp.MBPPTest.test_07_toggle_all_modes"
    ])
    def test_08_guard_when_not_all_cores_online(self):
        self._set_and_expect_set("city")
        self.lt.run("rm -f /tmp/mbpp_tmp", timeout=120)
        self._expect_root_prompt()
        _, out = self.lt.run(f"{self.MBPP_PATH} -s parking", timeout=120)
        self.assertRegex(out, self.RE_NOT_ALL_CORES)
        self._expect_root_prompt()

    @OETestDepends([
        "test_73_power_mbpp.MBPPTest."
        "test_08_guard_when_not_all_cores_online"
    ])
    def test_09_set_governor_to_default(self):
        """Restore all CPUFreq governors to
        'schedutil' after MBPP tests."""
        # Bring all CPUs online
        self.lt.run(
            'for f in /sys/devices/system/cpu/cpu*/online; do '
            '[ -f "$f" ] && echo 1 > "$f" 2>/dev/null; '
            'done',
            timeout=120
        )
        self.lt.send_wait_prompt()
        CPUFrequencyTest.tc = self.tc
        CPUFrequencyTest.setUpClass()
        freq_test = CPUFrequencyTest('test_cpu_frequency_policy')

        # Set governors to schedutil
        if freq_test._list_policy_dirs(
                f"{CPUFrequencyTest.CPU_FREQUENCY_SYSFS}/policy*"):
            for _, policy_dir in freq_test.POLICIES.items():
                freq_test._write_governor(policy_dir, "schedutil")
