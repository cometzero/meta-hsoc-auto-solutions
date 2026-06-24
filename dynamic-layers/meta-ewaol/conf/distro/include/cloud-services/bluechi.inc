# SPDX-License-Identifier: MIT

# Local replacement for the kas-applied meta-ewaol bluechi.inc patch.

VIRTUAL-RUNTIME_container_engine:${BASE_DISTRO} = "podman"

DISTRO_FEATURES:append:${BASE_DISTRO} = " overlayfs"

OVERLAYFS_MOUNT_POINT[data] = "/var/volatile"
OVERLAYFS_WRITABLE_PATHS[data] = "/var/lib/containers/storage/overlay"
