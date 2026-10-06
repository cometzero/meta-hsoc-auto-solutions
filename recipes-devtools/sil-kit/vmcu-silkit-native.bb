# SPDX-License-Identifier: MIT
SUMMARY = "Apollo vMCU SIL Kit CAN participant"
LICENSE = "MIT"
LIC_FILES_CHKSUM = "file://${COMMON_LICENSE_DIR}/MIT;md5=0835ade698e0bcf8506ecda2f7b4f302"

inherit cmake externalsrc deploy native

EXTERNALSRC = "${HSOC_APOLLO_BASE}/../scripts/silkit"
EXTERNALSRC_BUILD = "${WORKDIR}/build"
EXTERNALSRC_SYMLINKS = ""
DEPENDS = "sil-kit-native"
DEPLOY_DIR_IMAGE = "${DEPLOY_DIR}/vmcu-silkit-native"

# SilKit's exported CMake targets resolve its library inside this native sysroot.
EXTRA_OECMAKE = "-DSilKit_DIR=${STAGING_LIBDIR_NATIVE}/cmake/SilKit"

do_check() {
    ctest --test-dir ${B} --output-on-failure
}
addtask check after do_compile before do_install

python do_deploy() {
    import json
    import os

    native_root = d.getVar('STAGING_DIR_NATIVE')
    bindir = os.path.relpath(d.getVar('bindir'), native_root)
    component = os.path.join(d.getVar('COMPONENTS_DIR'), d.getVar('PACKAGE_ARCH'), d.getVar('PN'))
    manifest = {
        'schema_version': 1,
        'version': '5.0.7',
        'executable': os.path.join(component, bindir, 'vmcu-silkit'),
        'registry_executable': os.path.join(d.getVar('STAGING_BINDIR_NATIVE'), 'sil-kit-registry'),
        'library_path': [d.getVar('STAGING_LIBDIR_NATIVE'),
                         d.getVar('STAGING_BASE_LIBDIR_NATIVE')],
        'source': d.getVar('EXTERNALSRC'),
    }
    with open(os.path.join(d.getVar('DEPLOYDIR'), 'vmcu-silkit-native.json'), 'w') as output:
        json.dump(manifest, output, indent=2, sort_keys=True)
        output.write('\n')
}
addtask deploy after do_populate_sysroot before do_build
