# SPDX-License-Identifier: MIT

IMAGE_FEATURES:append:pn-nexios-image:auto-ad-nexios = " read-only-rootfs overlayfs-etc"
IMAGE_INSTALL:append:pn-nexios-image:auto-ad-nexios = " auto-ad-nexios-storage perf"
IMAGE_FSTYPES:append:pn-nexios-image:auto-ad-nexios = "${@bb.utils.contains('APOLLO_DM_VERITY', '1', '', ' ext4', d)}"

python __anonymous() {
    if d.getVar("DISTRO") != "auto-ad-nexios":
        return
    if d.getVar("PN") != "nexios-image":
        return
    if d.getVar("APOLLO_DM_VERITY") == "1":
        return
    if "wic" not in (d.getVar("IMAGE_FSTYPES") or "").split():
        return

    d.appendVarFlag("do_image_wic", "depends", " %s:do_image_ext4" % d.getVar("PN"))
}

CONVERSION_CMD:verity:append:pn-nexios-image:auto-ad-nexios = "; auto_ad_nexios_deploy_dm_verity_env ${type}"

inherit_defer ${@'auto-ad-nexios-uki-ab' if d.getVar("DISTRO") == "auto-ad-nexios" else ''}

ROOTFS_POSTPROCESS_COMMAND:append:pn-nexios-image:auto-ad-nexios = " auto_ad_nexios_check_overlay_storage; "

HSOC_FVP_WRITABLE_FLASH_DIR = "${TMPDIR}/fvp-writable/${PN}/${IMAGE_LINK_NAME}"
FVP_CONFIG[css.smb.rseil.rse_flashloader.fnameWrite] = "${HSOC_FVP_WRITABLE_FLASH_DIR}/rse-flash-image.img"
FVP_CONFIG[ros.flash_loader.fnameWrite] = "${HSOC_FVP_WRITABLE_FLASH_DIR}/ap-flash-image.img"

do_testimage[prefuncs] += "hsoc_prepare_fvp_writable_flash"
do_testimage[cleandirs] += "${HSOC_FVP_WRITABLE_FLASH_DIR}"

python hsoc_prepare_fvp_writable_flash() {
    import os
    import shutil

    if d.getVar("MACHINE") != "apollo-fvp":
        return

    writable_dir = d.getVar("HSOC_FVP_WRITABLE_FLASH_DIR")
    bb.utils.mkdirhier(writable_dir)
    deploy_dir = d.getVar("DEPLOY_DIR_IMAGE")

    for name in ("rse-flash-image.img", "ap-flash-image.img"):
        src = os.path.join(deploy_dir, name)
        dst = os.path.join(writable_dir, name)
        if not os.path.exists(src):
            bb.fatal("Missing Apollo FVP flash image for OEQA: %s" % src)
        shutil.copy2(src, dst)
}

auto_ad_nexios_deploy_dm_verity_env() {
    local type="$1"

    if [ "${DISTRO}" != "auto-ad-nexios" ]; then
        return
    fi

    if [ "${PN}" != "${DM_VERITY_IMAGE}" ]; then
        return
    fi

    install -m 0644 \
        "${STAGING_VERITY_DIR}/${DM_VERITY_IMAGE}.${type}.verity.env" \
        "${IMGDEPLOYDIR}/${IMAGE_NAME}.${type}.verity.env"

    ln -sf "${IMAGE_NAME}.${type}.verity.env" \
        "${IMGDEPLOYDIR}/${IMAGE_BASENAME}-${MACHINE}${IMAGE_NAME_SUFFIX}.${type}.verity.env"
}

auto_ad_nexios_check_overlay_storage() {
    if [ "${DISTRO}" != "auto-ad-nexios" ]; then
        return
    fi

    if [ "${OVERLAYFS_ETC_DEVICE}" != "LABEL=rootrw" ]; then
        bbfatal "auto-ad-nexios requires OVERLAYFS_ETC_DEVICE=LABEL=rootrw"
    fi

    if [ "${OVERLAYFS_ETC_CREATE_MOUNT_DIRS}" != "0" ]; then
        bbfatal "auto-ad-nexios must not remount dm-verity rootfs rw to create overlay mount directories"
    fi

    if [ ! -d "${IMAGE_ROOTFS}/rootrw" ]; then
        bbfatal "auto-ad-nexios rootrw mount point is missing from rootfs"
    fi

    if [ ! -d "${IMAGE_ROOTFS}/data" ]; then
        bbfatal "auto-ad-nexios /data mount point is missing from rootfs"
    fi

    if [ ! -d "${IMAGE_ROOTFS}/efi" ]; then
        bbfatal "auto-ad-nexios /efi mount point is missing from rootfs"
    fi

    if ! grep -q '^if false; then$' "${IMAGE_ROOTFS}/sbin/init"; then
        bbfatal "auto-ad-nexios overlayfs-etc preinit must not create mount dirs by remounting / rw"
    fi

    if [ ! -L "${IMAGE_ROOTFS}/var/run" ]; then
        bbfatal "auto-ad-nexios must preserve /var/run as a symlink to volatile /run"
    fi

    if ! grep -Eq '^[[:space:]]*tmpfs[[:space:]]+/run[[:space:]]+tmpfs[[:space:]]+' "${IMAGE_ROOTFS}/etc/fstab"; then
        bbfatal "auto-ad-nexios must preserve tmpfs /run in /etc/fstab"
    fi

    if ! grep -q '^What=LABEL=rootrw$' "${IMAGE_ROOTFS}${systemd_system_unitdir}/rootrw.mount"; then
        bbfatal "auto-ad-nexios rootrw.mount must use LABEL=rootrw"
    fi

    if ! grep -q '^What=PARTLABEL=data$' "${IMAGE_ROOTFS}${systemd_system_unitdir}/data.mount"; then
        bbfatal "auto-ad-nexios data.mount must use PARTLABEL=data"
    fi

    for unit in systemd-resolved.service systemd-timesyncd.service; do
        if ! grep -q '^After=var-volatile-lib.service$' \
            "${IMAGE_ROOTFS}${systemd_system_unitdir}/${unit}.d/auto-ad-nexios-after-var-lib.conf"
        then
            bbfatal "auto-ad-nexios ${unit} must start after volatile /var/lib is mounted"
        fi
    done

    if [ -L "${IMAGE_ROOTFS}${sysconfdir}/systemd/system/default.target.wants/podman.service" ]; then
        bbfatal "auto-ad-nexios must not auto-start podman.service; use podman.socket activation"
    fi

    if [ ! -L "${IMAGE_ROOTFS}${sysconfdir}/systemd/system/sockets.target.wants/podman.socket" ]; then
        bbfatal "auto-ad-nexios must enable podman.socket for socket activation"
    fi
}
