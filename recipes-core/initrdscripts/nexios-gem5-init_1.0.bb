# SPDX-License-Identifier: MIT
SUMMARY = "Minimal init and workload entry point for Apollo gem5"
LICENSE = "MIT"
LIC_FILES_CHKSUM = "file://${COMMON_LICENSE_DIR}/MIT;md5=0835ade698e0bcf8506ecda2f7b4f302"
SRC_URI = "file://init file://gem5-workload"
S = "${UNPACKDIR}"

do_install() {
    install -m 0755 ${S}/init ${D}/init
    install -d ${D}${bindir}
    install -m 0755 ${S}/gem5-workload ${D}${bindir}/gem5-workload
}
FILES:${PN} += "/init"
RDEPENDS:${PN} = "busybox gem5-apollo-guest"
