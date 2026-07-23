# SPDX-License-Identifier: MIT

INITRAMFS_IMAGE:auto-ad-nexios = "nexios-initramfs-image"
INITRAMFS_FSTYPES:auto-ad-nexios = "cpio.gz"
INITRD_ARCHIVE:auto-ad-nexios = "${INITRAMFS_IMAGE}-${MACHINE}.${INITRAMFS_FSTYPES}"
