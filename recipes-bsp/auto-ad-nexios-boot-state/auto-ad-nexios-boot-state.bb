#
# SPDX-License-Identifier: MIT
#

SUMMARY = "Default auto-ad-nexios misc boot-state blob"
DESCRIPTION = "Deploys the deterministic default A/B boot-state blob for the auto-ad-nexios misc raw partition."
HOMEPAGE = "https://gitlab.arm.com/automotive-and-industrial/arm-auto-solutions"
LICENSE = "MIT"
LIC_FILES_CHKSUM = "file://${COMMON_LICENSE_DIR}/MIT;md5=0835ade698e0bcf8506ecda2f7b4f302"

SRC_URI = "file://make-auto-ad-nexios-misc.py"

S = "${UNPACKDIR}"
B = "${WORKDIR}/build"

inherit deploy python3native

do_configure[noexec] = "1"
do_install[noexec] = "1"

do_compile() {
    install -d ${B}
    ${PYTHON} ${UNPACKDIR}/make-auto-ad-nexios-misc.py \
        --slot A \
        --out ${B}/auto-ad-nexios-misc-default.bin \
        --verify
}

do_deploy() {
    install -Dm0644 ${B}/auto-ad-nexios-misc-default.bin \
        ${DEPLOYDIR}/auto-ad-nexios-misc-default.bin
}

addtask deploy after do_compile before do_build
