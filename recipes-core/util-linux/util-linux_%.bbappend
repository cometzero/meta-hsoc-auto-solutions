#
# SPDX-License-Identifier: MIT
#

# util-linux-native is a build tool dependency of systemd-systemctl-native.
# With a systemd-based distro, systemd.bbclass also appends
# systemd-systemctl-native to every systemd-inheriting recipe, including the
# native util-linux variant. Drop that native-only edge to avoid a dependency
# cycle; target util-linux still keeps its normal systemd integration.
python __anonymous() {
    if d.getVar("PN") != "util-linux-native":
        return

    for var in ("DEPENDS", "PACKAGE_WRITE_DEPS"):
        deps = (d.getVar(var) or "").split()
        d.setVar(var, " ".join(dep for dep in deps
                               if dep != "systemd-systemctl-native"))
}
