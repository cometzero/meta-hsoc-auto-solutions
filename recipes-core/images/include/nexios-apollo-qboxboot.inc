# SPDX-License-Identifier: MIT

IMAGE_CLASSES:append:apollo-qvp = " qboxboot"

QBOX_PROVIDER:apollo-qvp = "qbox-apollo-qvp-native"
QBOX_EXE:apollo-qvp = "platforms-vp"
QBOX_CONFIG:apollo-qvp = "platforms/apollo/apollo-qvp.lua"
QBOX_APOLLO_NUM_CPUS:apollo-qvp = "${PC_CPUS_COUNT}"
QBOX_ENV_PASSTHROUGH:append:apollo-qvp = " QBOX_APOLLO_NUM_CPUS"

QBOX_IMAGES[kernel] = "${KERNEL_IMAGETYPE}"
QBOX_IMAGES[dtb] = "apollo-qvp.dtb"
QBOX_IMAGES[rootfs_wic] = "${@d.getVar('IMAGE_LINK_NAME') + '.wic' if 'wic' in (d.getVar('IMAGE_FSTYPES') or '').split() else ''}"
QBOX_IMAGES[ap_flash] = "ap-flash-image.img"
QBOX_IMAGES[rse_flash] = "rse-flash-image.img"
QBOX_IMAGES[rse_otp] = "rse-otp-image.img"
QBOX_IMAGES[rse_rom] = "rse-rom-image.img"
QBOX_IMAGES[si0_ramfw] = "si0_ramfw.bin"
QBOX_IMAGES[si_cl1] = "zephyr-demos-cl1.bin"
