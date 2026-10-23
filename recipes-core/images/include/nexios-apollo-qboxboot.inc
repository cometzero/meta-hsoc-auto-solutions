# SPDX-License-Identifier: MIT

IMAGE_CLASSES:append:apollo-qvp = " qboxboot"

QBOX_PROVIDER:apollo-qvp = "qbox-apollo-qvp-native"
QBOX_EXE:apollo-qvp = "platforms-vp"
QBOX_CONFIG:apollo-qvp = "platforms/apollo/apollo-qvp-saturn-v.lua"
QBOX_APOLLO_NUM_CPUS:apollo-qvp = "${PC_CPUS_COUNT}"
QBOX_ENV_PASSTHROUGH:append:apollo-qvp = " QBOX_APOLLO_NUM_CPUS"

# Embed the OS device tree in UKIs; the firmware FDT describes an earlier map.
KERNEL_DEVICETREE:apollo-qvp = "${APOLLO_QVP_DTB}"

QBOX_IMAGES[kernel] = "${KERNEL_IMAGETYPE}"
QBOX_IMAGES[dtb] = "${APOLLO_QVP_DTB}"
QBOX_IMAGES[rootfs_wic] = "${@d.getVar('IMAGE_LINK_NAME') + '.wic' if 'wic' in (d.getVar('IMAGE_FSTYPES') or '').split() else ''}"
QBOX_IMAGES[ap_flash] = "ap-flash-image.img"
QBOX_IMAGES[rse_flash] = "rse-flash-image.img"
QBOX_IMAGES[rse_otp] = "rse-otp-image.img"
QBOX_IMAGES[rse_rom] = "rse-rom-image.img"
QBOX_IMAGES[si0_ramfw] = "si0_ramfw.bin"
QBOX_IMAGES[si_cl1] = "zephyr-demos-cl1.bin"

# Full-system AutoSD UKI boot artifacts, deployed alongside both product and BSP images.
APOLLO_AUTOSD_BOOT_DEPENDS = ""
APOLLO_AUTOSD_BOOT_DEPENDS:apollo-qvp = "ukiboot:do_deploy"
do_build[depends] += "${APOLLO_AUTOSD_BOOT_DEPENDS}"

# The board's vMCU runs beside QBox, outside the AP root filesystem.
APOLLO_VMCU_DEPENDS = ""
APOLLO_VMCU_DEPENDS:apollo-qvp = "zephyr-vmcu:do_deploy qemu-apollo-native:do_deploy vmcu-silkit-native:do_deploy"
do_build[depends] += "${APOLLO_VMCU_DEPENDS}"
