# SPDX-License-Identifier: MIT

SUMMARY = "Nexios BSP validation initramfs"
DESCRIPTION = "BusyBox initramfs and boot-only disk for Apollo BSP validation."
LICENSE = "MIT"

APOLLO_DM_VERITY = "0"
IMAGE_CLASSES:remove:auto-ad-nexios = "dm-verity-img"
INITRAMFS_IMAGE:auto-ad-nexios = ""
INITRD_ARCHIVE:auto-ad-nexios = ""
DM_VERITY_IMAGE:auto-ad-nexios = ""
DM_VERITY_IMAGE_TYPE:auto-ad-nexios = ""
DISTRO_FEATURES:remove:auto-ad-nexios = "overlayfs"

inherit core-image auto-ad-nexios-uki-ab

require recipes-core/images/include/nexios-apollo-qboxboot.inc

PACKAGE_INSTALL = " \
    base-files \
    base-passwd \
    busybox \
    busybox-udhcpc \
    dropbear \
    nexios-bsp-init \
    kmod \
    util-linux-mount \
    util-linux-lsblk \
    iproute2-ip \
    perf \
    arm-si-rproc-mod \
    kernel-module-virtio-rpmsg-bus \
    rpmsg-net-mod \
    pfdi-misc-mod \
    pfdi-bsp-app \
"
PACKAGE_INSTALL:append:apollo-fvp = " libgpiod-tools"
PACKAGE_INSTALL:append:apollo-qvp = " libgpiod-tools"

IMAGE_FEATURES = "allow-empty-password allow-root-login empty-root-password"
IMAGE_FEATURES:auto-ad-nexios = "allow-empty-password allow-root-login empty-root-password"
IMAGE_FEATURES:remove:auto-ad-nexios = " \
    baremetal \
    bash-completion-pkgs \
    cloud-service \
    demos \
    post-install-logging \
    ssh-server-openssh \
"
EXTRA_IMAGE_FEATURES:auto-ad-nexios = ""
IMAGE_LINGUAS = ""
IMAGE_NAME_SUFFIX ?= ""
IMAGE_FSTYPES = "cpio.gz wic"
NO_RECOMMENDATIONS = "1"

AUTO_AD_NEXIOS_UKI_A = "nexios-bsp-initramfs-a.efi"
AUTO_AD_NEXIOS_UKI_B = "nexios-bsp-initramfs-b.efi"
AUTO_AD_NEXIOS_UKI_ESP_A = "auto-ad-nexios-a.efi"
AUTO_AD_NEXIOS_UKI_ESP_B = "auto-ad-nexios-b.efi"
AUTO_AD_NEXIOS_UKI_CMDLINE_A = "rdinit=/init rw console=${KERNEL_CONSOLE} ${BOOTLOADER_LINUX_APPEND}"
AUTO_AD_NEXIOS_UKI_CMDLINE_B = "${AUTO_AD_NEXIOS_UKI_CMDLINE_A}"
AUTO_AD_NEXIOS_UKI_INITRD = "${IMGDEPLOYDIR}/${IMAGE_LINK_NAME}.cpio.gz"

WKS_FILE:apollo-fvp:auto-ad-nexios = "apollo-fvp-nexios-bsp-initramfs.wks.in"
WKS_FILE:apollo-qvp:auto-ad-nexios = "apollo-qvp-nexios-bsp-initramfs.wks.in"
WKS_FILE_DEPENDS:append:apollo-fvp:auto-ad-nexios = " auto-ad-nexios-boot-state"
WKS_FILE_DEPENDS:append:apollo-qvp:auto-ad-nexios = " auto-ad-nexios-boot-state"

BAREMETAL_IMAGE_NUM_CPUS = "${PC_CPUS_COUNT}"
BAREMETAL_IMAGE_MEM_SIZE ?= "4064M"
BOOTLOADER_LINUX_APPEND:append = " \
    maxcpus=${BAREMETAL_IMAGE_NUM_CPUS} \
    mem=${BAREMETAL_IMAGE_MEM_SIZE} \
"

addtask uki after do_image_cpio before do_image_wic do_image_complete
