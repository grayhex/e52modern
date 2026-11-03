import pytest

from symport.analysis import compat, e32
from symport.devices import profiles
from symport.report import Report
from tests.helpers import REPO, make_e32


@pytest.fixture
def e52():
    return profiles.load_profile(REPO / "profiles" / "nokia-e52.toml")


def verdict(data, e52, fw=None):
    rep = Report("t")
    v = compat.evaluate(e32.analyze(data), e52, fw, rep)
    return v, rep


def test_parse_header_fields():
    info = e32.analyze(make_e32(uid3=0xE0ABCDEF, caps_low=(1 << 13) | (1 << 11)))
    assert info["uid3"] == 0xE0ABCDEF and info["uid_checksum_ok"] and info["header_crc_ok"]
    assert info["kernel"] == "eka2" and info["abi"] == "eabi" and info["cpu"] == "armv5"
    assert info["header_format"] == "V" and info["import_format"] == "elf" and not info["is_dll"]
    assert info["capabilities"] == ["AllFiles", "NetworkServices"]
    assert info["restricted_capabilities"] == ["AllFiles"]


def test_imports_decoded_including_ordinals():
    data = make_e32(imports={"euser{000a0000}[100039e5].dll": [1, 2, 300], "avkon{000a0000}[10003a02].dll": [7]})
    info = e32.analyze(data)
    got = {i["name"]: i["ordinals"] for i in info["imports"]}
    assert got == {"euser.dll": [1, 2, 300], "avkon.dll": [7]}
    assert info["imports"][0]["uid"] == "0x100039e5"


def test_not_e32_and_truncated():
    with pytest.raises(e32.E32Error):
        e32.analyze(b"\x00" * 200)
    with pytest.raises(e32.E32Error):
        e32.analyze(b"X" * 16 + b"EPOC" + b"\x00" * 20)


def test_header_crc_mismatch_is_incompatible(e52):
    v, rep = verdict(make_e32(corrupt_crc=True), e52)
    assert v == "incompatible"
    assert any(c.id == "e32.header_crc" and c.status == "fail" for c in rep.checks)


def test_compressed_image_reports_headers_only(e52):
    info = e32.analyze(make_e32(compression=0x101F7AFC))
    assert info["compression"] == "deflate" and info["imports"] is None and "compressed" in info["imports_note"]


def test_without_firmware_imports_are_unknown_not_compatible(e52):
    v, rep = verdict(make_e32(imports={"euser[100039e5].dll": [1]}), e52)
    assert v == "unknown"
    imp = next(c for c in rep.checks if c.id == "e32.imports")
    assert imp.status == "unknown" and imp.level == "firmware"
    assert rep.data["compatibility"]["runtime"] == "not-tested"


def test_no_imports_is_statically_compatible_but_runtime_untested(e52):
    v, rep = verdict(make_e32(), e52)
    assert v == "compatible"
    assert any(c.id == "compat.runtime" and c.status == "unknown" for c in rep.checks)


def fw(dlls):
    return compat.FirmwareProfile("fw", "nokia-e52", "x", "unit-test fixture", dlls)


def test_firmware_profile_resolves_imports(e52):
    data = make_e32(imports={"euser[100039e5].dll": [1, 2]})
    assert verdict(data, e52, fw({"euser.dll": {1, 2, 3}}))[0] == "compatible"
    v, rep = verdict(data, e52, fw({"euser.dll": {1}}))
    assert v == "incompatible"          # ordinal 2 missing
    v, rep = verdict(data, e52, fw({"avkon.dll": None}))
    assert v == "incompatible"          # euser.dll absent
    v, _ = verdict(data, e52, fw({"euser.dll": None}))
    assert v == "compatible"            # DLL present, ordinal table not available -> warn only


def test_wrong_cpu_and_kernel(e52):
    assert verdict(make_e32(cpu=0x2002), e52)[0] == "incompatible"   # ARMv6 vs ARMv5 profile
    assert verdict(make_e32(cpu=0x1000), e52)[0] == "incompatible"   # x86
    assert verdict(make_e32(kernel_eka2=False), e52)[0] == "incompatible"


def test_restricted_capability_is_warned_not_hidden(e52):
    v, rep = verdict(make_e32(caps_low=1 << 11), e52)
    c = next(c for c in rep.checks if c.id == "e32.capabilities")
    assert c.status == "warn" and "AllFiles" in c.message


def test_firmware_profile_loading(tmp_path):
    p = tmp_path / "fw.json"
    p.write_text('{"schema":1,"id":"a","device":"nokia-e52","source":"my dump","dlls":{"EUser.dll":{"ordinals":[1,2]},"x.dll":{}}}')
    f = compat.load_firmware_profile(p)
    assert f.dlls == {"euser.dll": {1, 2}, "x.dll": None}
    p.write_text('{"schema":2}')
    with pytest.raises(compat.FirmwareProfileError):
        compat.load_firmware_profile(p)
