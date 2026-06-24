# SPDX-License-Identifier: MIT

# The dm-verity initramfs only opens the verified root device. Keep the main
# image's login, demo, and container overlay policy out of this minimal image.
IMAGE_FEATURES:auto-ad-nexios = ""
IMAGE_FEATURES:remove:pn-dm-verity-image-initramfs:auto-ad-nexios = " \
    allow-empty-password \
    allow-root-login \
    baremetal \
    bash-completion-pkgs \
    cloud-service \
    demos \
    empty-root-password \
    post-install-logging \
    ssh-server-openssh \
"
EXTRA_IMAGE_FEATURES:pn-dm-verity-image-initramfs:auto-ad-nexios = ""
DISTRO_FEATURES:remove:pn-dm-verity-image-initramfs:auto-ad-nexios = "overlayfs"
