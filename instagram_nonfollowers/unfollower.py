from __future__ import annotations

import argparse
import json
import logging
import random
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

from .browser import launch_context, open_profile_page
from .collector import save_payload

logger = logging.getLogger(__name__)

FOLLOW_BUTTON_HINTS = ("following", "seguindo")
UNFOLLOW_BUTTON_HINTS = ("unfollow", "deixar de seguir", "confirm", "confirmar", "deixar de seguir")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Remove o follow dos perfis mantidos na lista filtrada."
    )
    parser.add_argument(
        "--input",
        default="nao_seguidores_filtrados.json",
        help="Arquivo JSON de entrada com a lista filtrada.",
    )
    parser.add_argument(
        "--output",
        default="unfollow_report.json",
        help="Arquivo JSON com o relatorio da operacao.",
    )
    parser.add_argument(
        "--user-data-dir",
        required=True,
        help="Caminho para o perfil persistente do navegador ja autenticado.",
    )
    parser.add_argument("--min-delay", type=float, default=1.5, help="Delay minimo entre perfis.")
    parser.add_argument("--max-delay", type=float, default=3.5, help="Delay maximo entre perfis.")
    parser.add_argument("--headless", action="store_true", help="Executa o navegador em modo headless.")
    return parser


def random_delay(min_delay: float, max_delay: float) -> None:
    time.sleep(random.uniform(min_delay, max_delay))


def load_items(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("O arquivo de entrada precisa conter um objeto JSON.")

    items = data.get("nao_seguidores")
    if not isinstance(items, list):
        raise ValueError("O arquivo de entrada precisa conter a chave 'nao_seguidores' como lista.")

    return items


def extract_username(item: dict) -> str:
    insta = str(item.get("insta") or "").strip()
    if insta.startswith("@"):
        insta = insta[1:]
    if insta:
        return insta

    link = str(item.get("link") or "").strip()
    if link:
        parsed = urlparse(link)
        path = parsed.path.strip("/")
        if path:
            return path.split("/")[0].lstrip("@")

    raise ValueError(f"Item sem username valido: {item}")


def element_text(locator) -> str:
    text = (locator.inner_text() or "").strip().lower()
    aria = (locator.get_attribute("aria-label") or "").strip().lower()
    href = (locator.get_attribute("href") or "").strip().lower()
    return " ".join(part for part in (text, aria, href) if part)


def find_clickable_by_hints(page, hints: tuple[str, ...], scope=None):
    root = scope if scope is not None else page
    for selector in ("button, div[role='button']", "a[href]"):
        locator = root.locator(selector)
        total = locator.count()
        for index in range(total):
            candidate = locator.nth(index)
            text = element_text(candidate)
            if any(hint in text for hint in hints):
                return candidate
    return None


def unfollow_profile(page, username: str) -> str:
    open_profile_page(page, username)

    follow_button = find_clickable_by_hints(page, FOLLOW_BUTTON_HINTS)
    if follow_button is None:
        return "nao_encontrado"

    follow_button.click()
    page.wait_for_timeout(700)

    dialog = page.locator("div[role='dialog']").first
    try:
        dialog.wait_for(state="visible", timeout=5000)
        confirm_button = find_clickable_by_hints(page, UNFOLLOW_BUTTON_HINTS, scope=dialog)
    except PlaywrightTimeoutError:
        confirm_button = find_clickable_by_hints(page, UNFOLLOW_BUTTON_HINTS)

    if confirm_button is None:
        return "confirmacao_nao_encontrada"

    confirm_button.click()
    page.wait_for_timeout(1000)
    return "unfollowed"


def build_report(source_items: list[dict], results: list[dict]) -> dict:
    return {
        "total_entrada": len(source_items),
        "total_processados": len(results),
        "total_unfollowed": sum(1 for item in results if item["status"] == "unfollowed"),
        "total_nao_encontrados": sum(1 for item in results if item["status"] == "nao_encontrado"),
        "total_sem_confirmacao": sum(1 for item in results if item["status"] == "confirmacao_nao_encontrada"),
        "resultados": results,
    }


def main() -> int:
    args = build_parser().parse_args()
    if args.min_delay < 0 or args.max_delay < 0 or args.min_delay > args.max_delay:
        raise ValueError("--min-delay e --max-delay precisam ser positivos e min <= max.")

    logging.basicConfig(level=logging.INFO, format="%(message)s")

    input_path = Path(args.input).expanduser().resolve()
    output_path = Path(args.output).expanduser().resolve()
    user_data_dir = Path(args.user_data_dir).expanduser().resolve()

    source_items = load_items(input_path)

    with sync_playwright() as playwright:
        context = launch_context(playwright, str(user_data_dir), args.headless)
        page = context.pages[0] if context.pages else context.new_page()
        results: list[dict] = []

        try:
            total = len(source_items)
            for index, item in enumerate(source_items, start=1):
                username = extract_username(item)
                logger.info("[%s/%s] Abrindo @%s...", index, total, username)
                status = unfollow_profile(page, username)
                results.append(
                    {
                        "insta": f"@{username}",
                        "link": f"https://www.instagram.com/{username}",
                        "status": status,
                    }
                )
                logger.info("@%s -> %s", username, status)
                if index < total:
                    random_delay(args.min_delay, args.max_delay)

            report = build_report(source_items, results)
            save_payload(output_path, report)
            logging.info("Arquivo salvo em: %s", output_path)
            logging.info(
                "Resumo: %s unfollows, %s sem localizacao, %s sem confirmacao.",
                report["total_unfollowed"],
                report["total_nao_encontrados"],
                report["total_sem_confirmacao"],
            )
        except (PlaywrightTimeoutError, PlaywrightError, RuntimeError, KeyboardInterrupt) as exc:
            logging.error("Erro: %s", exc)
            return 1
        finally:
            context.close()

    return 0
