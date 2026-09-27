from __future__ import annotations

import json
import sys
import tempfile
import types
import unittest
from argparse import Namespace
from pathlib import Path
from unittest.mock import Mock, patch


def _install_fake_playwright() -> None:
    if "playwright.sync_api" in sys.modules:
        return

    playwright_module = types.ModuleType("playwright")
    sync_api_module = types.ModuleType("playwright.sync_api")

    class FakePlaywrightError(Exception):
        pass

    class FakePlaywrightTimeoutError(Exception):
        pass

    def _placeholder_sync_playwright():
        raise AssertionError("sync_playwright deve ser mockado nos testes.")

    sync_api_module.Error = FakePlaywrightError
    sync_api_module.TimeoutError = FakePlaywrightTimeoutError
    sync_api_module.sync_playwright = _placeholder_sync_playwright
    playwright_module.sync_api = sync_api_module

    sys.modules["playwright"] = playwright_module
    sys.modules["playwright.sync_api"] = sync_api_module


class FakeSyncPlaywright:
    def __init__(self, value: object = "playwright"):
        self.value = value

    def __enter__(self):
        return self.value

    def __exit__(self, exc_type, exc, tb):
        return False


class FakeContext:
    def __init__(self, page: object | None = None, with_existing_page: bool = True):
        self._page = page if page is not None else Mock(name="page")
        self.pages = [self._page] if with_existing_page else []
        self.close = Mock(name="close")

    def new_page(self):
        return self._page


def _write_json_file(payload: object) -> Path:
    handle = tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", suffix=".json", delete=False)
    with handle:
        json.dump(payload, handle, ensure_ascii=False)
    return Path(handle.name)


_install_fake_playwright()
from instagram_nonfollowers import cli, collector, profile_filter, unfollower  # noqa: E402


class TestCollectorContract(unittest.TestCase):
    def test_build_payload_follows_readme_contract(self) -> None:
        payload = collector.build_payload(
            followers={"ana", "caio"},
            following={"ana", "caio", "bia"},
            expected_followers=2,
            expected_following=3,
        )

        self.assertEqual(payload["total_seguidores"], 2)
        self.assertEqual(payload["total_seguindo"], 3)
        self.assertEqual(payload["total_nao_seguidores"], 1)
        self.assertEqual(payload["nao_seguidores"], [{"insta": "@bia", "link": "https://www.instagram.com/bia"}])
        self.assertIn("validacao", payload)
        self.assertTrue(payload["validacao"]["bate_seguidores"])
        self.assertTrue(payload["validacao"]["bate_seguindo"])


class TestCliMainComponent(unittest.TestCase):
    def _args(self, **overrides) -> Namespace:
        base = dict(
            username="perfilmock",
            user_data_dir=r"C:\perfil",
            output="nao_seguidores.json",
            min_delay=1.0,
            max_delay=2.0,
            headless=True,
        )
        base.update(overrides)
        return Namespace(**base)

    def test_main_success_generates_payload(self) -> None:
        args = self._args()
        page = Mock(name="page")
        context = FakeContext(page=page)
        payload = {"total_nao_seguidores": 1, "total_seguidores": 2, "total_seguindo": 3}

        with (
            patch.object(cli, "parse_args", return_value=args),
            patch.object(cli, "sync_playwright", return_value=FakeSyncPlaywright("pw")),
            patch.object(cli, "launch_context", return_value=context),
            patch.object(cli, "open_profile"),
            patch.object(cli, "get_profile_counts", return_value={"seguidores": 2, "seguindo": 3}),
            patch.object(cli, "capture_modal", side_effect=[{"ana", "bia"}, {"ana", "bia", "joao"}]) as capture_modal,
            patch.object(cli, "build_payload", return_value=payload),
            patch.object(cli, "save_payload") as save_payload,
        ):
            result = cli.main()

        self.assertEqual(result, 0)
        self.assertEqual(capture_modal.call_count, 2)
        save_payload.assert_called_once()
        self.assertEqual(save_payload.call_args[0][1], payload)
        context.close.assert_called_once()

    def test_main_invalid_delay_raises_value_error(self) -> None:
        args = self._args(min_delay=5.0, max_delay=1.0)
        with patch.object(cli, "parse_args", return_value=args):
            with self.assertRaises(ValueError):
                cli.main()

    def test_main_runtime_error_returns_one(self) -> None:
        args = self._args()
        page = Mock(name="page")
        context = FakeContext(page=page)
        with (
            patch.object(cli, "parse_args", return_value=args),
            patch.object(cli, "sync_playwright", return_value=FakeSyncPlaywright("pw")),
            patch.object(cli, "launch_context", return_value=context),
            patch.object(cli, "open_profile", side_effect=RuntimeError("falha")),
        ):
            result = cli.main()
        self.assertEqual(result, 1)
        context.close.assert_called_once()


