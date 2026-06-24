# SPDX-License-Identifier: MIT

do_install:append() {
    sed -i \
        's/docker run "${engine_args}" "${image_name}"/docker run "${engine_args}" --network host "${image_name}"/' \
        "${D}/${TEST_COMMON_DIR}/container-engine-funcs.sh"
}
