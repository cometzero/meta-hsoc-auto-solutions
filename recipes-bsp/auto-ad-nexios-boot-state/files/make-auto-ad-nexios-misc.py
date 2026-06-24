#!/usr/bin/env python3
# SPDX-License-Identifier: MIT

import argparse
import binascii
import struct
import sys
from pathlib import Path


MAGIC = b"AANXBOOT"
VERSION = 1
HEADER_SIZE = 64
BLOB_SIZE = 4 * 1024 * 1024
CRC_OFFSET = 0x18
CRC_SIZE = 4
RESERVED_OFFSET = 0x1C
DEFAULT_ATTEMPTS = 3

FLAG_ROLLBACK_PENDING = 1 << 0
FLAG_SLOT_SUCCESSFUL = 1 << 1
DEFAULT_FLAGS = FLAG_SLOT_SUCCESSFUL


class MiscError(ValueError):
    pass


def slot_to_value(slot):
    normalized = slot.upper()
    if normalized == "A":
        return 0
    if normalized == "B":
        return 1
    raise MiscError(f"invalid slot {slot!r}: expected A or B")


def slot_to_name(slot):
    if slot == 0:
        return "A"
    if slot == 1:
        return "B"
    raise MiscError(f"invalid slot value {slot}: expected 0 or 1")


def _check_u8(name, value):
    if value < 0 or value > 0xFF:
        raise MiscError(f"{name} out of range: expected 0..255, got {value}")


def _check_u16(name, value):
    if value < 0 or value > 0xFFFF:
        raise MiscError(f"{name} out of range: expected 0..65535, got {value}")


def _check_u32(name, value):
    if value < 0 or value > 0xFFFFFFFF:
        raise MiscError(f"{name} out of range: expected 0..4294967295, got {value}")


def crc32_header(blob):
    crc_input = bytearray(blob[:RESERVED_OFFSET])
    crc_input[CRC_OFFSET:CRC_OFFSET + CRC_SIZE] = b"\x00" * CRC_SIZE
    return binascii.crc32(crc_input[:CRC_OFFSET]) & 0xFFFFFFFF


def build_blob(slot="A", attempts=DEFAULT_ATTEMPTS, flags=DEFAULT_FLAGS,
               generation=0):
    slot_value = slot_to_value(slot)
    _check_u8("attempts", attempts)
    _check_u16("flags", flags)
    _check_u32("generation", generation)

    blob = bytearray(BLOB_SIZE)
    struct.pack_into(
        "<8sIIBBHI",
        blob,
        0,
        MAGIC,
        VERSION,
        HEADER_SIZE,
        slot_value,
        attempts,
        flags,
        generation,
    )
    struct.pack_into("<I", blob, CRC_OFFSET, crc32_header(blob))
    return bytes(blob)


def parse_blob(blob):
    if len(blob) != BLOB_SIZE:
        raise MiscError(
            f"blob size mismatch: expected {BLOB_SIZE} bytes, got {len(blob)}"
        )

    magic, version, header_size, slot, attempts, flags, generation = (
        struct.unpack_from("<8sIIBBHI", blob, 0)
    )
    crc_stored, = struct.unpack_from("<I", blob, CRC_OFFSET)
    crc_expected = crc32_header(blob)

    if magic != MAGIC:
        raise MiscError(
            f"invalid magic: expected {MAGIC.decode('ascii')}, got "
            f"{magic!r}"
        )
    if version != VERSION:
        raise MiscError(
            f"unsupported version: expected {VERSION}, got {version}"
        )
    if header_size != HEADER_SIZE:
        raise MiscError(
            f"unsupported header size: expected {HEADER_SIZE}, got "
            f"{header_size}"
        )
    if slot not in (0, 1):
        raise MiscError(f"invalid slot: expected 0 or 1, got {slot}")
    if crc_stored != crc_expected:
        raise MiscError(
            "CRC mismatch: expected "
            f"0x{crc_expected:08x}, got 0x{crc_stored:08x}"
        )
    if any(blob[RESERVED_OFFSET:]):
        raise MiscError("reserved area is not zero-filled")

    return {
        "magic": magic.decode("ascii"),
        "version": version,
        "header_size": header_size,
        "slot": slot_to_name(slot),
        "attempts": attempts,
        "flags": flags,
        "rollback_pending": bool(flags & FLAG_ROLLBACK_PENDING),
        "slot_successful": bool(flags & FLAG_SLOT_SUCCESSFUL),
        "generation": generation,
        "crc32": crc_stored,
    }


def _format_info(info):
    return (
        "valid: "
        f"slot={info['slot']} "
        f"attempts={info['attempts']} "
        f"flags=0x{info['flags']:04x} "
        f"rollback_pending={int(info['rollback_pending'])} "
        f"slot_successful={int(info['slot_successful'])} "
        f"generation={info['generation']} "
        f"crc32=0x{info['crc32']:08x}"
    )


def validate_file(path):
    blob = Path(path).read_bytes()
    return parse_blob(blob)


def write_blob(path, slot):
    blob = build_blob(slot=slot)
    Path(path).write_bytes(blob)
    return blob


def parse_args(argv):
    parser = argparse.ArgumentParser(
        description="Generate or validate an auto-ad-nexios misc boot blob."
    )
    parser.add_argument(
        "--slot",
        choices=("A", "B", "a", "b"),
        default="A",
        help="slot to encode when generating a blob",
    )
    parser.add_argument("--out", help="write a generated blob to this path")
    parser.add_argument(
        "--validate",
        metavar="PATH",
        help="validate an existing blob instead of generating one",
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="validate the generated output before exiting",
    )
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv if argv is not None else sys.argv[1:])

    try:
        if args.validate:
            if args.out:
                raise MiscError("--out cannot be used with --validate")
            info = validate_file(args.validate)
            print(_format_info(info))
            return 0

        if not args.out:
            raise MiscError("either --out or --validate is required")

        blob = write_blob(args.out, args.slot)
        if args.verify:
            info = parse_blob(blob)
            print(_format_info(info))
        return 0
    except (OSError, MiscError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