class TestProfileFilterComponent(unittest.TestCase):
    def _args(self, **overrides) -> Namespace:
        base = dict(
            input="nao_seguidores.json",
            output="nao_seguidores_filtrados.json",
            user_data_dir=r"C:\perfil",
            threshold=3000,
            min_delay=1.0,
            max_delay=2.0,
            headless=True,
        )
        base.update(overrides)
        return Namespace(**base)

    def test_main_success_filters_by_threshold(self) -> None:
        args = self._args()
        parser = Mock(name="parser")
        parser.parse_args.return_value = args
        page = Mock(name="page")
        context = FakeContext(page=page)
        source_items = [{"insta": "@u1"}, {"insta": "@u2"}, {"insta": "@u3"}]

        with (
            patch.object(profile_filter, "build_parser", return_value=parser),
            patch.object(profile_filter, "load_input_items", return_value=source_items),
            patch.object(profile_filter, "sync_playwright", return_value=FakeSyncPlaywright("pw")),
            patch.object(profile_filter, "launch_context", return_value=context),
            patch.object(profile_filter, "extract_username", side_effect=["u1", "u2", "u3"]),
            patch.object(profile_filter, "open_profile_page"),
            patch.object(profile_filter, "extract_followers_count", side_effect=[None, 5001, 1200]),
            patch.object(profile_filter, "random_delay"),
            patch.object(profile_filter, "save_payload") as save_payload,
        ):
            result = profile_filter.main()

        self.assertEqual(result, 0)
        saved_payload = save_payload.call_args[0][1]
        self.assertEqual(saved_payload["total_entrada"], 3)
        self.assertEqual(saved_payload["total_mantidos"], 2)
        self.assertEqual(saved_payload["total_removidos_famosos"], 1)
        self.assertEqual(saved_payload["total_nao_classificados"], 1)
        context.close.assert_called_once()

    def test_main_invalid_delay_raises_value_error(self) -> None:
        args = self._args(min_delay=-1.0)
        parser = Mock(name="parser")
        parser.parse_args.return_value = args
        with patch.object(profile_filter, "build_parser", return_value=parser):
            with self.assertRaises(ValueError):
                profile_filter.main()

    def test_main_runtime_error_returns_one(self) -> None:
        args = self._args()
        parser = Mock(name="parser")
        parser.parse_args.return_value = args
        page = Mock(name="page")
        context = FakeContext(page=page)
        with (
            patch.object(profile_filter, "build_parser", return_value=parser),
            patch.object(profile_filter, "load_input_items", return_value=[{"insta": "@u1"}]),
            patch.object(profile_filter, "sync_playwright", return_value=FakeSyncPlaywright("pw")),
            patch.object(profile_filter, "launch_context", return_value=context),
            patch.object(profile_filter, "extract_username", return_value="u1"),
            patch.object(profile_filter, "open_profile_page", side_effect=RuntimeError("falha")),
        ):
            result = profile_filter.main()
        self.assertEqual(result, 1)
        context.close.assert_called_once()

    def test_load_input_items_validates_json_structure(self) -> None:
        valid_path = _write_json_file({"nao_seguidores": [{"insta": "@ok"}]})
        invalid_root_path = _write_json_file([{"insta": "@x"}])
        invalid_key_path = _write_json_file({"nao_seguidores": "invalido"})
        self.addCleanup(valid_path.unlink)
        self.addCleanup(invalid_root_path.unlink)
        self.addCleanup(invalid_key_path.unlink)

        self.assertEqual(profile_filter.load_input_items(valid_path), [{"insta": "@ok"}])
        with self.assertRaises(ValueError):
            profile_filter.load_input_items(invalid_root_path)
        with self.assertRaises(ValueError):
            profile_filter.load_input_items(invalid_key_path)

    def test_extract_username_handles_insta_and_link(self) -> None:
        self.assertEqual(profile_filter.extract_username({"insta": "@ana"}), "ana")
        self.assertEqual(
            profile_filter.extract_username({"link": "https://www.instagram.com/bia/"}),
            "bia",
        )
        with self.assertRaises(ValueError):
            profile_filter.extract_username({"insta": "", "link": ""})


