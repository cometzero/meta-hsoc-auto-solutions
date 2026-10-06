# SPDX-License-Identifier: MIT
SUMMARY = "Pinned GNU TriCore bare-metal compiler for the TC397 vMCU"
HOMEPAGE = "https://github.com/linumiz/aurix-gcc-toolchain"
LICENSE = "GPL-3.0-with-GCC-exception & GPL-3.0-only & LGPL-2.0-only & LGPL-3.0-only & BSD-3-Clause & BSD-2-Clause"
LIC_FILES_CHKSUM = " \
    file://LICENSES/GCC/COPYING3;md5=d32239bcb673463ab874e80d47fae504 \
    file://LICENSES/GCC/COPYING.RUNTIME;md5=fe60d87048567d4fe8c8a0ed2448bcc8 \
    file://LICENSES/NEWLIB/COPYING.NEWLIB;md5=268981f19d5ccd3f85036a755aaa3b2c \
"

SRC_URI = "https://github.com/linumiz/aurix-gcc-toolchain/releases/download/v${PV}/aurixgcc_03-2026_Linux_x86-x64.zip;subdir=toolchain"
SRC_URI[sha256sum] = "4d2a82c0bd2a65657e9f5212c75c6d9e5fab325d24baf632ff19b5214a332858"
S = "${UNPACKDIR}/toolchain"

inherit native
COMPATIBLE_HOST = "x86_64.*-linux"
INHIBIT_DEFAULT_DEPS = "1"
INHIBIT_SYSROOT_STRIP = "1"
TRICORE_TOOLCHAIN_DIR = "${libexecdir}/tricore-toolchain"
SYSROOT_DIRS += "${TRICORE_TOOLCHAIN_DIR}"

do_configure[noexec] = "1"
do_compile[noexec] = "1"
do_install() {
    install -d ${D}${TRICORE_TOOLCHAIN_DIR}
    cp -R --no-preserve=ownership ${S}/. ${D}${TRICORE_TOOLCHAIN_DIR}/
    # The release ZIP does not retain executable permissions.
    find ${D}${TRICORE_TOOLCHAIN_DIR}/bin \
         ${D}${TRICORE_TOOLCHAIN_DIR}/libexec \
         ${D}${TRICORE_TOOLCHAIN_DIR}/tricore-elf/bin \
         ${D}${TRICORE_TOOLCHAIN_DIR}/mcs-elf/bin -type f -exec chmod 0755 {} +
}
