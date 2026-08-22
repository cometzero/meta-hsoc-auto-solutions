from __future__ import annotations

import errno
import os
from pathlib import Path
import shutil
import tempfile
from typing import Final, IO


COPY_BUFFER_SIZE: Final = 1024 * 1024
SPARSE_BLOCK_SIZE: Final = 4096
SPARSE_UNSUPPORTED_ERRNOS: Final = frozenset(
    {
        errno.EINVAL,
        errno.ENOSYS,
        errno.ENOTSUP,
        errno.EOPNOTSUPP,
    }
)


def _write_all(target: IO[bytes], data: bytes) -> None:
    remaining = memoryview(data)
    while remaining:
        written = target.write(remaining)
        if written is None or written <= 0:
            raise OSError(errno.EIO, "short write while copying FVP image")
        remaining = remaining[written:]


def _copy_extent(
    source: IO[bytes],
    target: IO[bytes],
    start: int,
    end: int,
) -> None:
    source.seek(start)
    target.seek(start)
    remaining = end - start
    while remaining:
        chunk = source.read(min(COPY_BUFFER_SIZE, remaining))
        if not chunk:
            raise OSError(errno.EIO, "short read while copying FVP image")
        _write_all(target, chunk)
        remaining -= len(chunk)


def _copy_sparse_extents(
    source: IO[bytes],
    target: IO[bytes],
    size: int,
) -> None:
    offset = 0
    while offset < size:
        try:
            data_offset = os.lseek(source.fileno(), offset, os.SEEK_DATA)
        except OSError as error:
            if error.errno == errno.ENXIO:
                break
            raise
        hole_offset = os.lseek(source.fileno(), data_offset, os.SEEK_HOLE)
        extent_end = min(hole_offset, size)
        if extent_end <= data_offset:
            raise OSError(errno.EIO, "invalid sparse extent in FVP image")
        _copy_extent(source, target, data_offset, extent_end)
        offset = extent_end


def _copy_sparse_by_content(
    source: IO[bytes],
    target: IO[bytes],
    size: int,
) -> None:
    source.seek(0)
    target.seek(0)
    target.truncate(0)
    offset = 0
    while chunk := source.read(COPY_BUFFER_SIZE):
        if any(chunk):
            for block_offset in range(0, len(chunk), SPARSE_BLOCK_SIZE):
                block = chunk[block_offset : block_offset + SPARSE_BLOCK_SIZE]
                if any(block):
                    target.seek(offset + block_offset)
                    _write_all(target, block)
        offset += len(chunk)
    if offset != size:
        raise OSError(errno.EIO, "short read while scanning sparse FVP image")


def _copy_sparse_data(
    source: IO[bytes],
    target: IO[bytes],
    size: int,
) -> None:
    try:
        _copy_sparse_extents(source, target, size)
    except OSError as error:
        if error.errno not in SPARSE_UNSUPPORTED_ERRNOS:
            raise
        _copy_sparse_by_content(source, target, size)
    target.truncate(size)


def copy_runtime_file(source: Path, destination: Path) -> None:
    source_path = source.resolve(strict=True)
    if destination.exists() and source_path == destination.resolve(strict=True):
        raise shutil.SameFileError(source, destination, "same file")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.unlink(missing_ok=True)
    temporary_path: Path | None = None
    complete = False
    try:
        with tempfile.NamedTemporaryFile(
            mode="w+b",
            prefix=f".{destination.name}.",
            suffix=".tmp",
            dir=destination.parent,
            delete=False,
        ) as target:
            temporary_path = Path(target.name)
            with source_path.open("rb", buffering=0) as source_file:
                _copy_sparse_data(
                    source_file,
                    target.file,
                    source_path.stat().st_size,
                )
            target.flush()
            os.fsync(target.fileno())
        shutil.copystat(source_path, temporary_path)
        os.replace(temporary_path, destination)
        complete = True
    finally:
        if not complete:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)
            destination.unlink(missing_ok=True)
