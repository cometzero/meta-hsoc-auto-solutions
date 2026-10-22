# SPDX-License-Identifier: MIT
SUMMARY = "Minimal Nexios initramfs for Apollo gem5 AP workloads"
LICENSE = "MIT"
COMPATIBLE_MACHINE = "apollo-qvp"

APOLLO_DM_VERITY = "0"
IMAGE_CLASSES:remove:auto-ad-nexios = "dm-verity-img"
INITRAMFS_IMAGE:auto-ad-nexios = ""
INITRD_ARCHIVE:auto-ad-nexios = ""
DM_VERITY_IMAGE:auto-ad-nexios = ""
DM_VERITY_IMAGE_TYPE:auto-ad-nexios = ""
DISTRO_FEATURES:remove:auto-ad-nexios = "overlayfs"

inherit core-image

PACKAGE_INSTALL = "base-files base-passwd busybox nexios-gem5-init gem5-apollo-guest \
                   lmbench tinymembench stream stream-gem5-cache"
IMAGE_FEATURES = ""
IMAGE_FEATURES:auto-ad-nexios = ""
IMAGE_FEATURES:remove:auto-ad-nexios = "baremetal bash-completion-pkgs cloud-service demos post-install-logging ssh-server-openssh"
EXTRA_IMAGE_FEATURES:auto-ad-nexios = ""
IMAGE_LINGUAS = ""
IMAGE_NAME_SUFFIX = ""
IMAGE_FSTYPES = "cpio.gz"
NO_RECOMMENDATIONS = "1"

do_build[depends] += "gem5-native:do_build virtual/kernel:do_deploy"
