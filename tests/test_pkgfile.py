import pytest

from symport.theme import pkgfile, uids
from tests.helpers import REPO


def test_real_dist_pkgs_parse():
    for v, real in (("light", "e52clearlight"), ("dark", "e52cleardark")):
        p = pkgfile.parse((REPO / "theme" / "dist" / v / f"{real}.pkg").read_text())
        assert p.uid is not None and uids.classify(p.uid) == "test"
        assert 0x101F7961 in p.platform_deps
        assert {0xA00000EB, 0x10207113} <= set(p.package_deps)
        uid = f"{p.uid:08x}"
        dests = {e.dest.lower() for e in p.files}
        assert f"!:\\resource\\skins\\{uid}\\{real}.mbm" in dests
        assert f"!:\\resource\\skins\\{uid}\\{real}.mif" in dests
        assert f"!:\\private\\10207114\\import\\{uid}\\{real}.skn" in dests


def test_parse_syntax():
    p = pkgfile.parse('; c\n&EN\n#{"N"},(0x1),1,2,3\n[0x101f7961], 0,0,0,{"S60"}\n(0xA1), 0,0,0,{"d"}\n:"V"\n'
                      '"a.x" - "!:\\p\\a.x"\n"" - "!:\\p\\b.ini",FN\n')
    assert p.name == "N" and p.version == (1, 2, 3) and p.uid == 1
    assert p.files[1].options == "FN" and p.vendor == "V" and p.package_deps == [0xA1]


@pytest.mark.parametrize("text", ["", '#{"N"}\n', '#{"N"},(0x1),1,0,0\n"broken line\n',
                                  '#{"N"},(0x1),1,0,0\n[zz]\n'])
def test_malformed_pkg(text):
    with pytest.raises(pkgfile.PkgError):
        pkgfile.parse(text)


def test_uid_classification_and_collisions():
    assert uids.classify(0xE0E52C01) == "test" and uids.classify(0x2000B12D) == "protected"
    assert uids.classify(0xA0001234) == "unprotected"
    assert "collides" in uids.collision_note(0x2000B12D)
    assert "Symbian Signed" in uids.collision_note(0x20001234)
