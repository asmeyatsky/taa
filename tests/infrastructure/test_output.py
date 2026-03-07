"""Tests for filesystem output writer."""

import tempfile
from pathlib import Path

from taa.infrastructure.output.filesystem_writer import FilesystemWriter


class TestFilesystemWriter:
    def setup_method(self):
        self.writer = FilesystemWriter()

    def test_write_creates_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "subdir" / "test.sql"
            self.writer.write(path, "CREATE TABLE test;")
            assert path.exists()
            assert path.read_text() == "CREATE TABLE test;"

    def test_write_creates_parent_dirs(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "a" / "b" / "c" / "test.sql"
            self.writer.write(path, "content")
            assert path.exists()

    def test_write_multiple(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            files = {
                "main.tf": "terraform {}",
                "variables.tf": 'variable "x" {}',
            }
            written = self.writer.write_multiple(files, Path(tmpdir))
            assert len(written) == 2
            for p in written:
                assert p.exists()
