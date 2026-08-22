# SPDX-FileCopyrightText: <text>Copyright 2025 Arm Limited and/or its
# affiliates <open-source-office@arm.com></text>
#
# SPDX-License-Identifier: MIT
#
# noqa: SIZE_OK - kept aligned with the upstream MBPP validation sequence.

import re

from oeqa.core.decorator.depends import OETestDepends
from oeqa.runtime.case import OERuntimeTestCase
from oeqa.utils.arm_auto_solutions_config import (
    ArmAutoSolutionsConfig,
)
from oeqa.utils.linux_terminal_utils import LinuxTermUtils


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
        self.assertEqual(
            str(self.td.get("PC_CPUS_COUNT")),
            "16",
            "MBPP requires a 16-CPU Apollo configuration",
        )
        self.lt = type(self).lt
        self.pc_console = type(self).linux_console
        self._expect_root_prompt()

    @classmethod
    def tearDownClass(cls):
        try:
            cls._restore_default_state()
        finally:
            super(MBPPTest, cls).tearDownClass()

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
            self.fail("not all 16 cores are online")
        if outcome == "changed":
            self._validate_sysfs_for_mode(mode)

    def _dump_and_expect_current(self, mode_regex: str):
        _, out = self.lt.run(f"{self.MBPP_PATH} -d", timeout=120)
        if self.RE_NOT_ALL_CORES.search(out):
            self.fail("not all 16 cores are online during profile dump")
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
        status, out = self.lt.run(cmd, timeout=120)
        self.assertEqual(status, 0, msg=f"failed to read {leaf}:\n{out}")

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
        pairs = self._read_sysfs_pairs("scaling_governor")
        self.assertTrue(pairs, "no readable scaling_governor entries found")
        mismatches = [
            (cpu, gov, expected_governor)
            for cpu, gov in pairs if gov != expected_governor
        ]
        if mismatches:
            details = ", ".join(
                f"{cpu}:{gov}->{exp}" for cpu, gov, exp in mismatches
            )
            self.fail(f"Governor mismatch(es): {details}")

    @classmethod
    def _restore_default_state(cls):
        command = (
            "for f in /sys/devices/system/cpu/cpu*/online; do "
            "[ -f \"$f\" ] && echo 1 > \"$f\"; "
            "done; "
            "for d in /sys/devices/system/cpu/cpufreq/policy*; do "
            "[ -d \"$d\" ] || continue; "
            "echo schedutil > \"$d/scaling_governor\"; "
            "done; "
            "rm -f /tmp/mbpp_tmp; "
            "test \"$(nproc --all)\" -eq 16; "
            "test \"$(nproc)\" -eq 16; "
            "for d in /sys/devices/system/cpu/cpufreq/policy*; do "
            "[ \"$(cat \"$d/scaling_governor\")\" = schedutil ] || exit 1; "
            "done"
        )
        status, out = cls.lt.run(command, timeout=180)
        if status != 0:
            raise AssertionError(
                f"failed to restore MBPP all-online/schedutil state:\n{out}"
            )

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
            self.fail("not all 16 cores are online for MBPP help")
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
            self.fail("not all 16 cores are online for MBPP list")
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
            self.fail("not all 16 cores are online for initial MBPP dump")
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
                self.fail("not all 16 cores are online for idempotent MBPP")
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
                    self.fail("not all 16 cores are online for MBPP case handling")

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
            self.fail("not all 16 cores are online before invalid MBPP input")
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
                self.fail("not all 16 cores are online for invalid MBPP input")
            self.assertRegex(
                out_bad,
                r"(Invalid profile selection|Invalid profile|"
                r"Unknown profile|Usage:|"
                r"Invalid profile provided\.)",
            )
            self._expect_root_prompt()

        _, out2 = self.lt.run(f"{self.MBPP_PATH} -d", timeout=120)
        if self.RE_NOT_ALL_CORES.search(out2):
            self.fail("not all 16 cores are online after invalid MBPP input")
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
        type(self)._restore_default_state()
