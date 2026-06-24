# SPDX-License-Identifier: MIT

DESCRIPTION = "Simple Auto AD Nexios initramfs image for mounting the rootfs over the verity device mapper."

inherit core-image

PACKAGE_INSTALL = " \
    base-files \
    base-passwd \
    busybox \
    cryptsetup \
    initramfs-module-dmverity \
    initramfs-module-udev \
    lvm2 \
    udev \
    util-linux-mount \
"

# We want a clean, minimal image.
IMAGE_FEATURES = ""
IMAGE_LINGUAS = ""

IMAGE_NAME_SUFFIX ?= ""

# The initramfs only opens the verified root device. Keep the main image's
# login, demo, and container overlay policy out of this minimal image.
IMAGE_FEATURES:auto-ad-nexios = ""
IMAGE_FEATURES:remove:auto-ad-nexios = " \
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
EXTRA_IMAGE_FEATURES:auto-ad-nexios = ""
DISTRO_FEATURES:remove:auto-ad-nexios = "overlayfs"

ROOTFS_POSTPROCESS_COMMAND += "auto_ad_nexios_guard_efivarfs_mount; "

python auto_ad_nexios_guard_efivarfs_mount() {
    from pathlib import Path

    init_path = Path(d.getVar("IMAGE_ROOTFS")) / "init"
    text = init_path.read_text(encoding="utf-8")
    old = """if [ -d $EFI_DIR ];then
\tmount -t efivarfs none /sys/firmware/efi/efivars
fi"""
    new = """if [ -d "$EFI_DIR/efivars" ] && grep -qw efivarfs /proc/filesystems; then
\tmount -t efivarfs none "$EFI_DIR/efivars" 2>/dev/null || true
fi"""
    if old not in text:
        bb.fatal(f"Unable to patch efivarfs mount guard in {init_path}")
    init_path.write_text(text.replace(old, new, 1), encoding="utf-8")
}

# Can we somehow inspect reverse dependencies to avoid these variables?
python __anonymous() {
    verity_image = d.getVar('DM_VERITY_IMAGE')
    verity_type = d.getVar('DM_VERITY_IMAGE_TYPE')

    if verity_image and verity_type:
        dep = ' %s:do_image_%s' % (verity_image, verity_type.replace('-', '_'))
        d.appendVarFlag('do_image', 'depends', dep)
}

# Ensure dm-verity.env is updated also when rebuilding DM_VERITY_IMAGE
do_image[nostamp] = "1"

IMAGE_FSTYPES = "${INITRAMFS_FSTYPES}"

deploy_verity_hash() {
    install -D -m 0644 \
        ${STAGING_VERITY_DIR}/${DM_VERITY_IMAGE}.${DM_VERITY_IMAGE_TYPE}.verity.env \
        ${IMAGE_ROOTFS}${datadir}/misc/dm-verity.env
}
IMAGE_PREPROCESS_COMMAND += "deploy_verity_hash;"
