"""A consumer checked against the installed wheel, outside the source tree."""

import os
from pathlib import Path

from snakemd import Document, Inline, MDList, Paragraph, Table, new_doc
from snakemd.templates import CSVTable


def use_api(csv: Path, output: Path) -> None:
    class BytesPath(os.PathLike[bytes]):
        def __fspath__(self) -> bytes:
            return os.fsencode(csv)

    doc: Document = new_doc()
    Document(None)
    inline = Inline("hello", image=None, link=None)
    link: str | None = inline.get_link()
    inline.link("https://example.com").unlink().bold()
    paragraph: Paragraph = Paragraph(["hello", inline]).add(" world")
    doc.add_block(paragraph)
    doc.add_ordered_list(["one", "two"])
    MDList(["one"], checked=None)
    doc.add_table(["head"], [["cell"]], align=None)
    table = Table(["head"], body=None, align=None)
    table.add_row(["list"])
    table.add_row(("tuple",))
    doc.add_table_from_csv(csv)
    doc.add_table_from_csv(str(csv))
    CSVTable(csv)
    CSVTable(str(csv))
    doc.add_table_from_csv(os.fsencode(csv))
    doc.add_table_from_csv(BytesPath())
    CSVTable(os.fsencode(csv))
    CSVTable(BytesPath())
    doc.dump("example", directory=output)
    _ = link
