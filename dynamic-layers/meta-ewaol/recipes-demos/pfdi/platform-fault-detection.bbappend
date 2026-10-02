FILESEXTRAPATHS:prepend := "${THISDIR}/files:"

SRC_URI:append = " file://0001-pfdi-handle-missing-per-cpu-online-files.patch"

PACKAGES =+ "pfdi-bsp-app"

FILES:pfdi-bsp-app = " \
    ${bindir}/pfdi-cli \
    ${bindir}/pfdi-sample-app \
    ${sysconfdir}/pfdi/*.pack \
"

RDEPENDS:pfdi-bsp-app = "libpfdi"
RDEPENDS:pfdi-demo-app += "pfdi-bsp-app"

# The QVP machine timing policy sets the AP online test interval in milliseconds.
# Keep the reference platform default when that policy is absent.
PFDI_AP_INTERVAL_MS ?= "60"
PACKAGE_ARCH:apollo-qvp = "${MACHINE_ARCH}"

do_install:append:apollo-qvp() {
    install -d ${WORKDIR}/apollo-qvp-pfdi
    PYSITE=$(echo ${D}${libdir}/python3*/site-packages)
    export PYTHONPATH="${PYSITE}"
    ${D}${bindir}/pfdi-tool generate 0 40 ${PFDI_AP_INTERVAL_MS} 1 ${PC_CPUS_COUNT} ${WORKDIR}/apollo-qvp-pfdi
    ${D}${bindir}/pfdi-tool pack ${WORKDIR}/apollo-qvp-pfdi
    install -m 0644 ${WORKDIR}/apollo-qvp-pfdi/pfdi_test_config_0.pack ${D}${sysconfdir}/pfdi
}
