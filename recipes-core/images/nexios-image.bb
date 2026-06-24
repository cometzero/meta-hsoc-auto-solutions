#
# SPDX-FileCopyrightText: <text>Copyright 2023-2026 Arm Limited and/or its
# affiliates <open-source-office@arm.com></text>
#
# SPDX-License-Identifier: MIT

SUMMARY = "Auto AD Nexios image"
DESCRIPTION = "An image recipe, based on core-image"
LICENSE = "MIT"

IMAGE_INSTALL = ""
IMAGE_LINGUAS = ""

inherit ewaol-image

IMAGE_OVERHEAD_FACTOR = "1.5"

inherit features_check
REQUIRED_IMAGE_FEATURES = "baremetal"
CONFLICT_IMAGE_FEATURES = "virtualization domu"

BAREMETAL_IMAGE_NUM_CPUS = "${PC_CPUS_COUNT}"
# The total RAM size is 4G and 32M of it has been allocated to Trusted OS.
# The remaining RAM space size is (4096 - 32)M
BAREMETAL_IMAGE_MEM_SIZE ?= "4064M"

BOOTLOADER_LINUX_APPEND:append = "\
    maxcpus=${BAREMETAL_IMAGE_NUM_CPUS} \
    mem=${BAREMETAL_IMAGE_MEM_SIZE} \
    "
TEST_CPU_HOTPLUG_NUM_CPUS = "${BAREMETAL_IMAGE_NUM_CPUS}"
