# SPDX-License-Identifier: MIT

import argparse
from pathlib import Path
import re
import sys

import pexpect

from oeqa.core.decorator.depends import OETestDepends
from oeqa.runtime.case import OERuntimeTestCase


DEFAULT_SLOT = "A"
LINUX_BOOT_MARKER = "Booting Linux on physical CPU"


def expected_boot_markers(slot=DEFAULT_SLOT):
    slot = slot.upper()
    slot_filename = slot.lower()
    return (
        (
            "U-Boot slot selection",
            f"auto-ad-nexios: selected slot {slot}",
        ),
        (
            "selected UKI filename",
            f"auto-ad-nexios: selected UKI "
            f"EFI/Linux/auto-ad-nexios-{slot_filename}.efi",
        ),
        ("Linux boot", LINUX_BOOT_MARKER),
    )


def missing_boot_markers(log_text, slot=DEFAULT_SLOT):
    return [
        (label, marker)
        for label, marker in expected_boot_markers(slot)
        if marker not in log_text
    ]


def assert_boot_log(log_text, slot=DEFAULT_SLOT):
    missing = missing_boot_markers(log_text, slot)
    if missing:
        details = ", ".join(f"{label}: {marker}" for label, marker in missing)
        raise AssertionError(f"missing auto-ad-nexios boot markers: {details}")


class AutoAdNexiosUkiBootTest(OERuntimeTestCase):
    def setUp(self):
        super().setUp()
        self.console = self.target.DEFAULT_CONSOLE

    def _console_log_candidates(self):
        if getattr(self.target, "bootlog", None):
            yield Path(self.target.bootlog)

        test_log_dir = self.td.get("TEST_LOG_DIR")
        if test_log_dir:
            log_dir = Path(test_log_dir)
            yield log_dir / "default_log"
            yield from sorted(
                log_dir.glob("default_log.*"),
                key=lambda path: path.stat().st_mtime if path.exists() else 0,
                reverse=True,
            )

    def _read_console_log(self):
        seen = set()
        for path in self._console_log_candidates():
            if path in seen:
                continue
            seen.add(path)
            if not path.exists():
                continue
            return path.read_text(encoding="utf-8", errors="replace")
        return ""

    def _expect_boot_marker(self, label, marker, timeout=120):
        if marker in self._read_console_log():
            return

        try:
            result = self.target.expect(
                self.console, re.escape(marker), timeout=timeout
            )
        except pexpect.TIMEOUT:
            if marker in self._read_console_log():
                return
            raise

        self.assertEqual(result, 0, f"Missing {label}: {marker}")

    def _run_ok(self, command, timeout=120):
        status, output = self.target.run(command, timeout=timeout)
        self.assertEqual(status, 0, f"{command} failed:\n{output}")
        return output

    def test_01_uboot_uki_boot_markers(self):
        for label, marker in expected_boot_markers():
            self._expect_boot_marker(label, marker)

    @OETestDepends([
        "ssh.SSHTest.test_ssh",
        "test_01_auto_ad_nexios_uki_boot."
        "AutoAdNexiosUkiBootTest.test_01_uboot_uki_boot_markers",
    ])
    def test_02_dm_verity_root(self):
        cmdline = self._run_ok("cat /proc/cmdline")
        self.assertIn("root=PARTLABEL=rootro_a", cmdline)

        root_source = self._run_ok("findmnt -nro SOURCE /")
        root_sources = root_source.splitlines()
        self.assertTrue(
            any(
                source == "/dev/mapper/rootfs" or source.startswith("/dev/dm-")
                for source in root_sources
            ),
            f"unexpected root source: {root_source}",
        )

        root_options = self._run_ok("findmnt -nro OPTIONS /")
        self.assertIn("ro", root_options.strip().split(","))

        self._run_ok(
            "for name in /sys/block/dm-*/dm/name; do "
            "test -e \"$name\" && grep -qx rootfs \"$name\" && exit 0; "
            "done; exit 1"
        )

    @OETestDepends([
        "test_01_auto_ad_nexios_uki_boot."
        "AutoAdNexiosUkiBootTest.test_02_dm_verity_root",
    ])
    def test_03_writable_mounts(self):
        for path, fstype in (
            ("/rootrw", "ext4"),
            ("/data", "ext4"),
            ("/run", "tmpfs"),
        ):
            mount = self._run_ok(f"findmnt -nro TARGET,FSTYPE --target {path}")
            self.assertIn(
                f"{path} {fstype}",
                mount.splitlines(),
                f"unexpected mount for {path}: {mount}",
            )

        for path in (
            "/etc/auto-ad-nexios-oeqa-write-test",
            "/run/auto-ad-nexios-oeqa-write-test",
            "/var/run/auto-ad-nexios-oeqa-write-test",
            "/data/auto-ad-nexios-oeqa-write-test",
        ):
            self._run_ok(
                f"printf oeqa > {path} && "
                f"test -s {path} && "
                f"rm -f {path}"
            )


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Inspect an auto-ad-nexios boot log for required markers."
    )
    parser.add_argument("log", help="Boot log to inspect")
    parser.add_argument("--slot", default=DEFAULT_SLOT, choices=("A", "B"))
    args = parser.parse_args(argv)

    with open(args.log, "r", encoding="utf-8") as log_file:
        log_text = log_file.read()

    try:
        assert_boot_log(log_text, args.slot)
    except AssertionError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1

    print("PASS: auto-ad-nexios boot markers present")
    return 0


if __name__ == "__main__":
    sys.exit(main())
