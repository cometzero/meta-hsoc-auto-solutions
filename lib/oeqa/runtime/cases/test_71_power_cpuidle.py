#
# SPDX-FileCopyrightText: <text>Copyright 2025-2026 Arm Limited and/or its
# affiliates <open-source-office@arm.com></text>
#
# SPDX-License-Identifier: MIT
#
# noqa: SIZE_OK - kept aligned with the upstream cpuidle validation sequence.

from oeqa.runtime.case import OERuntimeTestCase
from oeqa.core.decorator.depends import OETestDepends
from oeqa.utils.linux_terminal_utils import LinuxTermUtils
from oeqa.utils.arm_auto_solutions_config import ArmAutoSolutionsConfig
from oeqa.utils.arm_auto_solutions_decorators import skipIfDataVarWithTestName

import posixpath as p
from typing import Dict
import time


class CPUIdleTest(OERuntimeTestCase):
    """
    OEQA runtime tests for validating CPUIdle C-states
    presence and behavior via sysfs interface.
    """

    CPU_SYSFS = "/sys/devices/system/cpu"
    CPUIDLE_DIR = p.join(CPU_SYSFS, "cpuidle")
    DEFAULT_TIMEOUT = 120
    SLEEP_SHORT = 5
    SLEEP_LONG = 10

    # Expected C-state names and properties
    # (platform-specific; adjust as needed)
    EXPECTED_STATE_NAMES = {
        "state0": "WFI",
        "state1": "cpu-sleep",
        "state2": "cluster-sleep",
    }
    EXPECTED_PROPS = {
        "state0": {"residency": 1, "latency": 1},
        "state1": {"residency": 4200, "latency": 4000},
        "state2": {"residency": 4500, "latency": 4200},
    }
    STATES_PER_CPU: Dict[int, Dict[str, str]] = {}

    @classmethod
    def setUpClass(cls):
        super(CPUIdleTest, cls).setUpClass()
        cls.prompt = ArmAutoSolutionsConfig.baremetal_prompt
        cls.linux_console = cls.tc.target._get_terminal("default")
        cls.lt_utils = LinuxTermUtils(cls.tc, cls.linux_console, cls.prompt)

    def run_ok(self, cmd: str, timeout: int = DEFAULT_TIMEOUT,
               msg: str = None) -> str:
        """
        Run a command on the target and assert rc == 0.
        Returns stdout.strip().
        """
        status, out = self.lt_utils.run(cmd, timeout)
        self.assertEqual(
            status,
            0,
            msg or f"command failed rc={status}: {cmd}\n{out}"
        )
        return out.strip()

    def cat(self, path: str, timeout: int = DEFAULT_TIMEOUT,
            msg: str = None) -> str:
        """Read a file on the target and return its contents."""
        return self.run_ok(f"cat {path}", timeout, msg)

    def exists(self, path: str, timeout: int = DEFAULT_TIMEOUT) -> bool:
        """Check if a path exists on the target."""
        out = self.run_ok(f"test -e {path}; echo $?", timeout)
        return True if out == "0" else False

    def write(self, path: str, value: str | int,
              timeout: int = DEFAULT_TIMEOUT):
        """ Write a value to a file on the target."""
        status, _ = self.lt_utils.run(f"echo {value} > {path}", timeout)
        return status

    def _list_state_dirs(self, cpu: int) -> Dict[str, str]:
        """List C-state directories for a specific CPU."""
        base = p.join(self.CPU_SYSFS, f"cpu{cpu}", "cpuidle")
        # List C-state directories robustly
        cmd = (f"for d in {base}/state* ;"
               f" do [ -d \"$d\" ] && basename \"$d\"; done")
        out = self.run_ok(cmd)
        states: Dict[str, str] = {}
        for line in out.splitlines():
            name = line.strip()
            if name:
                states[name] = p.join(base, name)
        return states

    def _load_states_per_cpu(self) -> bool:
        """Load respective C-state directories for all online CPUs."""
        for cpu in range(0, int(self.td.get('PC_CPUS_COUNT'))):
            states = self._list_state_dirs(cpu)
            if len(states.keys()) < 3:
                self.skipTest(f"no C-states found for cpu{cpu}")
            self.STATES_PER_CPU[cpu] = states
        return True if self.STATES_PER_CPU else False

    def _check_default_status_for_state(self, cpu: int, state_id: str,
                                        states: Dict[str, str]):
        """Check if a specific C-state is enabled by default."""
        path = p.join(states[state_id], "default_status")
        # If not present, skip this check for this DUT
        self.assertTrue(
            self.exists(path),
            msg=(
                f"default_status not exposed on {state_id} "
                f"cpu{cpu}"
            )
        )
        val = self.cat(path)
        self.assertEqual(
            val,
            "enabled",
            msg=f"{state_id} not enabled by default on cpu{cpu}"
        )

    def _validate_required_files(self, disable_path: str, usage_path: str):
        """Ensure required files exist for respective C-state testing."""
        for path in (disable_path, usage_path):
            self.assertTrue(
                self.exists(path),
                msg=f"missing {path}"
            )

    def _verify_usage_increases(
            self,
            usage_path: str,
            cpu: int,
            state_id: str
            ):
        """Verify that usage increases over time when respective C-state is
        active."""
        usage0 = int(self.cat(usage_path))
        time.sleep(self.SLEEP_SHORT)
        usage1 = int(self.cat(usage_path))
        self.assertGreaterEqual(
            usage1,
            usage0,
            msg=(f"no usage increase before disable on "
                 f"cpu{cpu}:{state_id}")
        )

    def _disable_and_verify_state(self, disable_path: str, usage_path: str):
        """Disable respective C-state and verify usage doesn't increase."""
        orig_disable = self.cat(disable_path)
        self.addCleanup(self.write, disable_path, orig_disable)

        self.write(disable_path, 1)
        self.assertEqual(
            self.cat(disable_path),
            "1",
            msg=f"failed to disable C-state at path: {disable_path}"
        )

        # While respective C-state is disabled, usage should not increase
        u_a = int(self.cat(usage_path))
        time.sleep(self.SLEEP_SHORT)
        u_b = int(self.cat(usage_path))
        self.assertEqual(
            u_a,
            u_b,
            msg=(f"usage changed while C-state disabled"
                 f" for path: {usage_path}")
        )

    def _verify_usage_time_advancement(self, base: str, cpu: Dict[int, str]):
        """Verify that usage and time values advance over time."""
        usage1 = int(self.cat(p.join(base, "usage")))
        time1 = int(self.cat(p.join(base, "time")))
        time.sleep(self.SLEEP_LONG)
        usage2 = int(self.cat(p.join(base, "usage")))
        time2 = int(self.cat(p.join(base, "time")))

        self.assertGreaterEqual(
            usage2,
            usage1,
            msg=(f"state not entered after {self.SLEEP_LONG}s on "
                 f"cpu{cpu['id']}:{cpu['state_id']}")
        )
        self.assertGreaterEqual(
            time2,
            time1,
            msg=f"time did not advance on cpu {cpu['id']}:{cpu['state_id']}"
        )

    def _test_single_residency_latency(self, cpu: Dict[int, str],
                                       states: Dict[str, str], props: Dict):
        """Test residency and latency for a single C-state."""
        base = states[cpu['state_id']]
        self._verify_latency_residency_values(base, props, cpu)
        self._verify_usage_time_advancement(base, cpu)

    def _test_single_cstate_disable(self, cpu: int, state_id: str,
                                    states: Dict[str, str]):
        """Test disabling a single C-state for a specific CPU."""
        base = states[state_id]
        disable_path = p.join(base, "disable")
        usage_path = p.join(base, "usage")

        self._validate_required_files(disable_path, usage_path)
        self._verify_usage_increases(usage_path, cpu, state_id)
        self._disable_and_verify_state(disable_path, usage_path)

    def _verify_latency_residency_values(self, base: str, props: Dict,
                                         cpu: Dict[int, str]):
        """Verify latency and residency values match expected values."""
        latency = int(self.cat(p.join(base, "latency")))
        residency = int(self.cat(p.join(base, "residency")))

        self.assertEqual(
            latency,
            props["latency"],
            msg=f"latency mismatch on cpu{cpu['id']}:{cpu['state_id']}"
        )
        self.assertEqual(
            residency,
            props["residency"],
            msg=f"residency mismatch on cpu{cpu['id']}:{cpu['state_id']}"
        )

    def _available_governors(self) -> bool:
        """Get list of available cpuidle governors."""
        path = p.join(self.CPUIDLE_DIR, "available_governors")
        self.assertTrue(self.exists(path),
                        msg=f"{path} not present on target")
        return (self.cat(path).strip()).split()

    def _current_governor(self, ro: bool = True) -> str:
        """Get current cpuidle governor (read-only or read-write version)."""
        fname = "current_governor_ro" if ro else "current_governor"
        path = p.join(self.CPUIDLE_DIR, fname)
        self.assertTrue(self.exists(path),
                        msg=f"{path} not present on target")
        return self.cat(path)

    @OETestDepends([
        'test_00_linux_boot.LinuxBootTest.test_linux_boot'
    ])
    def test_ensure_cpuidle_or_skip(self):
        """Check if cpuidle sysfs is present; skip tests if not."""
        self.assertTrue(self._load_states_per_cpu(), msg="No C-states found")

    @OETestDepends([
        'test_71_power_cpuidle.CPUIdleTest.test_ensure_cpuidle_or_skip'
    ])
    def test_cpuidle_c_states(self):
        """
        Verify required cpuidle C-states exist and have expected names.
        """
        for cpu, states in self.STATES_PER_CPU.items():
            for state_id, expected_name in self.EXPECTED_STATE_NAMES.items():
                with self.subTest(cpu=cpu, state=state_id):
                    self.assertIn(
                        state_id,
                        states,
                        msg=f"{state_id} missing on cpu{cpu}"
                    )
                    name_path = p.join(states[state_id], "name")
                    actual = self.cat(name_path)
                    self.assertEqual(
                        actual,
                        expected_name,
                        msg=f"cpu{cpu}:{state_id} name mismatch",
                    )

    @OETestDepends([
        'test_71_power_cpuidle.CPUIdleTest.test_cpuidle_c_states'
    ])
    def test_cstates_default_status(self):
        """
        Verify all required cpuidle C-states are enabled
        by default (if kernel exposes default_status).
        """
        for cpu, states in self.STATES_PER_CPU.items():
            for state_id in self.EXPECTED_STATE_NAMES:
                if state_id not in states:
                    continue
                with self.subTest(cpu=cpu, state=state_id):
                    self._check_default_status_for_state(cpu, state_id, states)

    @OETestDepends([
        'test_71_power_cpuidle.CPUIdleTest.test_cstates_default_status'
    ])
    @skipIfDataVarWithTestName('FREQUENCY', 'adhoc', 'Skip in adhoc builds')
    def test_disable_cstate(self):
        """
        Disable each required C-state and verify usage
        does not increase while disabled; restore afterwards.
        """
        for cpu, states in self.STATES_PER_CPU.items():
            for state_id in self.EXPECTED_STATE_NAMES:
                if state_id not in states:
                    continue
                with self.subTest(cpu=cpu, state=state_id):
                    self._test_single_cstate_disable(cpu, state_id, states)

    @OETestDepends([
        'test_71_power_cpuidle.CPUIdleTest.test_disable_cstate'
    ])
    @skipIfDataVarWithTestName('FREQUENCY', 'adhoc', 'Skip in adhoc builds')
    def test_cstate_residency_latency(self):
        """
        Check latency/residency values and that time/usage
        advance when the C-state is entered.
        """
        for cpu, states in self.STATES_PER_CPU.items():
            for state_id, props in self.EXPECTED_PROPS.items():

                if state_id not in states:
                    continue
                with self.subTest(cpu=cpu, state=state_id):
                    self._test_single_residency_latency(
                         {'id': cpu, 'state_id': state_id}, states, props
                        )

    @OETestDepends(
        ['test_71_power_cpuidle.CPUIdleTest.test_cstate_residency_latency'])
    @skipIfDataVarWithTestName('FREQUENCY', 'adhoc', 'Skip in adhoc builds')
    def test_cpuidle_governors(self):
        """
        Basic validation of cpuidle governors:
          * current_governor_ro is one of the available governors
          * if current_governor (rw) exists, it matches the _ro value
        """
        avail = self._available_governors()
        curr_ro = self._current_governor(ro=True)
        self.assertIn(
            curr_ro,
            avail,
            msg=f"current_governor_ro={curr_ro} "
                f"not in available_governors={avail}"
        )

        # Check if read-write interface exists and matches read-only
        curr_rw = self._current_governor(ro=False)
        self.assertEqual(
            curr_rw,
            curr_ro,
            msg="current_governor and current_governor_ro differ"
        )

    @OETestDepends([
        'test_71_power_cpuidle.CPUIdleTest.test_cpuidle_governors'
    ])
    @skipIfDataVarWithTestName('FREQUENCY', 'adhoc', 'Skip in adhoc builds')
    def test_cpuidle_governor_switching(self):
        """
        If runtime switching is supported (current_governor exists),
        try each available governor (except the current) and verify
        it takes effect.
        """
        avail = self._available_governors()
        rw_path = p.join(self.CPUIDLE_DIR, "current_governor")
        self.assertTrue(self.exists(rw_path),
                        msg=("current_governor (rw) not present; "
                             "switching not supported"))

        curr = self.cat(rw_path)

        # Ensure we always restore the original governor
        self.addCleanup(self.write, rw_path, curr)

        # Nothing to do if only one governor exists
        targets = [g for g in avail if g != curr]
        if targets == []:
            self.skipTest(
                f"only one governor available ({curr}); cannot switch"
            )

        for g in targets:
            with self.subTest(switch_to=g):
                self.write(
                    rw_path,
                    g
                )
                # Verify both RO and RW views reflect the new value
                self.assertEqual(
                    self._current_governor(ro=True),
                    g,
                    msg=f"current_governor_ro did not update to {g}"
                )
                self.assertEqual(
                    self._current_governor(ro=False),
                    g,
                    msg=f"current_governor did not update to {g}"
                )

    @OETestDepends([
        'test_71_power_cpuidle.CPUIdleTest.test_cpuidle_governor_switching'
    ])
    @skipIfDataVarWithTestName('FREQUENCY', 'adhoc', 'Skip in adhoc builds')
    def test_invalid_cpuidle_governor(self):
        """
        Writing an invalid governor should fail
        and must not change the current governor.
        """
        rw_path = p.join(self.CPUIDLE_DIR, "current_governor")
        before = self._current_governor(ro=True)

        # Attempt an invalid write; expect non-zero rc
        status = self.write(rw_path, "invalid_governor_name")
        self.assertNotEqual(status, 0,
                            msg=("writing an invalid governor",
                                 "unexpectedly succeeded"))

        # Governor must remain unchanged
        after_ro = self._current_governor(ro=True)
        after_rw = self._current_governor(ro=False)
        self.assertEqual(before, after_ro,
                         "current_governor_ro changed after invalid write")
        self.assertEqual(before, after_rw,
                         "current_governor changed after invalid write")
