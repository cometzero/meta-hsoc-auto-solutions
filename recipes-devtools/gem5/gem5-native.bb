# SPDX-License-Identifier: MIT
SUMMARY = "gem5 ARM simulator for the Apollo application domain"
HOMEPAGE = "https://www.gem5.org/"
LICENSE = "BSD-3-Clause & BSD-2-Clause & MIT & Apache-2.0"
LIC_FILES_CHKSUM = " \
    file://LICENSE;md5=a585e2893cee63d16a1d8bc16c6297ec \
    file://COPYING;md5=2d9514d69d8abf88b6e9125e759bf0ab \
    file://ext/libfdt/README;md5=b5faf5bf5660425b3f9f38a65715e967 \
    file://ext/nomali/LICENSE;md5=3b83ef96387f14655fc854ddc3c6bd57 \
"

inherit scons pkgconfig externalsrc deploy native

EXTERNALSRC = "${HSOC_APOLLO_GEM5_SRC}"
EXTERNALSRC_BUILD = "${WORKDIR}/build"
EXTERNALSRC_SYMLINKS = ""
CONFIGURE_FILES = "SConstruct build_opts/ARM"
DEPENDS += "libpng-native m4-native python3-pyyaml-native zlib-native"
DEPLOY_DIR_IMAGE = "${DEPLOY_DIR}/gem5-native"

# gem5 probes CXX as one executable; libelf also invokes a literal "cc".
export CC = "${B}/host-tools/cc"
export CXX = "${B}/host-tools/c++"
PATH:prepend = "${B}/host-tools:"

# gem5 consumes these variables instead of the usual CFLAGS/LDFLAGS.
export CCFLAGS_EXTRA = "${CFLAGS}"
export LINKFLAGS_EXTRA = "${LDFLAGS}"
export GEM5PY_CCFLAGS_EXTRA = "${CFLAGS}"
export GEM5PY_LINKFLAGS_EXTRA = "${LDFLAGS}"
export CPATH = "${STAGING_INCDIR_NATIVE}"
export LIBRARY_PATH = "${STAGING_LIBDIR_NATIVE}"
export LD_LIBRARY_PATH = "${STAGING_LIBDIR_NATIVE}:${STAGING_BASE_LIBDIR_NATIVE}"
export PYTHON_CONFIG = "${STAGING_BINDIR_NATIVE}/python3-config"

EXTRA_OESCONS = "--ignore-style --without-tcmalloc ${B}/ARM/gem5.opt"

do_configure() {
    install -d ${B}/host-tools
    printf '#!/bin/sh\nexec ${BUILD_CC} "$@"\n' > ${B}/host-tools/cc
    printf '#!/bin/sh\nexec ${BUILD_CXX} "$@"\n' > ${B}/host-tools/c++
    chmod 0755 ${B}/host-tools/cc ${B}/host-tools/c++

    # Keep host acceleration and optional host libraries out of the AP model.
    cat ${S}/build_opts/ARM > ${B}/apollo.defconfig
    printf '\nUSE_CAPSTONE=n\nUSE_SYSTEMC=n\nUSE_KVM=n\n' >> ${B}/apollo.defconfig
    ${STAGING_BINDIR_NATIVE}/scons --directory=${S} \
        --ignore-style --without-tcmalloc \
        defconfig ${B}/ARM ${B}/apollo.defconfig
}

do_install() {
    install -d ${D}${bindir}
    install -m 0755 ${B}/ARM/gem5.opt ${D}${bindir}/gem5.opt
}

python do_deploy() {
    import json
    import os
    import shutil

    destination = d.getVar('DEPLOYDIR')
    shutil.copy2(os.path.join(d.getVar('B'), 'ARM', 'gem5.opt'),
                 os.path.join(destination, 'gem5.opt'))
    manifest = {
        'schema_version': 1,
        'executable': os.path.join(d.getVar('DEPLOY_DIR_IMAGE'), 'gem5.opt'),
        'library_path': [d.getVar('STAGING_LIBDIR_NATIVE'),
                         d.getVar('STAGING_BASE_LIBDIR_NATIVE')],
        'python_home': os.path.join(d.getVar('STAGING_DIR_NATIVE'), 'usr'),
        'source': d.getVar('EXTERNALSRC'),
        'build_target': 'ARM/gem5.opt',
    }
    with open(os.path.join(destination, 'gem5-native.json'), 'w') as output:
        json.dump(manifest, output, indent=2, sort_keys=True)
        output.write('\n')
}
addtask deploy after do_populate_sysroot before do_build

do_build[depends] += "gem5-apollo-guest:do_deploy"