class TestUnfollowerComponent(unittest.TestCase):
    def _args(self, **overrides) -> Namespace:
        base = dict(
            input="nao_seguidores_filtrados.json",
            output="unfollow_report.json",
            user_data_dir=r"C:\perfil",
            min_delay=1.0,
            max_delay=2.0,
            headless=True,
        )
        base.update(overrides)
        return Namespace(**base)

    def test_unfollow_profile_returns_nao_encontrado(self) -> None:
        page = Mock(name="page")
        with (
            patch.object(unfollower, "open_profile_page"),
            patch.object(unfollower, "find_clickable_by_hints", return_value=None),
        ):
            status = unfollower.unfollow_profile(page, "ana")
        self.assertEqual(status, "nao_encontrado")

    def test_unfollow_profile_returns_confirmacao_nao_encontrada(self) -> None:
        page = Mock(name="page")
        dialog = Mock(name="dialog")
        page.locator.return_value.first = dialog
        follow_button = Mock(name="follow_button")

        with (
            patch.object(unfollower, "open_profile_page"),
            patch.object(unfollower, "find_clickable_by_hints", side_effect=[follow_button, None]),
        ):
            status = unfollower.unfollow_profile(page, "ana")

        self.assertEqual(status, "confirmacao_nao_encontrada")
        follow_button.click.assert_called_once()

    def test_unfollow_profile_returns_unfollowed(self) -> None:
        page = Mock(name="page")
        dialog = Mock(name="dialog")
        page.locator.return_value.first = dialog
        follow_button = Mock(name="follow_button")
        confirm_button = Mock(name="confirm_button")

        with (
            patch.object(unfollower, "open_profile_page"),
            patch.object(unfollower, "find_clickable_by_hints", side_effect=[follow_button, confirm_button]),
        ):
            status = unfollower.unfollow_profile(page, "ana")

        self.assertEqual(status, "unfollowed")
        follow_button.click.assert_called_once()
        confirm_button.click.assert_called_once()

    def test_main_success_generates_report(self) -> None:
        args = self._args()
        parser = Mock(name="parser")
        parser.parse_args.return_value = args
        page = Mock(name="page")
        context = FakeContext(page=page)
        source_items = [{"insta": "@u1"}, {"insta": "@u2"}]

        with (
            patch.object(unfollower, "build_parser", return_value=parser),
            patch.object(unfollower, "load_items", return_value=source_items),
            patch.object(unfollower, "sync_playwright", return_value=FakeSyncPlaywright("pw")),
            patch.object(unfollower, "launch_context", return_value=context),
            patch.object(unfollower, "extract_username", side_effect=["u1", "u2"]),
            patch.object(unfollower, "unfollow_profile", side_effect=["unfollowed", "confirmacao_nao_encontrada"]),
            patch.object(unfollower, "random_delay"),
            patch.object(unfollower, "save_payload") as save_payload,
        ):
            result = unfollower.main()

        self.assertEqual(result, 0)
        report = save_payload.call_args[0][1]
        self.assertEqual(report["total_entrada"], 2)
        self.assertEqual(report["total_unfollowed"], 1)
        self.assertEqual(report["total_sem_confirmacao"], 1)
        context.close.assert_called_once()

    def test_main_invalid_delay_raises_value_error(self) -> None:
        args = self._args(min_delay=3.0, max_delay=2.0)
        parser = Mock(name="parser")
        parser.parse_args.return_value = args
        with patch.object(unfollower, "build_parser", return_value=parser):
            with self.assertRaises(ValueError):
                unfollower.main()

    def test_main_runtime_error_returns_one(self) -> None:
        args = self._args()
        parser = Mock(name="parser")
        parser.parse_args.return_value = args
        page = Mock(name="page")
        context = FakeContext(page=page)
        with (
            patch.object(unfollower, "build_parser", return_value=parser),
            patch.object(unfollower, "load_items", return_value=[{"insta": "@u1"}]),
            patch.object(unfollower, "sync_playwright", return_value=FakeSyncPlaywright("pw")),
            patch.object(unfollower, "launch_context", return_value=context),
            patch.object(unfollower, "extract_username", return_value="u1"),
            patch.object(unfollower, "unfollow_profile", side_effect=RuntimeError("falha")),
        ):
            result = unfollower.main()
        self.assertEqual(result, 1)
        context.close.assert_called_once()

    def test_load_items_and_extract_username_validations(self) -> None:
        valid_path = _write_json_file({"nao_seguidores": [{"insta": "@ok"}]})
        invalid_root_path = _write_json_file([{"insta": "@x"}])
        invalid_key_path = _write_json_file({"nao_seguidores": "invalido"})
        self.addCleanup(valid_path.unlink)
        self.addCleanup(invalid_root_path.unlink)
        self.addCleanup(invalid_key_path.unlink)

        self.assertEqual(unfollower.load_items(valid_path), [{"insta": "@ok"}])
        with self.assertRaises(ValueError):
            unfollower.load_items(invalid_root_path)
        with self.assertRaises(ValueError):
            unfollower.load_items(invalid_key_path)
        self.assertEqual(unfollower.extract_username({"insta": "@ana"}), "ana")
        self.assertEqual(unfollower.extract_username({"link": "https://www.instagram.com/bia/"}), "bia")
        with self.assertRaises(ValueError):
            unfollower.extract_username({"insta": "", "link": ""})


if __name__ == "__main__":
    unittest.main()
