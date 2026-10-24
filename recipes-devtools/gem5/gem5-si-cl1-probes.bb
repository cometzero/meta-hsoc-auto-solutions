# SPDX-License-Identifier: MIT
SUMMARY = "Apollo gem5 SI CL1 PMSA and Minor atomic regression probes"
LICENSE = "BSD-3-Clause"
LIC_FILES_CHKSUM = "file://tests/zena_si_cl1/pmsa.c;beginline=1;endline=1;md5=de1725a63086dd4e294708e0418c3a37"

inherit externalsrc deploy
EXTERNALSRC = "${HSOC_APOLLO_GEM5_SRC}"
EXTERNALSRC_BUILD = "${WORKDIR}/build"
EXTERNALSRC_SYMLINKS = ""
COMPATIBLE_MACHINE = "apollo-qvp"
PACKAGE_ARCH = "${MACHINE_ARCH}"

do_configure[noexec] = "1"
do_compile[cleandirs] = "${B}"
do_compile() {
    # Bare metal EL2 probe; do not inherit Linux hardening or libc startup.
    ${CC} -nostdlib -static -ffreestanding -fno-builtin \
        -fno-stack-protector -fno-pie -no-pie -mgeneral-regs-only \
        -mbranch-protection=none -march=armv8-a -O2 \
        -Wl,--build-id=none -Wl,-T,${S}/tests/zena_si_cl1/probe.ld \
        ${S}/tests/zena_si_cl1/start.S ${S}/tests/zena_si_cl1/pmsa.c \
        -o ${B}/gem5-si-cl1-pmsa.elf
    ${CC} -nostdlib -static -ffreestanding -fno-builtin \
        -fno-stack-protector -fno-pie -no-pie -mgeneral-regs-only \
        -mbranch-protection=none -march=armv8-a -O2 \
        -DPMSA_TEST_UNSUPPORTED_STAGE2 \
        -Wl,--build-id=none -Wl,-T,${S}/tests/zena_si_cl1/probe.ld \
        ${S}/tests/zena_si_cl1/start.S ${S}/tests/zena_si_cl1/pmsa.c \
        -o ${B}/gem5-si-cl1-stage2.elf
    # This executable uses gem5 SE only; it is not a Zephyr image.
    ${CC} -nostdlib -static -fno-pie -no-pie -march=armv8.1-a \
        -mbranch-protection=none -Wl,--build-id=none \
        ${S}/tests/zena_si_cl1/minor_atomic_speculation.S \
        -o ${B}/gem5-si-cl1-minor-atomic.elf
}
do_install[noexec] = "1"
do_deploy() {
    install -d ${DEPLOYDIR}/gem5
    install -m 0644 ${B}/gem5-si-cl1-pmsa.elf ${DEPLOYDIR}/gem5/
    install -m 0644 ${B}/gem5-si-cl1-stage2.elf ${DEPLOYDIR}/gem5/
    install -m 0644 ${B}/gem5-si-cl1-minor-atomic.elf ${DEPLOYDIR}/gem5/
    cd ${DEPLOYDIR}/gem5
    sha256sum gem5-si-cl1-pmsa.elf gem5-si-cl1-stage2.elf gem5-si-cl1-minor-atomic.elf > gem5-si-cl1-probes.sha256
}
addtask deploy after do_compile before do_build
