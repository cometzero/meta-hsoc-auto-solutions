# SPDX-License-Identifier: MIT

FILESEXTRAPATHS:prepend := "${THISDIR}/files:"

SRC_URI:append:apollo-fvp:baremetal = " file://10-ovsbr0.network"

python allarch_package_arch_handler:append:apollo-fvp:baremetal() {
    d.setVar("PACKAGE_ARCH", d.getVar("MACHINE_ARCH"))
}

do_install:append:apollo-fvp:baremetal() {
    install -m 0644 ${UNPACKDIR}/10-ovsbr0.network \
        ${D}${NETWORK_CONF_DIR}/10-ovsbr0.network
}
