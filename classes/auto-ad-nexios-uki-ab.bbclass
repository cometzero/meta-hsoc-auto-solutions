# SPDX-License-Identifier: MIT

# Generate Auto AD Nexios slot-specific Unified Kernel Images. This class
# inherits the upstream UKI class for its image task wiring and dependency
# semantics, then replaces do_uki with an A/B generator.

inherit uki

IMAGE_CLASSES:append = " uki"

UEFI_SECURE_BOOT ?= "0"
AUTO_AD_NEXIOS_UEFI_SECURE_BOOT_DEFAULT ?= "0"

def auto_ad_nexios_uefi_secure_boot(d):
    history = getattr(d, "varhistory", None)
    if history:
        for event in history.variable("UEFI_SECURE_BOOT"):
            if event.get("op") == "set" and not event.get("flag"):
                return str(event.get("detail", "")).strip()

    return d.getVar("AUTO_AD_NEXIOS_UEFI_SECURE_BOOT_DEFAULT") or "0"

# The shared baremetal image feature enables UEFI secure boot with a
# :baremetal override. Auto AD Nexios keeps unsigned UKIs as the first-boot
# parity default, but a plain UEFI_SECURE_BOOT assignment must still be able to
# opt back into signing for negative and product-policy tests.
UEFI_SECURE_BOOT:baremetal:auto-ad-nexios = "${@auto_ad_nexios_uefi_secure_boot(d)}"

AUTO_AD_NEXIOS_UKI_A ?= "auto-ad-nexios-a.efi"
AUTO_AD_NEXIOS_UKI_B ?= "auto-ad-nexios-b.efi"

AUTO_AD_NEXIOS_UKI_CMDLINE_A ?= "rootwait root=PARTLABEL=rootro_a ro console=${KERNEL_CONSOLE} ${BOOTLOADER_LINUX_APPEND}"
AUTO_AD_NEXIOS_UKI_CMDLINE_B ?= "rootwait root=PARTLABEL=rootro_b ro console=${KERNEL_CONSOLE} ${BOOTLOADER_LINUX_APPEND}"

UKI_SB_KEY ?= "${@'${UEFI_SB_KEYS_DIR}/DB.key' if oe.types.boolean(d.getVar('UEFI_SECURE_BOOT') or '0') and d.getVar('UEFI_SB_KEYS_DIR') else ''}"
UKI_SB_CERT ?= "${@'${UEFI_SB_KEYS_DIR}/DB.crt' if oe.types.boolean(d.getVar('UEFI_SECURE_BOOT') or '0') and d.getVar('UEFI_SB_KEYS_DIR') else ''}"

DEPENDS:append = " ${@'sbsigntool-native' if oe.types.boolean(d.getVar('UEFI_SECURE_BOOT') or '0') else ''}"

# bootimg-efi uses label-specific IMAGE_EFI_BOOT_FILES variables before the
# fallback variable. Keep the existing ESP payload and add only the matching
# slot UKI to each boot partition.
AUTO_AD_NEXIOS_EFI_BOOT_FILES_BASE ?= "${IMAGE_EFI_BOOT_FILES}"
IMAGE_EFI_BOOT_FILES_label-boot_a = "${AUTO_AD_NEXIOS_EFI_BOOT_FILES_BASE} ${AUTO_AD_NEXIOS_UKI_A};EFI/Linux/${AUTO_AD_NEXIOS_UKI_A}"
IMAGE_EFI_BOOT_FILES_label-boot_b = "${AUTO_AD_NEXIOS_EFI_BOOT_FILES_BASE} ${AUTO_AD_NEXIOS_UKI_B};EFI/Linux/${AUTO_AD_NEXIOS_UKI_B}"
WICVARS:append = " IMAGE_EFI_BOOT_FILES_label-boot_a IMAGE_EFI_BOOT_FILES_label-boot_b"

do_image_wic[postfuncs] += "auto_ad_nexios_install_slot_ukis_into_wic"

auto_ad_nexios_wic_part_offset() {
    local wic="$1"
    local part_name="$2"

    sgdisk -p "$wic" | awk -v name="$part_name" '$7 == name {print $2 * 512}'
}

auto_ad_nexios_install_slot_uki() {
    local wic="$1"
    local part_name="$2"
    local uki="$3"
    local offset

    offset="$(auto_ad_nexios_wic_part_offset "$wic" "$part_name")"
    if [ -z "$offset" ]; then
        bbfatal "auto-ad-nexios: could not find ${part_name} in ${wic}"
    fi

    if [ ! -f "${DEPLOY_DIR_IMAGE}/${uki}" ]; then
        bbfatal "auto-ad-nexios: missing deployed UKI ${DEPLOY_DIR_IMAGE}/${uki}"
    fi

    mmd -i "${wic}@@${offset}" ::/EFI/Linux 2>/dev/null || true
    mcopy -o -i "${wic}@@${offset}" \
        "${DEPLOY_DIR_IMAGE}/${uki}" "::/EFI/Linux/${uki}"
}

