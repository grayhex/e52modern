import pytest

from symport.sis import fields, reader, writer
from symport.sis.fields import SisFormatError


def pkg(**kw):
    files = kw.pop("files", [writer.SisFile("!:\\resource\\skins\\e0e52c01\\a.mbm", b"hello world"),
                             writer.SisFile("!:\\private\\10207114\\import\\e0e52c01\\a.skn", b"x" * 1001)])
    return writer.SisPackage(kw.pop("uid", 0xE0E52C01), kw.pop("name", "Test"), kw.pop("vendor", "v"),
                             kw.pop("version", (1, 0, 0)), files)


def test_roundtrip_and_hashes():
    data = writer.build(pkg())
    info = reader.inspect(data)
    assert info["uid_checksum_ok"] and info["controller_crc_ok"] and info["data_crc_ok"]
    assert info["package"]["uid"] == 0xE0E52C01 == info["uid3"]
    assert [f["target"] for f in info["files"]] == [
        "!:\\resource\\skins\\e0e52c01\\a.mbm", "!:\\private\\10207114\\import\\e0e52c01\\a.skn"]
    assert all(f["hash_ok"] for f in info["files"])
    assert info["signed"] is False


def test_deterministic():
    assert writer.build(pkg()) == writer.build(pkg())


def test_extract_returns_file_bytes():
    blobs = reader.extract(writer.build(pkg()))
    assert blobs["!:\\resource\\skins\\e0e52c01\\a.mbm"] == b"hello world"


def test_known_crc_vectors():
    # CRC-16/XMODEM check value
    assert fields.crc16(b"123456789") == 0x31C3


@pytest.mark.parametrize("bad", [
    dict(files=[]),
    dict(name=""),
    dict(name="x" * 200),
    dict(version=(1, 0, 99999)),
    dict(files=[writer.SisFile("relative\\path", b"x")]),
    dict(files=[writer.SisFile("!:\\a\\..\\b", b"x")]),
    dict(files=[writer.SisFile("!:\\a\\x", b"1"), writer.SisFile("!:\\A\\X", b"2")]),
])
def test_writer_rejects_invalid(bad):
    with pytest.raises(SisFormatError):
        writer.build(pkg(**bad))


def test_reader_detects_bit_flip_in_payload():
    data = bytearray(writer.build(pkg()))
    data[-5] ^= 0xFF           # inside the data section
    info = reader.inspect(bytes(data))
    assert info["data_crc_ok"] is False


def test_reader_detects_controller_corruption():
    data = bytearray(writer.build(pkg()))
    data[100] ^= 0x55          # inside the controller
    try:
        info = reader.inspect(bytes(data))
    except SisFormatError:
        return
    assert info["controller_crc_ok"] is False


@pytest.mark.parametrize("n", [0, 3, 15, 16, 40, 200])
def test_truncated_files_raise(n):
    data = writer.build(pkg())
    with pytest.raises(SisFormatError):
        reader.inspect(data[:n])


def test_wrong_magic():
    with pytest.raises(SisFormatError):
        reader.inspect(b"\x00" * 64)


def test_uid_header_checksum_mismatch_reported():
    data = bytearray(writer.build(pkg()))
    data[8] ^= 1               # change UID3 without fixing the checksum
    assert reader.inspect(bytes(data))["uid_checksum_ok"] is False
