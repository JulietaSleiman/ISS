from pathlib import Path
import tempfile
import unittest

from scripts.check_release_version import read_version, validate_tag


class ReleaseVersionTests(unittest.TestCase):
    def test_version_can_be_read_without_importing_application_dependencies(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as directory:
            source = Path(directory) / 'updater.py'
            source.write_text('import nonexistent_runtime_dependency\nCURRENT_VERSION = "1.1.0"\n', encoding='utf-8')
            self.assertEqual(read_version(source), '1.1.0')

    def test_invalid_or_mismatched_tags_are_rejected(self):
        for tag in ('v1.0.5', '1.1.0', 'v01.1.0', 'v1.1.0\nEVIL=1', 'v1.1.0$(anything)'):
            with self.subTest(tag=tag), self.assertRaises(ValueError):
                validate_tag(tag, '1.1.0')
        validate_tag('v1.1.0', '1.1.0')

    def test_duplicate_or_computed_versions_are_rejected(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as directory:
            source = Path(directory) / 'updater.py'
            for content in ('CURRENT_VERSION = "1.1.0"\nCURRENT_VERSION = "1.2.0"', 'CURRENT_VERSION = get_version()'):
                source.write_text(content, encoding='utf-8')
                with self.subTest(content=content), self.assertRaises(ValueError):
                    read_version(source)

    def test_repository_version_matches_prepared_release(self):
        version = read_version(Path(__file__).resolve().parents[1] / 'src/core/updater.py')
        validate_tag('v1.1.0', version)


if __name__ == '__main__':
    unittest.main()
