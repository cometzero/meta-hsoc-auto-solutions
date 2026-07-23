# SPDX-License-Identifier: MIT

IMAGE_CLASSES:append:auto-ad-nexios = " dm-verity-img"
DM_VERITY_IMAGE:auto-ad-nexios = "nexios-image"
DM_VERITY_IMAGE_TYPE:auto-ad-nexios = "ext4"
DM_VERITY_SEPARATE_HASH:auto-ad-nexios = "0"

require conf/distro/include/auto-ad-nexios-initramfs.inc
