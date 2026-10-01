from pathlib import Path


def test_managed_block_fixtures_cover_required_byte_shapes(fixtures_dir: Path):
    cases = {p.name for p in (fixtures_dir / "managed-block").iterdir()}
    assert cases == {
        "plain-lf.md", "plain-crlf.md", "no-final-newline.md", "utf8-bom.md",
        "existing-valid.md", "duplicate.md", "broken-start.md", "similar-unmanaged.md",
    }
    assert (fixtures_dir / "managed-block/plain-crlf.md").read_bytes().count(b"\r\n") >= 1
    assert (fixtures_dir / "managed-block/utf8-bom.md").read_bytes().startswith(b"\xef\xbb\xbf")
    assert not (fixtures_dir / "managed-block/no-final-newline.md").read_bytes().endswith((b"\n", b"\r"))
