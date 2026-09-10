# SPDX-License-Identifier: MIT
SUMMARY = "ALSA playback-to-capture integrity test"
LICENSE = "MIT"
LIC_FILES_CHKSUM = "file://${COMMON_LICENSE_DIR}/MIT;md5=0835ade698e0bcf8506ecda2f7b4f302"
SRC_URI = "file://i2s_loopback.c"
S = "${UNPACKDIR}"
DEPENDS = "alsa-lib"

do_compile() {
    ${CC} ${CPPFLAGS} ${CFLAGS} ${LDFLAGS} ${S}/i2s_loopback.c -lasound -o i2s-loopback
}

do_install() {
    install -d ${D}${bindir}
    install -m 0755 i2s-loopback ${D}${bindir}/i2s-loopback
}
