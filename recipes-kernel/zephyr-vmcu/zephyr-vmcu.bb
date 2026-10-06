# SPDX-License-Identifier: MIT
SUMMARY = "TC397 vMCU Zephyr firmware using the shared hsoc-stack source"
LICENSE = "GPL-2.0-or-later & Apache-2.0"
LIC_FILES_CHKSUM = " \
    file://LICENSES/GPL-2.0-or-later.txt;md5=b234ee4d69f5fce4486a80fdaf4a4263 \
    file://LICENSES/Apache-2.0.txt;md5=3b83ef96387f14655fc854ddc3c6bd57 \
"

inherit externalsrc python3native deploy
EXTERNALSRC = "${HSOC_APOLLO_ZEPHYRPROJECT_SRC}/zephyr_vmcu_src"
EXTERNALSRC_BUILD = "${WORKDIR}/build"
EXTERNALSRC_SYMLINKS = ""
COMPATIBLE_MACHINE = "apollo-qvp"
PACKAGE_ARCH = "${MACHINE_ARCH}"
INHIBIT_DEFAULT_DEPS = "1"
DEPENDS = "tricore-toolchain-native cmake-native ninja-native dtc-native gperf-native patch-native python3-pyelftools-native python3-pyyaml-native python3-pykwalify-native python3-packaging-native"

VMCU_ZEPHYR_BASE = "${WORKDIR}/zephyr"
VMCU_TOOLCHAIN = "${STAGING_LIBEXECDIR_NATIVE}/tricore-toolchain"
VMCU_ZEPHYR_PATCH = "${S}/compat/zephyr-4.1.patch"

# Shared Zephyr remains untouched: only the disposable copy gets TriCore glue.
python do_prepare_vmcu() {
    import os
    import shutil
    import subprocess

    destination = d.getVar("VMCU_ZEPHYR_BASE")
    if os.path.exists(destination):
        shutil.rmtree(destination)
    shutil.copytree(d.getVar("HSOC_APOLLO_ZEPHYR_SRC"), destination,
                    ignore=shutil.ignore_patterns(".git"))
    subprocess.run(["patch", "--batch", "--forward", "-p1", "-i",
                    d.getVar("VMCU_ZEPHYR_PATCH")], cwd=destination, check=True)
}
addtask prepare_vmcu after do_prepare_recipe_sysroot before do_configure

python () {
    checksums = " ${HSOC_APOLLO_ZEPHYR_SRC}:True ${EXTERNALSRC}:True"
    for task in ("do_prepare_vmcu", "do_configure", "do_compile"):
        d.appendVarFlag(task, "file-checksums", checksums)
}

do_configure[cleandirs] = "${B}"
do_configure() {
    unset CC CXX CPP AR AS LD CFLAGS CXXFLAGS CPPFLAGS LDFLAGS
    export ZEPHYR_BASE=${VMCU_ZEPHYR_BASE}
    export ZEPHYR_TOOLCHAIN_VARIANT=cross-compile
    export CROSS_COMPILE=${VMCU_TOOLCHAIN}/bin/tricore-elf-
    cmake -S ${S} -B ${B} -G Ninja \
        -DBOARD=qemu_tc3x \
        -DPython3_EXECUTABLE=${PYTHON} \
        -DZEPHYR_MODULES=${S} \
        -DDTC_OVERLAY_FILE=${S}/boards/qemu_tc3x.overlay \
        -DSYSROOT_DIR=${VMCU_TOOLCHAIN}/tricore-elf
}

do_compile() {
    cmake --build ${B} -- ${PARALLEL_MAKE}
}

do_install[noexec] = "1"
do_deploy() {
    install -d ${DEPLOYDIR}
    install -m 0644 ${B}/zephyr/zephyr.elf ${DEPLOYDIR}/zephyr-vmcu-tc397.elf
}
addtask deploy after do_compile before do_build
