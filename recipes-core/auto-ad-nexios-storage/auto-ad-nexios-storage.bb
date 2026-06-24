# SPDX-License-Identifier: MIT

SUMMARY = "Auto AD Nexios writable storage mount units"
DESCRIPTION = "Installs rootrw and data mount metadata for the Auto AD Nexios read-only root filesystem profile."
LICENSE = "MIT"
LIC_FILES_CHKSUM = "file://${COMMON_LICENSE_DIR}/MIT;md5=0835ade698e0bcf8506ecda2f7b4f302"

SRC_URI = " \
    file://auto-ad-nexios-after-var-lib.conf \
    file://data.mount \
    file://rootrw.mount \
"

S = "${UNPACKDIR}"

inherit features_check systemd

REQUIRED_DISTRO_FEATURES = "systemd"

SYSTEMD_SERVICE:${PN} = "rootrw.mount data.mount"
SYSTEMD_AUTO_ENABLE:${PN} = "enable"

do_install() {
    install -d ${D}/efi
    install -d ${D}/rootrw
    install -d ${D}/data
    install -d ${D}${systemd_system_unitdir}
    install -d ${D}${systemd_system_unitdir}/systemd-resolved.service.d
    install -d ${D}${systemd_system_unitdir}/systemd-timesyncd.service.d

    install -m 0644 ${UNPACKDIR}/rootrw.mount ${D}${systemd_system_unitdir}/rootrw.mount
    install -m 0644 ${UNPACKDIR}/data.mount ${D}${systemd_system_unitdir}/data.mount
    install -m 0644 ${UNPACKDIR}/auto-ad-nexios-after-var-lib.conf \
        ${D}${systemd_system_unitdir}/systemd-resolved.service.d/auto-ad-nexios-after-var-lib.conf
    install -m 0644 ${UNPACKDIR}/auto-ad-nexios-after-var-lib.conf \
        ${D}${systemd_system_unitdir}/systemd-timesyncd.service.d/auto-ad-nexios-after-var-lib.conf
}

FILES:${PN} = " \
    /efi \
    /rootrw \
    /data \
    ${systemd_system_unitdir}/rootrw.mount \
    ${systemd_system_unitdir}/data.mount \
    ${systemd_system_unitdir}/systemd-resolved.service.d/auto-ad-nexios-after-var-lib.conf \
    ${systemd_system_unitdir}/systemd-timesyncd.service.d/auto-ad-nexios-after-var-lib.conf \
"
