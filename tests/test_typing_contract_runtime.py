"""Runtime behavior underlying the public type annotations."""

import os

import pytest

from snakemd import CSVTable, Checklist, Code, Document, Inline, MDList, Paragraph, Table


def test_inline_link_can_be_absent():
    inline = Inline("text")
    assert inline.get_link() is None
    assert inline.link("https://example.com").get_link() == "https://example.com"
    assert inline.unlink().get_link() is None


def test_optional_document_and_table_arguments():
    assert Document(None).get_elements() == []
    assert str(Table(["header"], body=None, align=None))
    assert Document().add_table(["header"], [["cell"]], align=None)


def test_csv_paths_accept_strings_and_path_objects(tmp_path):
    path = tmp_path / "sample.csv"
    path.write_text("header\ncell\n", encoding="utf-8")

    class BytesPath(os.PathLike[bytes]):
        def __fspath__(self) -> bytes:
            return os.fsencode(path)

    for value in (path, str(path), os.fsencode(path), BytesPath()):
        assert "cell" in str(CSVTable(value))
        assert "cell" in str(Document().add_table_from_csv(value))


def test_table_add_row_requires_sized_iterable():
    table = Table(["header"])
    table.add_row(("cell",))
    assert "cell" in str(table)
    with pytest.raises(TypeError):
        table.add_row(iter(["cell"]))


def test_dump_directory_accepts_string_and_path(tmp_path):
    doc = Document()
    doc.add_raw("text")
    doc.dump("path", directory=tmp_path)
    doc.dump("string", directory=str(tmp_path))
    assert (tmp_path / "path.md").read_text(encoding="utf-8") == "text"
    assert (tmp_path / "string.md").read_text(encoding="utf-8") == "text"


def test_other_annotated_public_methods():
    assert Code("body") == Code("body")
    assert Code("body") != object()
    assert str(Paragraph("body")) == "body"
    assert str(Checklist(["body"])) == "- [ ] body"
    assert str(MDList(["body"], checked=None)) == "- body"
