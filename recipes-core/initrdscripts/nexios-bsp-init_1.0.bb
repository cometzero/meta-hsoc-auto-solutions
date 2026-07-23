# SPDX-License-Identifier: MIT

SUMMARY = "Nexios BSP initramfs init and self-test"
DESCRIPTION = "Provides the PID 1 init script and console BSP smoke tests."
LICENSE = "MIT"
LIC_FILES_CHKSUM = "file://${COMMON_LICENSE_DIR}/MIT;md5=0835ade698e0bcf8506ecda2f7b4f302"

FILESEXTRAPATHS:prepend := "${THISDIR}/${PN}:"
SRC_URI = " \
    file://init \
    file://nexios-bsp-selftest \
"

S = "${UNPACKDIR}"

do_install() {
    install -m 0755 "${UNPACKDIR}/init" "${D}/init"
    install -d "${D}${libexecdir}/nexios-bsp"
    install -m 0755 \
        "${UNPACKDIR}/nexios-bsp-selftest" \
        "${D}${libexecdir}/nexios-bsp/selftest"
    install -d "${D}${sysconfdir}"
    printf '%s\n' "${MACHINE}" >"${D}${sysconfdir}/nexios-bsp-machine"
    printf '%s\n' "${PC_CPUS_COUNT}" >"${D}${sysconfdir}/nexios-bsp-cpus"
}

FILES:${PN} = " \
    /init \
    ${libexecdir}/nexios-bsp/selftest \
    ${sysconfdir}/nexios-bsp-machine \
    ${sysconfdir}/nexios-bsp-cpus \
"

RDEPENDS:${PN} = "busybox kmod"
