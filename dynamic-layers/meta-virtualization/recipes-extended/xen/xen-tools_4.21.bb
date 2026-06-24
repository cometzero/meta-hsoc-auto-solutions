# SPDX-License-Identifier: MIT

SRCREV ?= "06af9ef22996cecc2024a2e6523cec77a655581e"

XEN_REL ?= "4.21"
XEN_BRANCH ?= "stable-4.21"

SRC_URI = " \
    git://xenbits.xen.org/xen.git;branch=${XEN_BRANCH} \
    file://0001-python-pygrub-pass-DISTUTILS-xen-4.19.patch \
    file://0001-libxl_nocpuid-fix-build-error.patch \
    file://0001-tools-libxl-Fix-build-with-NOCPUID-and-json-c.patch \
    "

LIC_FILES_CHKSUM ?= "file://COPYING;md5=d1a1e216f80b6d8da95fec897d0dbec9"

PV = "${XEN_REL}+stable"
S = "${WORKDIR}/git"
DEFAULT_PREFERENCE ??= "-1"
VIRTUALIZATION_XEN_FILESDIR := "${@d.getVar('BBFILE_PATTERN_virtualization-layer').lstrip('^')}recipes-extended/xen/files"
FILESEXTRAPATHS:prepend := "${VIRTUALIZATION_XEN_FILESDIR}:"

require recipes-extended/xen/xen.inc
require recipes-extended/xen/xen-tools.inc

RDEPENDS:${PN} += "${PN}-libxenmanage"

PACKAGES += " \
    ${PN}-libxenmanage \
    ${PN}-libxenmanage-dev \
"

FILES:${PN}-staticdev += "${libdir}/libxenmanage.a"

FILES:${PN}-libxenmanage = "${libdir}/libxenmanage.so.*"
FILES:${PN}-libxenmanage-dev = " \
    ${libdir}/libxenmanage.so \
    ${libdir}/pkgconfig/xenmanage.pc \
    ${datadir}/pkgconfig/xenmanage.pc \
"

FILES:${PN}-xen-watchdog += " \
    ${systemd_unitdir}/system-sleep/xen-watchdog-sleep.sh \
"

FILES:${PN}-test += " \
    ${libdir}/xen/tests/test-xenstore \
    ${libdir}/xen/tests/test-rangeset \
    ${libdir}/xen/tests/test-resource \
    ${libdir}/xen/tests/test-domid \
    ${libdir}/xen/tests/test-paging-mempool \
    ${libdir}/xen/tests/test_vpci \
    ${libdir}/xen/tests/test-pdx-offset \
    ${libdir}/xen/tests/test-pdx-mask \
"
