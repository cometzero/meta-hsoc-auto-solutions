from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import shutil
from typing import Final, Protocol, TypeAlias


type JsonValue = None | bool | int | float | str | list[JsonValue] | dict[str, JsonValue]
FvpConfig: TypeAlias = tuple[tuple[str, str], ...]
PROFILE_ENV: Final = "APOLLO_VALIDATION_FVP_CONFIG"
SI_CL1_UART: Final = "css.smb.si.cluster1_pl011_uart.uart_enable"
FVP_USER_NETWORKING: Final = "ros.virtio_net.hostbridge.userNetworking"
FVP_INTERFACE_NAME: Final = "ros.virtio_net.hostbridge.interfaceName"
APPROVED_FVP_CONFIG: Final = {
    SI_CL1_UART: "1",
    FVP_USER_NETWORKING: "0",
    FVP_INTERFACE_NAME: "apollo-fvp-tap0",
}
WRITABLE_FLASH_PAIRS: Final = (
    (
        "css.smb.rseil.rse_flashloader.fname",
        "css.smb.rseil.rse_flashloader.fnameWrite",
    ),
    ("ros.flash_loader.fname", "ros.flash_loader.fnameWrite"),
)
WRITABLE_IMAGE_KEYS: Final = (
    "css.smb.rseil.rse.lcm_nvm.raw_image",
    "ros.virtio_block0.image_path",
    "ros.virtio_block1.image_path",
)


class RuntimeLogger(Protocol):
    def debug(self, message: str, *values: str | Path) -> None: ...


@dataclass(frozen=True, slots=True)
class RuntimeConfigRequest:
    source: Path
    bootlog: Path
    logger: RuntimeLogger


class FvpConfigError(ValueError):
    pass


def _mapping(value: JsonValue, field: str) -> dict[str, JsonValue]:
    if not isinstance(value, dict):
        raise FvpConfigError(f"FVP config field {field} must be an object")
    return value


def _selected_config() -> FvpConfig:
    raw = os.environ.get(PROFILE_ENV)
    if raw is None:
        return ()
    try:
        loaded: JsonValue = json.loads(raw)
    except json.JSONDecodeError as error:
        raise FvpConfigError("FVP config must be a JSON object") from error
    data = _mapping(loaded, "root")
    selected: list[tuple[str, str]] = []
    for key, value in data.items():
        expected_value = APPROVED_FVP_CONFIG.get(key)
        if expected_value is None:
            raise FvpConfigError(f"unknown FVP config key: {key}")
        if not isinstance(value, str):
            raise FvpConfigError(f"FVP config value for {key} must be a string")
        if value != expected_value:
            raise FvpConfigError(f"unsafe FVP config value for {key}")
        selected.append((key, value))
    if not selected:
        raise FvpConfigError("FVP config must not be empty")
    return tuple(selected)


def _config_path(source: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else source.parent / path


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prepare_runtime_config(request: RuntimeConfigRequest) -> Path:
    source_hash = _sha256(request.source)
    loaded: JsonValue = json.loads(request.source.read_text(encoding="utf-8"))
    config = _mapping(loaded, "root")
    parameters = _mapping(config.get("parameters"), "parameters")
    selected = _selected_config()
    writable_dir = request.bootlog.parent / "profile-runtime" if selected else None

    for read_key, write_key in WRITABLE_FLASH_PAIRS:
        read_image = parameters.get(read_key)
        write_image = parameters.get(write_key)
        if not isinstance(read_image, str) or not isinstance(write_image, str):
            continue
        read_path = _config_path(request.source, read_image)
        write_path = _config_path(request.source, write_image)
        if writable_dir is not None or read_path == write_path:
            writable_dir = writable_dir or request.source.parent / "hsoc-oeqa-writable"
            write_path = writable_dir / read_path.name
        write_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(read_path, write_path)
        parameters[write_key] = str(write_path)
        writable_dir = write_path.parent
        request.logger.debug("Reset writable FVP flash %s from %s", write_path, read_path)

    for key in WRITABLE_IMAGE_KEYS:
        image = parameters.get(key)
        if not isinstance(image, str) or not image:
            continue
        read_path = _config_path(request.source, image)
        writable_dir = writable_dir or request.source.parent / "hsoc-oeqa-writable"
        write_path = writable_dir / read_path.name
        write_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(read_path, write_path)
        parameters[key] = str(write_path)
        request.logger.debug("Reset writable FVP image %s from %s", write_path, read_path)

    for key, value in selected:
        parameters[key] = value
    if writable_dir is None:
        return request.source
    runtime = writable_dir / f"{request.source.stem}.hsoc-oeqa.fvpconf"
    runtime.write_text(json.dumps(config), encoding="utf-8")
    if selected:
        receipt = {
            "source": str(request.source),
            "source_sha256": source_hash,
            "source_after_sha256": _sha256(request.source),
            "runtime": str(runtime),
            "runtime_sha256": _sha256(runtime),
            "applied_fvp_config": dict(selected),
        }
        (writable_dir / "fvp-config-application.json").write_text(
            json.dumps(receipt, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    return runtime
