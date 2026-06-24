# SPDX-License-Identifier: MIT

do_shared_workdir:append() {
    if [ "${MODSIGN_ENABLED}" = "1" ] && [ -f modsign_key.pem ]; then
        cp modsign_key.pem "${kerneldir}/"
    fi
}
