"""Tests — services.embeddable_python (activation site-packages sur embeddable)."""
import os

from services.embeddable_python import enable_site_packages, is_site_enabled


def _make_python_dir(tmp_path, pth_content: str | None, pth_name: str = "python312._pth"):
    python_dir = tmp_path / "python_dir"
    python_dir.mkdir()
    python_exe = python_dir / "python.exe"
    python_exe.write_text("")  # fichier bidon, seul le chemin compte
    if pth_content is not None:
        (python_dir / pth_name).write_text(pth_content)
    return str(python_exe)


class TestIsSiteEnabled:
    def test_no_pth_file_means_not_embeddable_so_enabled(self, tmp_path):
        python_exe = _make_python_dir(tmp_path, pth_content=None)
        assert is_site_enabled(python_exe) is True

    def test_site_commented_out_is_disabled(self, tmp_path):
        content = "python312.zip\n.\n\n# Uncomment to run site.main() automatically\n#import site\n"
        python_exe = _make_python_dir(tmp_path, content)
        assert is_site_enabled(python_exe) is False

    def test_site_uncommented_is_enabled(self, tmp_path):
        content = "python312.zip\n.\n\nimport site\n"
        python_exe = _make_python_dir(tmp_path, content)
        assert is_site_enabled(python_exe) is True


class TestEnableSitePackages:
    def test_no_pth_file_is_noop_success(self, tmp_path):
        python_exe = _make_python_dir(tmp_path, pth_content=None)
        assert enable_site_packages(python_exe) is True

    def test_already_enabled_is_noop_success(self, tmp_path):
        content = "python312.zip\n.\n\nimport site\n"
        python_exe = _make_python_dir(tmp_path, content)
        assert enable_site_packages(python_exe) is True
        pth_path = os.path.join(os.path.dirname(python_exe), "python312._pth")
        with open(pth_path, encoding="utf-8") as fh:
            assert fh.read() == content

    def test_commented_line_gets_uncommented(self, tmp_path):
        content = "python312.zip\n.\n\n# Uncomment to run site.main()\n#import site\n"
        python_exe = _make_python_dir(tmp_path, content)

        assert enable_site_packages(python_exe) is True

        pth_path = os.path.join(os.path.dirname(python_exe), "python312._pth")
        with open(pth_path, encoding="utf-8") as fh:
            new_content = fh.read()
        assert is_site_enabled(python_exe) is True
        assert "import site" in new_content
        assert "#import site" not in new_content

    def test_missing_site_line_entirely_gets_appended(self, tmp_path):
        content = "python312.zip\n.\n"
        python_exe = _make_python_dir(tmp_path, content)

        assert enable_site_packages(python_exe) is True
        assert is_site_enabled(python_exe) is True
