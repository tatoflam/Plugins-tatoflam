import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import vault_paths as vp  # noqa: E402


def touch(root, rel):
    p = os.path.join(root, rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    open(p, "w").close()


class FlatVault(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        touch(self.d, "03_work/meguru-crm.md")
        touch(self.d, "05_learn/claude-code-hooks.md")

    def test_flat_page_resolves_to_itself(self):
        self.assertEqual(vp.resolve("03_work/meguru-crm", self.d), "03_work/meguru-crm")

    def test_missing_page(self):
        self.assertIsNone(vp.resolve("03_work/nope", self.d))

    def test_other_category(self):
        self.assertEqual(vp.resolve("05_learn/claude-code-hooks.md", self.d), "05_learn/claude-code-hooks")

    def test_next_number_empty(self):
        self.assertEqual(vp.next_number("03_work", self.d), "001")


class FolderVault(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        touch(self.d, "03_work/001_habi-bff/habi-bff.md")
        touch(self.d, "03_work/012_meguru-crm/meguru-crm.md")
        touch(self.d, "03_work/035_sorato-sayama/sorato-sayama.md")
        touch(self.d, "03_work/035_sorato-sayama/sayama-land-contract.md")

    def test_old_path_resolves_to_main(self):
        self.assertEqual(vp.resolve("03_work/meguru-crm", self.d), "03_work/012_meguru-crm/meguru-crm")

    def test_heading_and_alias_are_ignored(self):
        self.assertEqual(vp.resolve("03_work/meguru-crm#経緯|CRM", self.d), "03_work/012_meguru-crm/meguru-crm")

    def test_folder_path(self):
        self.assertEqual(vp.resolve("03_work/012_meguru-crm", self.d), "03_work/012_meguru-crm/meguru-crm")
        self.assertEqual(vp.resolve("03_work/012_meguru-crm/meguru-crm", self.d), "03_work/012_meguru-crm/meguru-crm")

    def test_old_flat_subpage(self):
        # moved across categories: 04_life/sayama-land-contract now lives in a 03_work folder
        self.assertEqual(vp.resolve("04_life/sayama-land-contract", self.d),
                         "03_work/035_sorato-sayama/sayama-land-contract")
        self.assertEqual(vp.resolve("03_work/sayama-land-contract", self.d),
                         "03_work/035_sorato-sayama/sayama-land-contract")

    def test_missing_project(self):
        self.assertIsNone(vp.resolve("03_work/new-project", self.d))

    def test_next_number_does_not_fill_gaps(self):
        self.assertEqual(vp.next_number("03_work", self.d), "036")
        self.assertEqual(vp.next_number("04_life", self.d), "001")


if __name__ == "__main__":
    unittest.main()
