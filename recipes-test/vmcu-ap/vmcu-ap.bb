# SPDX-License-Identifier: MIT
SUMMARY = "Apollo management UART peer for the Zephyr TC397 vMCU"
DESCRIPTION = "Allowlisted ping/status peer; SI CL0 PFDI owns safety monitoring."
LICENSE = "GPL-2.0-or-later"
LIC_FILES_CHKSUM = "file://${COMMON_LICENSE_DIR}/GPL-2.0-only;md5=801f80980d171dd6425610833a22dbe6"

VMCU_SOURCE = "${HSOC_APOLLO_ZEPHYRPROJECT_SRC}/zephyr_vmcu_src"
FILESEXTRAPATHS:prepend := "${VMCU_SOURCE}/tools:${VMCU_SOURCE}/lib:${VMCU_SOURCE}/include:"
SRC_URI = "file://vmcu-ap.c file://protocol.c file://protocol.h file://rpc.c file://rpc.h"
S = "${UNPACKDIR}"

do_compile() {
    ${CC} ${CPPFLAGS} ${CFLAGS} -std=c11 -Wall -Wextra -Werror -I${S} \
        ${S}/vmcu-ap.c ${S}/protocol.c ${S}/rpc.c ${LDFLAGS} -o vmcu-ap
}

do_install() {
    install -d ${D}${bindir}
    install -m 0755 vmcu-ap ${D}${bindir}/vmcu-ap
}
