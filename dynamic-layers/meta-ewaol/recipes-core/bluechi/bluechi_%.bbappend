# SPDX-License-Identifier: MIT

# Keep BlueChi's writable container overlay backed by the volatile tmpfs mount.
# Using the writable path itself as the backing mount creates a systemd ordering
# cycle between the overlay mount unit and its directory preparation service.
OVERLAYFS_MOUNT_POINT[data] = "/var/volatile"

do_install:append() {
    install -d ${D}${localstatedir}/lib/containers/storage/overlay
}
