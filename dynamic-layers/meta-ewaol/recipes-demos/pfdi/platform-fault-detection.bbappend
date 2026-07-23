FILESEXTRAPATHS:prepend := "${THISDIR}/files:"

SRC_URI:append = " file://0001-pfdi-handle-missing-per-cpu-online-files.patch"

PACKAGES =+ "pfdi-bsp-app"

FILES:pfdi-bsp-app = " \
    ${bindir}/pfdi-sample-app \
    ${sysconfdir}/pfdi/*.pack \
"

RDEPENDS:pfdi-bsp-app = "libpfdi"
RDEPENDS:pfdi-demo-app += "pfdi-bsp-app"
