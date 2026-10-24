# SPDX-License-Identifier: MIT
SUMMARY = "Standalone Apollo SI CL1 Zephyr memory and realtime benchmarks"
LICENSE = "Apache-2.0"
LIC_FILES_CHKSUM = "file://zephyr/LICENSE;md5=fa818a259cbed7ce8bc2a22d35a464fc"

ZEPHYR_TOOLCHAIN_VARIANT = "zephyr"
require recipes-kernel/zephyr-kernel/zephyr-kernel-common.inc
inherit externalsrc deploy

EXTERNALSRC = "${HSOC_APOLLO_ZEPHYRPROJECT_SRC}"
EXTERNALSRC_BUILD = "${WORKDIR}/build"
EXTERNALSRC_SYMLINKS = ""
COMPATIBLE_MACHINE = "apollo-qvp"
PACKAGE_ARCH = "${MACHINE_ARCH}"
ZEPHYR_BOARD = "apollo_si_cl1_bench"
ZEPHYR_MODULES = ""
ZEPHYR_SRC_DIR = "${HSOC_APOLLO_ZEPHYR_HSOC_SRC}/apps/si_cl1_bench"
OECMAKE_SOURCEPATH = "${ZEPHYR_SRC_DIR}"
EXTRA_OECMAKE:append = " -DBOARD_ROOT=${HSOC_APOLLO_ZEPHYR_HSOC_SRC}"

# Neither shared source tree is modified or patched during this build.
do_configure[file-checksums] += "${HSOC_APOLLO_ZEPHYR_SRC}:True ${HSOC_APOLLO_ZEPHYR_HSOC_SRC}:True"
do_compile[file-checksums] += "${HSOC_APOLLO_ZEPHYR_SRC}:True ${HSOC_APOLLO_ZEPHYR_HSOC_SRC}:True"
do_install[noexec] = "1"

python do_deploy() {
    import hashlib
    import json
    import pathlib
    import shutil
    import subprocess

    output = pathlib.Path(d.getVar("B")) / "zephyr"
    deploy = pathlib.Path(d.getVar("DEPLOYDIR"))
    deploy.mkdir(parents=True, exist_ok=True)
    artifacts = {}
    for suffix in ("elf", "bin", "map", "dts", "config"):
        source = output / (".config" if suffix == "config" else "zephyr." + suffix)
        target = deploy / (d.getVar("PN") + "." + suffix)
        shutil.copyfile(source, target)
        artifacts[target.name] = {"sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
                                  "size": target.stat().st_size}
    compiler = pathlib.Path(d.getVar("ZEPHYR_SDK_INSTALL_DIR")) / "aarch64-zephyr-elf/bin/aarch64-zephyr-elf-gcc"
    sources = {}
    for variable in ("HSOC_APOLLO_ZEPHYR_SRC", "HSOC_APOLLO_ZEPHYR_HSOC_SRC"):
        path = d.getVar(variable)
        sources[variable] = {"path": path, "revision": subprocess.check_output(
            ["git", "-C", path, "rev-parse", "HEAD"], text=True).strip(),
            "tracked_diff_sha256": hashlib.sha256(subprocess.check_output(
                ["git", "-C", path, "diff", "HEAD", "--binary"])).hexdigest()}
    # Include newly added board/app inputs even before their first commit.
    module = pathlib.Path(d.getVar("HSOC_APOLLO_ZEPHYR_HSOC_SRC"))
    inputs = {}
    for directory in (pathlib.Path(d.getVar("ZEPHYR_SRC_DIR")), module / "boards/hsoc/apollo_si_cl1_bench"):
        for path in sorted(directory.rglob("*")):
            if path.is_file():
                inputs[str(path.relative_to(module))] = hashlib.sha256(path.read_bytes()).hexdigest()
    manifest = {"board": d.getVar("ZEPHYR_BOARD"), "machine": d.getVar("MACHINE"),
                "counter_hz": 100000000, "sources": sources, "inputs": inputs, "artifacts": artifacts,
                "compiler": subprocess.check_output([str(compiler), "--version"], text=True)}
    (deploy / (d.getVar("PN") + "-manifest.json")).write_text(json.dumps(manifest, indent=2) + "\n")
}
addtask deploy after do_compile before do_build
