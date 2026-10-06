# SPDX-License-Identifier: MIT
SUMMARY = "SIL Kit native SDK and registry"
HOMEPAGE = "https://github.com/vectorgrp/sil-kit"
# Built dependencies: Asio (BSL), fmt/spdlog/rapidyaml (MIT).
# Google Test and Oat++ sources are fetched but their targets are disabled.
LICENSE = "MIT & BSL-1.0"
LIC_FILES_CHKSUM = "file://LICENSE;md5=95654a2cab6505c130d8de2d06a4d1b8 \
                    file://ThirdParty/LICENSES.rst;md5=2ba08bd0012ae39be25fabb1ec19eaf1"

SRC_URI = "gitsm://github.com/vectorgrp/sil-kit.git;protocol=https;nobranch=1 \
           file://0001-honor-package-symbols-option.patch"
SRCREV = "fcb625632ad82edd85e322e1ec0de6f021bff497"
S = "${UNPACKDIR}/git"

inherit cmake native

EXTRA_OECMAKE = "-DSILKIT_BUILD_DEMOS=OFF \
                 -DSILKIT_BUILD_TESTS=OFF \
                 -DSILKIT_BUILD_UTILITIES=ON \
                 -DSILKIT_BUILD_DOCS=OFF \
                 -DSILKIT_BUILD_DASHBOARD=OFF \
                 -DSILKIT_INSTALL_SOURCE=OFF \
                 -DSILKIT_USE_SYSTEM_LIBRARIES=OFF \
                 -DSILKIT_BUILD_REPRODUCIBLE=ON \
                 -DSILKIT_PACKAGE_SYMBOLS=OFF"

do_install:append() {
    install -d ${D}${datadir}/licenses/sil-kit
    install -m 0644 ${S}/LICENSE ${S}/ThirdParty/LICENSES.rst ${D}${datadir}/licenses/sil-kit/
}
