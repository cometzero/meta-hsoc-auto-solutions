#
# SPDX-FileCopyrightText: <text>Copyright 2026 Arm Limited
# and/or its affiliates <open-source-office@arm.com></text>
#
# SPDX-License-Identifier: MIT
#
# noqa: SIZE_OK - kept aligned with the upstream end-to-end HIPC sequence.
#

from oeqa.runtime.case import OERuntimeTestCase
from oeqa.core.decorator.depends import OETestDepends
from oeqa.utils.linux_terminal_utils import LinuxTermUtils
from oeqa.utils.iperf_utils import IperfUtils
from oeqa.utils.mem_utils import MemUtils
from oeqa.utils.zephyr_shell import Shell
from oeqa.utils.arm_auto_solutions_config import ArmAutoSolutionsConfig


class HIPCMidBaremetalTests(OERuntimeTestCase):
    """
    HIPC Mid baremetal validation for FVP.
    Notes for this FVP topology:
    - Linux-visible endpoint is ethsi1 / brsi1
    - CL1 is validated through the Zephyr shell on safety_island_c1.
    - Shared memory layout is validated through DT reserved-memory nodes.
    """

    CL1_IP = "192.168.1.1"
    PC_IP = "192.168.1.2"
    UDP_TEST_DURATION = 3
    TCP_TEST_DURATION = 3
    STRESS_TEST_DURATION = 300

    @classmethod
    def setUpClass(cls):
        super(HIPCMidBaremetalTests, cls).setUpClass()
        cls.logger.debug(f"Target type: {type(cls.tc.target)}")
        cls.logger.debug(
            f"Available terminals: "
            f"{list(getattr(cls.tc.target, 'terminals', {}).keys())}"
        )

        cls.prompt = ArmAutoSolutionsConfig.baremetal_prompt
        cls.si_prompt = r"uart:~\$ "
        cls.linux_console_name = "default"
        cls.zephyr_console_name = "safety_island_c1"

        cls.logger.debug(
            "setUpClass: initialized static config "
            f"(linux={cls.linux_console_name},"
            "zephyr={cls.zephyr_console_name})"
        )

    def setUp(self):
        super().setUp()
        self.rse_console = "rse"
        self.scp_console = "scp"
        self.tfa_console = "tf-a"
        self.hostname = getattr(ArmAutoSolutionsConfig, "hostname", None)

        self.logger.debug("setUp: transitioning target to linux")
        self.tc.target.transition("linux")

        self.logger.debug("setUp: transitioned to linux, verifying state")

        try:
            buf = self.tc.target.before(self.linux_console_name)
            if hasattr(buf, "decode"):
                buf = buf.decode(errors="ignore")
            self.logger.debug(f"[LINUX BEFORE]\n{buf}")
        except Exception as e:
            self.logger.debug(f"[LINUX BEFORE ERROR] {e}")

        """ Reacquire fresh terminal objects every test """
        self.linux_console = self.tc.target._get_terminal(
            self.linux_console_name
        )
        self.zephyr_console = self.tc.target._get_terminal(
            self.zephyr_console_name
        )

        self.logger.debug(
            "setUp: reacquired consoles "
            f"(linux id={id(self.linux_console)}, "
            f"zephyr id={id(self.zephyr_console)})"
        )

        self.linux_utils = LinuxTermUtils(
            self.tc,
            self.linux_console,
            self.prompt,
        )
        self.logger.debug(
            f"setUp: created LinuxTermUtils id={id(self.linux_utils)}"
        )

        self.zephyr_shell = Shell(
            self.tc.target,
            self.zephyr_console_name,
            self.tc.logger,
            prompt="uart:~$",
        )
        self.logger.debug(
            f"setUp: created Zephyr Shell id={id(self.zephyr_shell)}"
        )

        self.iperf_utils = IperfUtils(
            self.tc.target,
            self.zephyr_shell,
            self.zephyr_console_name,
            self.si_prompt,
        )
        self.logger.debug(
            f"setUp: created IperfUtils id={id(self.iperf_utils)}"
        )

        self.mem_utils = MemUtils(
            self.linux_utils,
            self.tc.logger,
            self,
        )

        self.logger.debug("setUp: syncing Linux prompt")
        self.linux_utils.send_wait_prompt()

        self.logger.debug("setUp: Linux prompt synced")

        # Dump last console buffer
        try:
            buf = self.tc.target.before(self.linux_console_name)
            if hasattr(buf, "decode"):
                buf = buf.decode(errors="ignore")
            self.logger.debug(f"[LINUX PROMPT SYNC BUFFER]\n{buf}")
        except Exception as e:
            self.logger.debug(f"[PROMPT SYNC ERROR] {e}")

        self.logger.debug("setUp: syncing Zephyr prompt")
        self.zephyr_shell.wait_for_prompt(timeout=60)

        self.recover_linux_console()
        self.recover_zephyr_shell()

    def linux_ok(self, cmd, timeout=180, msg=None):
        self.logger.debug(f"[LINUX CMD START] {cmd}")
        status, output = self.linux_utils.run(cmd, timeout=timeout)
        self.logger.debug(f"[LINUX CMD END] rc={status}")
        self.logger.debug(f"[LINUX CMD OUTPUT]\n{output}")

        fail_msg = (
            f"{msg}\nCommand: {cmd}\nOutput:\n{output}"
            if msg
            else f"Linux command failed rc={status}: {cmd}\n{output}"
        )
        self.assertEqual(status, 0, fail_msg)
        return output

    def recover_linux_console(self):
        self.logger.debug("Recovering Linux console state")
        self.logger.debug(
            "[RECOVER] run_in_progress="
            f"{getattr(self.linux_utils, 'run_in_progress', None)}"
        )
        try:
            self.linux_utils.stop_cmd_wait_prompt()
            self.logger.debug("[RECOVER] stop_cmd_wait_prompt success")
        except Exception as e:
            self.logger.debug(f"stop_cmd_wait_prompt failed: {e}")

        self.linux_utils.run_in_progress = False

    def recover_zephyr_shell(self):
        try:
            self.target.sendline(self.zephyr_console_name, "")
            self.zephyr_shell.wait_for_prompt(timeout=60)
        except Exception:
            try:
                self.target.sendcontrol(self.zephyr_console_name, "c")
                self.zephyr_shell.wait_for_prompt(timeout=60)
            except Exception:
                pass

    """ 01. Sanity: CL1 + shared memory layout in DT """

    @OETestDepends([
        "test_00_linux_boot.LinuxBootTest.test_linux_boot",
        "test_00_si_cl1_boot.SiCl1BootTest.test_si_cl1_boot",
    ])
    def test_01_mid_sanity_dt_and_shared_memory(self):
        dt_out = self.linux_ok(
            r"grep -Rnia 'si-cl1' /proc/device-tree || true",
            timeout=180,
        )
        self.assertRegex(
            dt_out,
            r"si-cl1",
            msg="CL1 DT node not found; system may look like Min config.",
        )

        si_path = dt_out.splitlines()[0].split(":")[0]
        si_dir = si_path.rsplit("/", 1)[0]

        self.logger.debug(f"si-cl1 path: {si_path}")
        self.logger.debug(f"si-cl1 directory: {si_dir}")

        si_cl1_memregion = self.linux_ok(
            f"hexdump -Cv {si_dir}/memory-region",
            timeout=180,
        )
        self.logger.debug(
            f" si-cl1 memory-region hexdump:\n{si_cl1_memregion}"
        )

        reserved_nodes = self.mem_utils.get_reserved_memory_nodes()

        matched_nodes = self.mem_utils.match_reserved_nodes(reserved_nodes)

        matched_phandles, total_size = self.mem_utils.process_matched_nodes(
            matched_nodes
        )

        memregion_hex = self.mem_utils.flatten_memory_region(si_cl1_memregion)

        self.mem_utils.validate_phandles(matched_phandles, memregion_hex)

        self.logger.debug(
            f"total reserved SRAM for CL1 IPC: "
            f"{total_size} bytes (0x{total_size:x})"
        )

        self.assertEqual(
            total_size,
            0x80000,
            msg=(
                f"Unexpected total SRAM reserved for CL1 IPC.\n"
                f"Expected: 524288 bytes (512 KB)\n"
                f"Found: {total_size} bytes"
            ),
        )

    """ 02. Enablement: Linux stack + FVP-visible interfaces """

    @OETestDepends([
        "test_31_si_cl1_hipc."
        "HIPCMidBaremetalTests.test_01_mid_sanity_dt_and_shared_memory"
    ])
    def test_02_enablement_linux_stack(self):
        """
        Validate Linux-side HIPC enablement using stable runtime state.
        Avoid relying on boot-time dmesg logs which may be overwritten.
        """

        dmesg_out = self.linux_ok(
            r"dmesg | grep -Ei 'arm-mhuv3-mailbox|remoteproc|"
            r"rproc-virtio|virtio_rpmsg_bus|ethsi1' || true",
            timeout=180,
        )

        if dmesg_out.strip():
            """If logs exist, validate them"""
            for pattern in [
                r"arm-mhuv3-mailbox",
                r"remoteproc .*si-cl1",
                r"rproc-virtio .*vdev0buffer",
                r"virtio_rpmsg_bus .*rpmsg host is online",
                r"virtio_rpmsg_bus .*ethsi1",
            ]:
                self.assertRegex(
                    dmesg_out,
                    pattern,
                    msg=f"Missing expected enablement log: {pattern}",
                )

        """Validate module presence"""
        modules_out = self.linux_ok(
            r"find /lib/modules/$(uname -r) -type f | "
            r"grep -E 'arm_si_rproc|virtio_rpmsg_bus|rpmsg_core|"
            r"rpmsg_ns|rpmsg_net' || true",
            timeout=180,
        )

        for pattern in [
            r"arm_si_rproc\.ko",
            r"virtio_rpmsg_bus\.ko",
            r"rpmsg_core\.ko",
            r"rpmsg_ns\.ko",
            r"rpmsg_net\.ko",
        ]:
            self.assertRegex(
                modules_out,
                pattern,
                msg=f"Expected module not present in image: {pattern}",
            )

        """Validate runtime state"""
        rproc_out = self.linux_ok(
            r"for d in /sys/class/remoteproc/remoteproc*; do "
            r"[ -f $d/name ] && echo \"$(cat $d/name) $(cat $d/state)\"; done",
            timeout=180,
        )

        self.assertRegex(
            rproc_out,
            r"si-cl1",
            msg=f"si-cl1 remoteproc not found:\n{rproc_out}",
        )

        self.assertRegex(
            rproc_out,
            r"(running|attached)",
            msg=f"remoteproc not active:\n{rproc_out}",
        )

        ethsi_out = self.linux_ok("ip link show ethsi1", timeout=180)
        self.assertRegex(
            ethsi_out,
            r"ethsi1:.*UP",
            msg="ethsi1 interface not UP",
        )

        brsi_out = self.linux_ok("ip addr show brsi1", timeout=180)
        self.assertRegex(
            brsi_out,
            r"brsi1:.*UP",
            msg="brsi1 interface not UP",
        )
        self.assertRegex(
            brsi_out,
            r"inet 192\.168\.1\.2/24",
            msg="brsi1 does not have expected IP 192.168.1.2/24",
        )

    """ 03. Memory: 512 KB reserved-memory layout """

    @OETestDepends([
        "test_31_si_cl1_hipc."
        "HIPCMidBaremetalTests.test_02_enablement_linux_stack"
    ])
    def test_03_memory_layout(self):
        reserved = self.linux_ok(
            r"ls /proc/device-tree/reserved-memory",
            timeout=180,
        )
        self.logger.debug(f"reserved-memory entries:\n{reserved}")

        reserved_nodes = [token for token in reserved.split() if "@" in token]

        required_roles = [
            "rsctbl",
            "vdev0vring0",
            "vdev0vring1",
            "vdev0buffer",
        ]

        matched_nodes = {}
        for role in required_roles:
            match = next(
                (node for node in reserved_nodes if role in node), None
            )
            self.assertIsNotNone(
                match,
                msg=(
                    f"Reserved-memory node for role '{role}' not found.\n"
                    f"Available nodes:\n{reserved}"
                ),
            )
            matched_nodes[role] = match
            self.logger.debug(f"matched reserved node for {role}: {match}")

        regions = []

        for role, node in matched_nodes.items():
            reg_out = self.linux_ok(
                'python3 -c "import struct; '
                f"b=open('/proc/device-tree/reserved-memory/"
                f"{node}/reg','rb').read(); "
                "c=struct.unpack('>%dI' % (len(b)//4), b); "
                "base=(c[0]<<32)|c[1]; size=(c[2]<<32)|c[3]; "
                'print(base, size)"',
                timeout=180,
            ).strip()

            parts = reg_out.split()
            self.assertEqual(
                len(parts),
                2,
                msg=f"Could not parse base/size for node {node}: {reg_out}",
            )

            base = int(parts[0])
            size = int(parts[1])

            self.logger.debug(
                f"{role}: node={node}, base=0x{base:x}, "
                f"size={size} bytes (0x{size:x})"
            )

            self.assertEqual(
                size,
                0x20000,
                msg=(
                    f"Unexpected size for {node}.\n"
                    f"Expected: 0x20000 (131072 bytes)\n"
                    f"Found: 0x{size:x} ({size} bytes)"
                ),
            )

            regions.append((base, size, node, role))

        regions.sort(key=lambda x: x[0])

        total_size = sum(size for base, size, node, role in regions)
        self.logger.debug(
            f"total reserved SRAM for CL1 IPC: {total_size} bytes "
            f"(0x{total_size:x})"
        )

        self.assertEqual(
            total_size,
            0x80000,
            msg=(
                f"Unexpected total SRAM reserved for CL1 IPC.\n"
                f"Expected: 0x80000 (524288 bytes, 512 KB)\n"
                f"Found: 0x{total_size:x} ({total_size} bytes)"
            ),
        )

        for i in range(len(regions) - 1):
            curr_base, curr_size, curr_node, curr_role = regions[i]
            next_base, next_size, next_node, next_role = regions[i + 1]

            curr_end = curr_base + curr_size

            self.logger.debug(
                f"checking layout: {curr_node} ends at 0x{curr_end:x}, "
                f"next node {next_node} starts at 0x{next_base:x}"
            )

            self.assertEqual(
                curr_end,
                next_base,
                msg=(
                    "Memory regions are not contiguous or overlap.\n"
                    f"{curr_node}: base=0x{curr_base:x}, "
                    f"size=0x{curr_size:x}, end=0x{curr_end:x}\n"
                    f"{next_node}: base=0x{next_base:x}, "
                    f"size=0x{next_size:x}"
                ),
            )

        rproc_out = self.linux_ok(
            r"for d in /sys/class/remoteproc/remoteproc*; do "
            r"[ -f $d/name ] && echo \"$(cat $d/name) $(cat $d/state)\"; done",
            timeout=180,
        )
        self.logger.debug(f"remoteproc runtime state:\n{rproc_out}")

        self.assertRegex(
            rproc_out,
            r"si-cl1",
            msg=f"si-cl1 remoteproc not found:\n{rproc_out}",
        )
        self.assertRegex(
            rproc_out,
            r"(running|attached)",
            msg=f"si-cl1 remoteproc not active:\n{rproc_out}",
        )

        ethsi_out = self.linux_ok("ip link show ethsi1", timeout=180)
        self.logger.debug(f"ethsi1 state:\n{ethsi_out}")

        self.assertRegex(
            ethsi_out,
            r"ethsi1:.*UP",
            msg=(
                "ethsi1 interface not UP; " "RPMsg/OpenAMP may not be active"
            ),
        )

    """04. Functional: ICMP both ways"""

    @OETestDepends([
        "test_31_si_cl1_hipc.HIPCMidBaremetalTests.test_03_memory_layout"
    ])
    def test_04_icmp_bidirectional(self):
        self.logger.debug("Starting Zephyr -> Linux ping")

        self.assertTrue(
            self.zephyr_shell.wait_for_prompt(timeout=180),
            "Failed to sync Zephyr prompt",
        )
        cmd = f"net ping {self.PC_IP} -c 10"
        self.logger.debug(f"Zephyr command: {cmd}")
        self.target.sendline(self.zephyr_console_name, cmd)

        self.target.expect(
            self.zephyr_console_name,
            r"icmp_seq=10",
            timeout=600,
        )
        self.target.expect(
            self.zephyr_console_name,
            self.si_prompt,
            timeout=180,
        )

        zephyr_out = self.target.before(self.zephyr_console_name)
        if hasattr(zephyr_out, "decode"):
            zephyr_out = zephyr_out.decode(errors="ignore")

        self.logger.debug(f"Zephyr ping output:\n{zephyr_out}")
        self.logger.debug("Starting Linux -> Zephyr ping")

        linux_cmd = f"ping {self.CL1_IP} -c 10"
        self.logger.debug(f"Linux command: {linux_cmd}")

        linux_ping = self.linux_ok(
            linux_cmd,
            timeout=400,
        )

        self.logger.debug(f"Linux ping output:\n{linux_ping}")

        self.assertRegex(
            linux_ping,
            r"10 packets transmitted,\s+10 packets received,\s+0% packet loss",
            msg=f"Linux->Zephyr ping failed:\n{linux_ping}",
        )

    """ 05. Functional: UDP PC -> CL1 """

    @OETestDepends([
        "test_31_si_cl1_hipc."
        "HIPCMidBaremetalTests.test_04_icmp_bidirectional"
    ])
    def test_05_udp_pc_to_cl1(self):
        self.logger.debug("Starting UDP PC -> CL1 test")
        self.logger.debug("[DEBUG] Checking Linux network state before test")
        self.linux_ok("ip addr", timeout=60)
        self.linux_ok("ip route", timeout=60)
        self.linux_ok("ps aux | grep iperf || true", timeout=60)

        self.iperf_utils.zephyr_cmd_expect(
            f"zperf udp download 5001 {self.CL1_IP}",
            r"UDP server started on port 5001",
            timeout=120,
        )

        self.logger.debug("Zephyr UDP server started")

        try:
            cmd = (
                f"iperf -u -c {self.CL1_IP} -t {self.UDP_TEST_DURATION} "
                f"-b 100K -l 1438"
            )
            self.logger.debug(f"Linux command: {cmd}")

            out = self.linux_ok(
                cmd,
                timeout=600,
            )

            self.logger.debug(f"Linux iperf output:\n{out}")

            self.assertRegex(
                out, r"Server Report:", msg=f"iperf UDP failed:\n{out}"
            )
            self.assertRegex(
                out, r"0/\d+\s+\(0%\)", msg=f"UDP loss detected:\n{out}"
            )
            self.logger.debug("Waiting for Zephyr UDP session stats")
            self.iperf_utils.expect_udp_sessions_ok(1, timeout=400)
            zephyr_out = self.target.before(self.zephyr_console_name)
            if hasattr(zephyr_out, "decode"):
                zephyr_out = zephyr_out.decode(errors="ignore")
            self.logger.debug(f"Zephyr UDP session output:\n{zephyr_out}")

        finally:
            self.logger.debug("Stopping Zephyr UDP server")
            self.iperf_utils.zephyr_cmd_expect(
                "zperf udp download stop",
                r"UDP server stopped",
                timeout=180,
                wait_prompt=True,
            )
            self.logger.debug("Zephyr UDP server stopped")

    """ 06. Functional: TCP PC -> CL1 """

    @OETestDepends([
        "test_31_si_cl1_hipc.HIPCMidBaremetalTests.test_05_udp_pc_to_cl1"
    ])
    def test_06_tcp_pc_to_cl1(self):
        self.logger.debug("Starting TCP PC -> CL1 test")

        self.recover_linux_console()
        self.recover_zephyr_shell()

        self.logger.debug("[DEBUG] Checking Linux network state before test")
        self.linux_ok("ip addr", timeout=60)
        self.linux_ok("ip route", timeout=60)
        self.linux_ok("ps aux | grep iperf || true", timeout=60)

        self.iperf_utils.zephyr_cmd_expect(
            f"zperf tcp download 5001 {self.CL1_IP}",
            r"TCP server started on port 5001",
            timeout=120,
        )
        self.logger.debug("Zephyr TCP server started")

        try:
            cmd = f"timeout -s INT 20 iperf -c {self.CL1_IP} -n 8M"
            self.logger.debug(f"Linux command: {cmd}")
            self.linux_console.sendline(cmd)
            self.linux_console.expect(r"[KMG]bits/sec", timeout=180)
            first_chunk = self.linux_console.before + self.linux_console.after

            self.linux_console.expect(self.prompt, timeout=120)
            second_chunk = self.linux_console.before

            out = first_chunk + second_chunk
            if hasattr(out, "decode"):
                out = out.decode(errors="ignore")

            self.logger.debug(f"Linux iperf output:\n{out}")

            self.assertRegex(
                out, r"Bandwidth", msg=f"iperf TCP failed:\n{out}"
            )
            self.assertRegex(
                out, r"[KMG]bits/sec", msg=f"iperf TCP failed:\n{out}"
            )

            self.logger.debug("Waiting for Zephyr TCP session completion")
            self.iperf_utils.expect_tcp_sessions_ok(1, timeout=400)

            zephyr_out = self.tc.target.before(self.zephyr_console_name)
            if hasattr(zephyr_out, "decode"):
                zephyr_out = zephyr_out.decode(errors="ignore")

            self.logger.debug(f"Zephyr TCP session output:\n{zephyr_out}")

        finally:
            self.logger.debug("Stopping Zephyr TCP server")
            self.iperf_utils.zephyr_cmd_expect(
                "zperf tcp download stop",
                r"TCP server stopped",
                timeout=180,
                wait_prompt=True,
            )
            self.logger.debug("Zephyr TCP server stopped")
            self.recover_linux_console()
            self.recover_zephyr_shell()

    """ 07. Functional: UDP CL1 -> PC """

    @OETestDepends([
        "test_31_si_cl1_hipc.HIPCMidBaremetalTests.test_06_tcp_pc_to_cl1"
    ])
    def test_07_udp_cl1_to_pc(self):
        self.logger.debug("Starting UDP CL1 -> PC test")
        self.recover_linux_console()
        self.recover_zephyr_shell()

        self.logger.debug("[DEBUG] Checking Linux network state before test")
        self.linux_ok("ip addr", timeout=60)
        self.linux_ok("ip route", timeout=60)
        self.linux_ok("ps aux | grep iperf || true", timeout=60)

        bg = self.linux_utils.background_cmd_ctx("iperf -u -s -P 1", 180)
        self.logger.debug(
            "BG object created: "
            f"id={id(bg)}, "
            f"bin_name={getattr(bg, 'bin_name', None)}, "
            f"cmd_log={getattr(bg, 'cmd_log', None)}, "
            f"cmd={getattr(bg, 'cmd', None)}, "
            f"timeout={getattr(bg, 'timeout', None)}, "
            f"console_id={id(getattr(bg, 'console', None))}, "
            f"lt_utils_id={id(getattr(bg, 'lt_utils', None))}"
        )
        self.logger.debug("Linux UDP server (iperf) starting in background")

        try:
            with bg:
                self.logger.debug(
                    "Inside bg context: "
                    f"cmd_output={repr(getattr(bg, 'cmd_output', None))}"
                )
                self.assertTrue(
                    self.zephyr_shell.wait_for_prompt(timeout=180),
                    "Failed to sync Zephyr prompt",
                )

                cmd = (
                    f"zperf udp upload {self.PC_IP} 5001 "
                    f"{self.UDP_TEST_DURATION} 1k 100K"
                )
                self.logger.debug(f"Zephyr command: {cmd}")

                self.target.sendline(
                    self.zephyr_console_name,
                    cmd,
                )

                self.target.expect(
                    self.zephyr_console_name,
                    r"Upload completed!",
                    timeout=600,
                )
                self.target.expect(
                    self.zephyr_console_name,
                    r"Num packets:\s*\d+",
                    timeout=180,
                )
                self.target.expect(
                    self.zephyr_console_name,
                    r"Num packets out order:\s*0",
                    timeout=180,
                )
                self.target.expect(
                    self.zephyr_console_name,
                    r"Num packets lost:\s*0",
                    timeout=180,
                )
                self.target.expect(
                    self.zephyr_console_name,
                    self.si_prompt,
                    timeout=180,
                )

                zephyr_out = self.target.before(self.zephyr_console_name)
                if hasattr(zephyr_out, "decode"):
                    zephyr_out = zephyr_out.decode(errors="ignore")

                self.logger.debug(f"Zephyr UDP upload output:\n{zephyr_out}")
        finally:
            self.recover_linux_console()
            self.recover_zephyr_shell()

        self.logger.debug("Linux UDP server output (iperf):")
        self.logger.debug(f"\n{bg.cmd_output}")

        self.assertRegex(
            bg.cmd_output,
            r"0/\d+\s+\(0%\)",
            msg=f"Linux UDP server saw packet loss:\n{bg.cmd_output}",
        )

        self.logger.debug("UDP CL1 -> PC test completed successfully")

    """ 08. Functional: TCP CL1 -> PC """

    @OETestDepends([
        "test_31_si_cl1_hipc.HIPCMidBaremetalTests.test_07_udp_cl1_to_pc"
    ])
    def test_08_tcp_cl1_to_pc(self):
        self.logger.debug("Starting TCP CL1 -> PC test")

        self.recover_linux_console()
        self.recover_zephyr_shell()

        self.logger.debug("[DEBUG] Checking Linux network state before test")
        self.linux_ok("ip addr", timeout=60)
        self.linux_ok("ip route", timeout=60)
        self.linux_ok("ps aux | grep iperf || true", timeout=60)

        self.logger.debug("Starting Linux TCP server")
        self.linux_ok(
            "sh -c 'rm -f /tmp/iperf_tcp_server.log "
            "/tmp/iperf_tcp_server.pid; "
            "iperf -s -P 1 >/tmp/iperf_tcp_server.log 2>&1 & "
            "echo $! >/tmp/iperf_tcp_server.pid'",
            timeout=30,
        )

        self.logger.debug(
            "Waiting for Linux TCP server to listen on port 5001"
        )
        self.linux_ok(
            "sh -c 'for i in $(seq 1 10); do "
            'grep -q "Server listening on TCP port 5001" '
            "/tmp/iperf_tcp_server.log && exit 0; "
            "sleep 1; "
            "done; "
            "exit 1'",
            timeout=20,
        )

        try:
            self.assertTrue(
                self.zephyr_shell.wait_for_prompt(timeout=180),
                "Failed to sync Zephyr prompt",
            )

            cmd = f"zperf tcp upload {self.PC_IP} 5001 1 1k"
            self.logger.debug(f"Zephyr command: {cmd}")

            self.target.sendline(
                self.zephyr_console_name,
                cmd,
            )

            self.target.expect(
                self.zephyr_console_name,
                r"Num packets:\s*\d+",
                timeout=600,
            )
            self.target.expect(
                self.zephyr_console_name,
                r"Num errors:\s*0",
                timeout=180,
            )
            self.target.expect(
                self.zephyr_console_name,
                self.si_prompt,
                timeout=180,
            )

            zephyr_out = self.tc.target.before(self.zephyr_console_name)
            if hasattr(zephyr_out, "decode"):
                zephyr_out = zephyr_out.decode(errors="ignore")

            self.logger.debug(f"Zephyr TCP upload output:\n{zephyr_out}")

        finally:
            self.logger.debug("Stopping Linux TCP server")
            self.linux_ok(
                "sh -c 'test -f /tmp/iperf_tcp_server.pid && "
                "kill -INT $(cat /tmp/iperf_tcp_server.pid) || true'",
                timeout=30,
            )
            self.recover_linux_console()
            self.recover_zephyr_shell()

        self.logger.debug("Linux TCP server output (iperf):")
        server_out = self.linux_ok(
            "cat /tmp/iperf_tcp_server.log || true",
            timeout=30,
        )
        self.logger.debug(f"\n{server_out}")

        self.assertRegex(
            server_out,
            r"[KMG]bits/sec",
            msg=(
                "Linux TCP server did not receive valid transfer output:\n"
                f"{server_out}"
            ),
        )

        self.logger.debug("TCP CL1 -> PC test completed successfully")

    """ 09. Boundary: payload sizes + oversized handled safely """

    @OETestDepends([
        "test_31_si_cl1_hipc.HIPCMidBaremetalTests.test_08_tcp_cl1_to_pc"
    ])
    def test_09_boundary_payload_sizes(self):
        self.logger.debug("Starting UDP payload boundary test (PC -> CL1)")

        self.recover_linux_console()
        self.recover_zephyr_shell()

        self.logger.debug("[DEBUG] Checking Linux network state before test")
        self.linux_ok("ip addr", timeout=60)
        self.linux_ok("ip route", timeout=60)
        self.linux_ok("ps aux | grep iperf || true", timeout=60)

        valid_sizes = [1024, 1200, 1438, 1472]

        self.iperf_utils.zephyr_cmd_expect(
            f"zperf udp download 5001 {self.CL1_IP}",
            r"UDP server started on port 5001",
            timeout=120,
        )

        self.logger.debug("Zephyr UDP server started")

        try:
            for size in valid_sizes:
                self.logger.debug(f"Testing payload size: {size} bytes")

                cmd = (
                    f"iperf -u -c {self.CL1_IP} -t {self.UDP_TEST_DURATION} "
                    f"-b 100K -l {size}"
                )
                self.logger.debug(f"Linux command: {cmd}")

                out = self.linux_ok(
                    cmd,
                    timeout=300,
                )

                self.logger.debug(f"Linux iperf output (size={size}):\n{out}")

                self.assertRegex(
                    out,
                    r"0/\d+\s+\(0%\)",
                    msg=f"Packet loss for payload {size}:\n{out}",
                )

                self.logger.debug(
                    f"Waiting for Zephyr UDP session stats (size={size})"
                )

                self.iperf_utils.expect_udp_sessions_ok(1, timeout=300)

                zephyr_out = self.target.before(self.zephyr_console_name)
                if hasattr(zephyr_out, "decode"):
                    zephyr_out = zephyr_out.decode(errors="ignore")

                self.logger.debug(
                    f"Zephyr UDP session output (size={size}):\n{zephyr_out}"
                )
                self.recover_linux_console()
                self.recover_zephyr_shell()

            oversized_size = 2500
            self.logger.debug(
                f"Testing oversized payload: {oversized_size} bytes"
            )

            oversized_cmd = (
                f"iperf -u -c {self.CL1_IP} -t {self.UDP_TEST_DURATION} "
                f"-b 100K -l {oversized_size} || true"
            )
            self.logger.debug(f"Linux command: {oversized_cmd}")

            oversized_out = self.linux_ok(
                oversized_cmd,
                timeout=300,
            )

            self.logger.debug(f"Oversized payload output:\n{oversized_out}")

            self.assertTrue(
                oversized_out is not None,
                "Oversized payload run produced no output",
            )

        finally:
            self.logger.debug("Stopping Zephyr UDP server")
            self.iperf_utils.zephyr_cmd_expect(
                "zperf udp download stop",
                r"UDP server stopped",
                timeout=180,
                wait_prompt=True,
            )
            self.logger.debug("Zephyr UDP server stopped")
            self.recover_linux_console()
            self.recover_zephyr_shell()

        self.logger.debug("Checking for kernel crashes after payload tests")

        self.mem_utils.assert_no_kernel_crash()

        self.logger.debug("UDP payload boundary test completed successfully")

    """ 10. Boundary: multistream P=2,4 """

    @OETestDepends([
        "test_31_si_cl1_hipc."
        "HIPCMidBaremetalTests.test_09_boundary_payload_sizes"
    ])
    def test_10_boundary_multistream(self):
        self.logger.debug("Starting UDP multistream PC -> CL1 test")

        self.recover_linux_console()
        self.recover_zephyr_shell()

        self.logger.debug("[DEBUG] Checking Linux network state before test")
        self.linux_ok("ip addr", timeout=60)
        self.linux_ok("ip route", timeout=60)
        self.linux_ok("ps aux | grep iperf || true", timeout=60)
        self.iperf_utils.zephyr_cmd_expect(
            f"zperf udp download 5001 {self.CL1_IP}",
            r"UDP server started on port 5001",
            timeout=120,
        )

        self.logger.debug("Zephyr UDP server started")

        try:
            for p in [2, 4]:
                self.logger.debug(f"Running multistream test with P={p}")

                cmd = (
                    f"iperf -u -c {self.CL1_IP} -t {self.UDP_TEST_DURATION} "
                    f"-b 100K -l 1438 -P {p}"
                )
                self.logger.debug(f"Linux command: {cmd}")

                out = self.linux_ok(
                    cmd,
                    timeout=300,
                )

                self.logger.debug(f"Linux iperf output (P={p}):\n{out}")

                self.assertRegex(
                    out,
                    rf"\[SUM-{p}\] Sent \d+ datagrams",
                    msg=f"multistream P={p} did not complete:\n{out}",
                )
                self.assertRegex(
                    out,
                    r"0/\d+\s+\(0%\)",
                    msg=f"Loss seen in multistream P={p}:\n{out}",
                )

                self.logger.debug(
                    f"Waiting for Zephyr UDP session stats for P={p}"
                )

                self.iperf_utils.expect_udp_sessions_ok(p, timeout=300)

                zephyr_out = self.target.before(self.zephyr_console_name)
                if hasattr(zephyr_out, "decode"):
                    zephyr_out = zephyr_out.decode(errors="ignore")

                self.logger.debug(
                    f"Zephyr UDP session output (P={p}):\n{zephyr_out}"
                )

        finally:
            self.logger.debug("Stopping Zephyr UDP server")
            self.iperf_utils.zephyr_cmd_expect(
                "zperf udp download stop",
                r"UDP server stopped",
                timeout=180,
                wait_prompt=True,
            )
            self.logger.debug("Zephyr UDP server stopped")
            self.recover_linux_console()
            self.recover_zephyr_shell()
