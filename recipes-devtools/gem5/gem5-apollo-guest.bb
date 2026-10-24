# SPDX-License-Identifier: MIT
SUMMARY = "Apollo gem5 AP boot firmware and Linux benchmarks"
LICENSE = "BSD-3-Clause"
LIC_FILES_CHKSUM = " \
    file://system/arm/bootloader/zena_css/boot.S;beginline=2;endline=2;md5=de1725a63086dd4e294708e0418c3a37 \
    file://${GEM5_APOLLO_BENCH_SOURCE};beginline=1;endline=1;md5=de1725a63086dd4e294708e0418c3a37 \
    file://${GEM5_APOLLO_CONTROL_SOURCE};beginline=1;endline=1;md5=de1725a63086dd4e294708e0418c3a37 \
    file://workloads/zena_cmn/memory_bench.c;beginline=1;endline=1;md5=de1725a63086dd4e294708e0418c3a37 \
    file://util/m5/src/abi/arm64/m5op.S;md5=303b810284fa71397f1ce5dc741bb174 \
"

inherit externalsrc deploy

EXTERNALSRC = "${HSOC_APOLLO_GEM5_SRC}"
EXTERNALSRC_BUILD = "${WORKDIR}/build"
EXTERNALSRC_SYMLINKS = ""
COMPATIBLE_MACHINE = "apollo-qvp"
PACKAGE_ARCH = "${MACHINE_ARCH}"
GEM5_APOLLO_BENCH_SOURCE ?= "${HSOC_APOLLO_BASE}/../scripts/gem5/benchmark.c"
GEM5_APOLLO_CONTROL_SOURCE ?= "${HSOC_APOLLO_BASE}/../scripts/gem5/control.c"

do_configure[noexec] = "1"
# The benchmark belongs to the workspace, outside the gem5 externalsrc tree.
python () {
    d.appendVarFlag("do_compile", "file-checksums",
                    " ${GEM5_APOLLO_BENCH_SOURCE}:True ${GEM5_APOLLO_CONTROL_SOURCE}:True")
}
do_compile[cleandirs] = "${B}"
do_compile() {
    # The standalone EL3 firmware does not initialize pointer authentication.
    oe_runmake -C ${S}/system/arm/bootloader/zena_css \
        BUILDDIR=${B}/firmware CC="${CC} -mbranch-protection=none" LD="${LD}" all
    ${CC} ${CPPFLAGS} ${CFLAGS} -std=c11 -O2 -Wall -Wextra -Werror \
        -static -pthread -march=armv8-a -mno-outline-atomics \
        -I${S}/workloads/zena_cmn ${GEM5_APOLLO_BENCH_SOURCE} \
        ${LDFLAGS} -o ${B}/apollo-bench
    ${CC} ${CPPFLAGS} ${CFLAGS} -std=c11 -O2 -Wall -Wextra -Werror \
        -static -pthread -march=armv8-a -mno-outline-atomics \
        ${S}/workloads/zena_cmn/memory_bench.c \
        ${LDFLAGS} -o ${B}/apollo-memory-bench
    ${CC} ${CPPFLAGS} ${CFLAGS} -std=c11 -O2 -Wall -Wextra -Werror \
        -static -march=armv8-a -mno-outline-atomics -I${S}/include \
        ${GEM5_APOLLO_CONTROL_SOURCE} ${S}/util/m5/src/abi/arm64/m5op.S \
        ${LDFLAGS} -Wl,-z,noexecstack -o ${B}/gem5-control
}

do_install() {
    install -d ${D}${bindir}
    install -m 0755 ${B}/apollo-bench ${D}${bindir}/apollo-bench
    install -m 0755 ${B}/apollo-memory-bench ${D}${bindir}/apollo-memory-bench
    install -m 0755 ${B}/gem5-control ${D}${bindir}/gem5-control
}
do_deploy() {
    install -d ${DEPLOYDIR}/gem5
    install -m 0644 ${B}/firmware/zena_css4.elf ${DEPLOYDIR}/gem5/
    install -m 0644 ${B}/firmware/zena_css16.elf ${DEPLOYDIR}/gem5/
    install -m 0755 ${B}/apollo-bench ${DEPLOYDIR}/gem5/
    install -m 0755 ${B}/apollo-memory-bench ${DEPLOYDIR}/gem5/
    install -m 0755 ${B}/gem5-control ${DEPLOYDIR}/gem5/
}
addtask deploy after do_compile before do_build
