# SPDX-License-Identifier: MIT
#
# Image class to write .qboxconf files for host-side QBox execution.

# Native recipe that provides the QBox executable, libraries, modules, and data
# through sysroots-components.
QBOX_PROVIDER ?= ""
QBOX_PROVIDER_VERSION ?= "1.0"
QBOX_PROVIDER_COMPONENTS_DIR ?= "${COMPONENTS_DIR}/${BUILD_ARCH}/${QBOX_PROVIDER}"
QBOX_PROVIDER_BINDIR ?= "${QBOX_PROVIDER_COMPONENTS_DIR}${bindir}"
QBOX_PROVIDER_LIBDIR ?= "${QBOX_PROVIDER_COMPONENTS_DIR}${libdir}"
QBOX_PROVIDER_MODULE_DIR ?= "${QBOX_PROVIDER_COMPONENTS_DIR}${libdir}/qbox/modules"
QBOX_PROVIDER_DATA_DIR ?= "${QBOX_PROVIDER_COMPONENTS_DIR}${datadir}/qbox"
QBOX_PROVIDER_WORKDIR ?= "${BASE_WORKDIR}/${BUILD_SYS}/${QBOX_PROVIDER}/${QBOX_PROVIDER_VERSION}"
QBOX_RECIPE_SYSROOT_NATIVE ?= "${QBOX_PROVIDER_WORKDIR}/recipe-sysroot-native"

# Relative executable and Lua platform configuration within the provider layout.
QBOX_EXE ?= ""
QBOX_CONFIG ?= ""

# Optional relative data entries and named image artifacts.
QBOX_DATA ?= ""
QBOX_ENV_PASSTHROUGH ?= ""

EXTRA_IMAGEDEPENDS += "${QBOX_PROVIDER}"

inherit image-artifact-names

addtask do_write_qboxboot_conf before do_image_complete

def qboxboot_enabled(d):
    return bool(d.getVar("QBOX_PROVIDER") or d.getVar("QBOX_EXE") or d.getVar("QBOX_CONFIG"))

def qboxboot_provider_dep(d):
    provider = d.getVar("QBOX_PROVIDER")
    if provider:
        return "%s:do_populate_sysroot" % provider
    return ""

def qboxboot_vars(d):
    build_vars = [
        "BASE_WORKDIR",
        "BUILD_ARCH",
        "BUILD_SYS",
        "COMPONENTS_DIR",
        "DEPLOY_DIR_IMAGE",
        "IMAGE_LINK_NAME",
        "IMAGE_NAME",
        "IMGDEPLOYDIR",
        "QBOX_CONFIG",
        "QBOX_DATA",
        "QBOX_ENV_PASSTHROUGH",
        "QBOX_EXE",
        "QBOX_PROVIDER",
        "QBOX_PROVIDER_BINDIR",
        "QBOX_PROVIDER_COMPONENTS_DIR",
        "QBOX_PROVIDER_DATA_DIR",
        "QBOX_PROVIDER_LIBDIR",
        "QBOX_PROVIDER_MODULE_DIR",
        "QBOX_RECIPE_SYSROOT_NATIVE",
    ]
    build_vars.extend(k for k in d.keys() if k.startswith("QBOX_"))
    return " ".join(sorted(set(build_vars)))

do_write_qboxboot_conf[depends] += "${@qboxboot_provider_dep(d)}"
do_write_qboxboot_conf[vardeps] += "${@qboxboot_vars(d)}"
do_write_qboxboot_conf[vardepsexclude] += "DATETIME SOURCE_DATE_EPOCH TOPDIR"
do_write_qboxboot_conf[dirs] = "${IMGDEPLOYDIR}"

python do_write_qboxboot_conf() {
    import json
    import os
    from pathlib import PurePosixPath
    import shlex

    if not qboxboot_enabled(d):
        return

    def required(varname):
        value = d.getVar(varname)
        if not value:
            bb.fatal("qboxboot: %s must be set when qboxboot config generation is enabled" % varname)
        return value

    def safe_relative(value):
        path = PurePosixPath(value)
        return bool(value) and not path.is_absolute() and "\x00" not in value and ".." not in path.parts

    def required_safe_relative(varname):
        value = required(varname)
        if not safe_relative(value):
            bb.fatal("qboxboot: %s must be a safe relative path: %s" % (varname, value))
        return value

    def get_flags(varname):
        flags = d.getVarFlags(varname) or {}
        ignored = {"doc", "func", "type", "vardeps", "vardepsexclude", "vardepvalue"}
        values = {}
        for key in sorted(flags):
            if key.startswith("_") or key in ignored:
                continue
            value = d.expand(flags[key])
            if value:
                values[key] = value
        return values

    provider = required("QBOX_PROVIDER")
    data_entries = shlex.split(d.getVar("QBOX_DATA") or "")
    images = get_flags("QBOX_IMAGES")

    for key, value in images.items():
        if not safe_relative(value):
            bb.fatal("qboxboot: QBOX_IMAGES[%s] must be a safe relative path: %s" % (key, value))

    env = {}
    for varname in (d.getVar("QBOX_ENV_PASSTHROUGH") or "").split():
        value = d.getVar(varname)
        if value is not None:
            env[varname] = value

    qboxconf = {
        "provider": {
            "name": provider,
            "bindir": required("QBOX_PROVIDER_BINDIR"),
            "libdir": required("QBOX_PROVIDER_LIBDIR"),
            "module_dir": required("QBOX_PROVIDER_MODULE_DIR"),
            "data_dir": required("QBOX_PROVIDER_DATA_DIR"),
        },
        "sysroot": {
            "components_dir": required("COMPONENTS_DIR"),
            "recipe_sysroot_native": required("QBOX_RECIPE_SYSROOT_NATIVE"),
        },
        "exe": required_safe_relative("QBOX_EXE"),
        "config": required_safe_relative("QBOX_CONFIG"),
    }
    if data_entries:
        qboxconf["data"] = data_entries
    if images:
        qboxconf["images"] = images
    if env:
        qboxconf["env"] = env

    conffile = os.path.join(d.getVar("IMGDEPLOYDIR"), d.getVar("IMAGE_NAME") + ".qboxconf")
    link_name = d.getVar("IMAGE_LINK_NAME")
    conffile_link = os.path.join(d.getVar("IMGDEPLOYDIR"), link_name + ".qboxconf") if link_name else ""

    bb.utils.mkdirhier(os.path.dirname(conffile))
    with open(conffile, "wt", encoding="utf-8") as f:
        json.dump(qboxconf, f, indent=2, sort_keys=True)
        f.write("\n")

    if conffile_link and conffile_link != conffile:
        if os.path.lexists(conffile_link):
            os.remove(conffile_link)
        os.symlink(os.path.basename(conffile), conffile_link)
}
