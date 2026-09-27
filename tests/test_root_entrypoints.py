from __future__ import annotations

import runpy
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import Mock, patch


ROOT_DIR = Path(__file__).resolve().parents[1]


class TestRootEntrypoints(unittest.TestCase):
    def _assert_entrypoint(self, script_name: str, imported_module: str, exit_code: int) -> None:
        script_path = ROOT_DIR / script_name
        fake_main = Mock(return_value=exit_code)
        package_name, child_name = imported_module.split(".", maxsplit=1)

        fake_package = types.ModuleType(package_name)
        fake_package.__path__ = []  # type: ignore[attr-defined]
        fake_submodule = types.ModuleType(imported_module)
        fake_submodule.main = fake_main
        setattr(fake_package, child_name, fake_submodule)

        with patch.dict(
            sys.modules,
            {package_name: fake_package, imported_module: fake_submodule},
            clear=False,
        ):
            with self.assertRaises(SystemExit) as context:
                runpy.run_path(str(script_path), run_name="__main__")

        self.assertEqual(context.exception.code, exit_code)
        fake_main.assert_called_once_with()

    def test_instagram_nonfollowers_entrypoint(self) -> None:
        self._assert_entrypoint(
            script_name="instagram_nonfollowers.py",
            imported_module="instagram_nonfollowers.cli",
            exit_code=0,
        )

    def test_instagram_filter_famous_entrypoint(self) -> None:
        self._assert_entrypoint(
            script_name="instagram_filter_famous.py",
            imported_module="instagram_nonfollowers.profile_filter",
            exit_code=3,
        )

    def test_instagram_unfollow_selected_entrypoint(self) -> None:
        self._assert_entrypoint(
            script_name="instagram_unfollow_selected.py",
            imported_module="instagram_nonfollowers.unfollower",
            exit_code=7,
        )


if __name__ == "__main__":
    unittest.main()