auto_ad_nexios_install_slot_ukis_into_wic() {
    local wic="${IMGDEPLOYDIR}/${IMAGE_NAME}.wic"

    if [ ! -f "$wic" ]; then
        bbfatal "auto-ad-nexios: missing generated WIC image ${wic}"
    fi

    auto_ad_nexios_install_slot_uki "$wic" "boot_a" "${AUTO_AD_NEXIOS_UKI_A}"
    auto_ad_nexios_install_slot_uki "$wic" "boot_b" "${AUTO_AD_NEXIOS_UKI_B}"
}

python __anonymous() {
    import oe.types

    if not oe.types.boolean(d.getVar("UEFI_SECURE_BOOT") or "0"):
        return

    missing = [var for var in ("UKI_SB_KEY", "UKI_SB_CERT") if not d.getVar(var)]
    if missing:
        bb.fatal(
            "UEFI_SECURE_BOOT=1 requires UKI_SB_KEY and UKI_SB_CERT for "
            "auto-ad-nexios A/B UKI signing; missing: %s" % ", ".join(missing)
        )
}

python do_uki() {
    import os
    import shlex
    import bb.process
    import oe.types

    def quote(value):
        return shlex.quote(str(value))

    def require_file(path, description):
        if not path or not os.path.exists(path):
            bb.fatal("%s not found: %s" % (description, path or "<unset>"))

    def append_option(command, option, value):
        return "%s %s %s" % (command, option, quote(value))

    def append_joined_option(command, option, value):
        return "%s %s=%s" % (command, option, quote(value))

    deploy_dir_image = d.getVar("DEPLOY_DIR_IMAGE")
    target_arch = d.getVar("EFI_ARCH")
    secure_boot = oe.types.boolean(d.getVar("UEFI_SECURE_BOOT") or "0")

    command = d.getVar("UKIFY_CMD")
    if target_arch:
        command = append_option(command, "--efi-arch", target_arch)

    stub = "%s/linux%s.efi.stub" % (deploy_dir_image, target_arch)
    require_file(stub, "UKI EFI stub")
    command = append_option(command, "--stub", stub)

    initrd_archive = d.getVar("INITRD_ARCHIVE")
    initrd = os.path.join(deploy_dir_image, initrd_archive)
    require_file(initrd, "UKI initramfs")
    command = append_joined_option(command, "--initrd", initrd)

    kernel_filename = d.getVar("UKI_KERNEL_FILENAME")
    if not kernel_filename:
        bb.fatal("UKI_KERNEL_FILENAME is not set")
    kernel = os.path.join(deploy_dir_image, kernel_filename)
    require_file(kernel, "UKI kernel")
    command = append_joined_option(command, "--linux", kernel)

    kernel_version = d.getVar("KERNEL_VERSION")
    if kernel_version:
        command = append_option(command, "--uname", kernel_version)

    kernel_devicetree = d.getVar("KERNEL_DEVICETREE")
    if kernel_devicetree:
        for dtb in kernel_devicetree.split():
            dtb_path = os.path.join(deploy_dir_image, dtb)
            require_file(dtb_path, "UKI device tree")
            command = append_option(command, "--devicetree", dtb_path)

    config_file = d.getVar("UKI_CONFIG_FILE")
    if config_file and os.path.exists(config_file):
        command = append_joined_option(command, "--config", config_file)

    tools_dir = "%s%s/lib/systemd/tools" % (
        d.getVar("RECIPE_SYSROOT_NATIVE"),
        d.getVar("prefix"),
    )
    command = append_joined_option(command, "--tools", tools_dir)

    os_release = "%s%s/lib/os-release" % (
        d.getVar("RECIPE_SYSROOT"),
        d.getVar("prefix"),
    )
    command = append_joined_option(command, "--os-release", "@%s" % os_release)

    if secure_boot:
        key = d.getVar("UKI_SB_KEY")
        cert = d.getVar("UKI_SB_CERT")
        require_file(key, "UKI_SB_KEY")
        require_file(cert, "UKI_SB_CERT")
        command = "%s --sign-kernel" % command
        command = append_joined_option(command, "--secureboot-private-key", key)
        command = append_joined_option(command, "--secureboot-certificate", cert)

    slots = (
        ("A", d.getVar("AUTO_AD_NEXIOS_UKI_A"), d.getVar("AUTO_AD_NEXIOS_UKI_CMDLINE_A")),
        ("B", d.getVar("AUTO_AD_NEXIOS_UKI_B"), d.getVar("AUTO_AD_NEXIOS_UKI_CMDLINE_B")),
    )

    for slot, filename, cmdline in slots:
        if not filename:
            bb.fatal("Auto AD Nexios slot %s UKI filename is not set" % slot)
        if not cmdline:
            bb.fatal("Auto AD Nexios slot %s UKI command line is not set" % slot)
        output = os.path.join(deploy_dir_image, filename)
        slot_command = append_joined_option(command, "--cmdline", cmdline)
        slot_command = append_joined_option(slot_command, "--output", output)
        bb.note("auto-ad-nexios: generating slot %s UKI: %s" % (slot, output))
        bb.debug(2, "auto-ad-nexios UKI command: %s" % slot_command)
        out, err = bb.process.run(slot_command, shell=True)
        bb.debug(2, "%s\n%s" % (out, err))
}
