# SPDX-License-Identifier: MIT
# Use an explicit comparison baseline; upstream already disables LTO.
CFLAGS:append:apollo-qvp = " -O2 -fno-inline"

FILESEXTRAPATHS:prepend := "${THISDIR}/files:"
SRC_URI:append:apollo-qvp = " file://0001-gem5-loop-roi.patch"
LICENSE:append:apollo-qvp = " & BSD-3-Clause"
LIC_FILES_CHKSUM:append:apollo-qvp = " file://${HSOC_APOLLO_GEM5_SRC}/util/m5/src/abi/arm64/m5op.S;md5=303b810284fa71397f1ce5dc741bb174"
do_compile[file-checksums] += "${HSOC_APOLLO_GEM5_SRC}/util/m5/src/abi/arm64/m5op.S:True ${HSOC_APOLLO_GEM5_SRC}/include/gem5/m5ops.h:True ${HSOC_APOLLO_GEM5_SRC}/include/gem5/asm/generic/m5ops.h:True"

do_compile:append:apollo-qvp() {
    ${CC} ${CPPFLAGS} ${CFLAGS} -DGEM5_ROI -I${HSOC_APOLLO_GEM5_SRC}/include \
        -c ${S}/dhry_1.c -o ${B}/dhry_gem5.o
    ${CC} ${CPPFLAGS} ${CFLAGS} -I${HSOC_APOLLO_GEM5_SRC}/include \
        -c ${HSOC_APOLLO_GEM5_SRC}/util/m5/src/abi/arm64/m5op.S -o ${B}/m5op.o
    ${CC} ${LDFLAGS} -Wl,-z,noexecstack -o ${B}/dhry-gem5 \
        ${B}/dhry_gem5.o ${B}/dhry_2.o ${B}/m5op.o
    # Keep the O2 baseline and build both translation units at O3 for comparison.
    ${CC} ${CPPFLAGS} ${CFLAGS} -O3 -DGEM5_ROI -I${HSOC_APOLLO_GEM5_SRC}/include \
        -c ${S}/dhry_1.c -o ${B}/dhry_gem5_o3.o
    ${CC} ${CPPFLAGS} ${CFLAGS} -O3 -c ${S}/dhry_2.c -o ${B}/dhry_2_o3.o
    ${CC} ${LDFLAGS} -Wl,-z,noexecstack -o ${B}/dhry-gem5-o3 \
        ${B}/dhry_gem5_o3.o ${B}/dhry_2_o3.o ${B}/m5op.o
}

do_install:append:apollo-qvp() {
    install -m 0755 ${B}/dhry-gem5 ${D}${bindir}/dhry-gem5
    install -m 0755 ${B}/dhry-gem5-o3 ${D}${bindir}/dhry-gem5-o3
}
