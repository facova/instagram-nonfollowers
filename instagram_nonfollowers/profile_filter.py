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

from .browser import (
    extract_profile_count,
    launch_context,
    open_profile_page,
)
from .collector import save_payload

logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    return build_parser().parse_args()


def build_parser(default_threshold: int = 3000) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Filtra perfis famosos da lista de nao seguidores."
    )
    parser.add_argument(
        "--input",
        default="nao_seguidores.json",
        help="Arquivo JSON de entrada com a lista nao_seguidores.",
    )
    parser.add_argument(
        "--output",
        default="nao_seguidores_filtrados.json",
        help="Arquivo JSON de saida com a lista filtrada.",
    )
    parser.add_argument(
        "--user-data-dir",
        required=True,
        help="Caminho para o perfil persistente do navegador ja autenticado.",
    )
    parser.add_argument(
        "--threshold",
        type=int,
        default=default_threshold,
        help="Limite minimo de seguidores para considerar um perfil famoso. Qualquer valor acima deste numero sera removido.",
    )
    parser.add_argument("--min-delay", type=float, default=1.5, help="Delay minimo entre perfis.")
    parser.add_argument("--max-delay", type=float, default=3.5, help="Delay maximo entre perfis.")
    parser.add_argument("--headless", action="store_true", help="Executa o navegador em modo headless.")
    return parser


def random_delay(min_delay: float, max_delay: float) -> None:
    time.sleep(random.uniform(min_delay, max_delay))


def load_input_items(path: Path) -> list[dict]:
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


def extract_followers_count(page) -> int | None:
    candidates = page.locator("a[href], button, div[role='button']")
    total = candidates.count()
    for index in range(total):
        element = candidates.nth(index)
        text = " ".join(
            part
            for part in (
                (element.inner_text() or "").strip().lower(),
                (element.get_attribute("aria-label") or "").strip().lower(),
                (element.get_attribute("href") or "").strip().lower(),
            )
            if part
        )

        if "followers" not in text and "seguidores" not in text:
            continue

        for label in ("followers", "seguidores"):
            count = extract_profile_count(text, (label,))
            if count is not None:
                return count

    return None


def build_output(
    source_items: list[dict],
    kept_items: list[dict],
    removed_items: list[dict],
    unknown_items: list[dict],
    threshold: int,
) -> dict:
    return {
        "limite_famoso": threshold,
        "total_entrada": len(source_items),
        "total_mantidos": len(kept_items),
        "total_removidos_famosos": len(removed_items),
        "total_nao_classificados": len(unknown_items),
        "nao_seguidores": kept_items,
        "famosos_removidos": removed_items,
        "nao_classificados": unknown_items,
    }


def main(default_threshold: int = 3000) -> int:
    args = build_parser(default_threshold).parse_args()
    if args.min_delay < 0 or args.max_delay < 0 or args.min_delay > args.max_delay:
        raise ValueError("--min-delay e --max-delay precisam ser positivos e min <= max.")

    logging.basicConfig(level=logging.INFO, format="%(message)s")

    input_path = Path(args.input).expanduser().resolve()
    output_path = Path(args.output).expanduser().resolve()
    user_data_dir = Path(args.user_data_dir).expanduser().resolve()

    source_items = load_input_items(input_path)

    with sync_playwright() as playwright:
        context = launch_context(playwright, str(user_data_dir), args.headless)
        page = context.pages[0] if context.pages else context.new_page()

        kept_items: list[dict] = []
        removed_items: list[dict] = []
        unknown_items: list[dict] = []

        try:
            total = len(source_items)
            for index, item in enumerate(source_items, start=1):
                username = extract_username(item)
                logger.info("[%s/%s] Abrindo @%s...", index, total, username)
                open_profile_page(page, username)

                followers_count = extract_followers_count(page)
                if followers_count is None:
                    logger.warning(
                        "Nao foi possivel ler os seguidores de @%s; mantendo na lista.",
                        username,
                    )
                    kept_items.append(item)
                    unknown_items.append(item)
                elif followers_count > args.threshold:
                    logger.info(
                        "@%s removido por ter %s seguidores (> %s).",
                        username,
                        followers_count,
                        args.threshold,
                    )
                    removed_items.append(
                        {**item, "seguidores_totais": followers_count}
                    )
                else:
                    logger.info(
                        "@%s mantido com %s seguidores.",
                        username,
                        followers_count,
                    )
                    kept_items.append(item)

                if index < total:
                    random_delay(args.min_delay, args.max_delay)

            payload = build_output(source_items, kept_items, removed_items, unknown_items, args.threshold)
            save_payload(output_path, payload)
            logging.info("Arquivo salvo em: %s", output_path)
            logging.info(
                "Resumo: %s mantidos, %s removidos, %s nao classificados.",
                payload["total_mantidos"],
                payload["total_removidos_famosos"],
                payload["total_nao_classificados"],
            )
        except (PlaywrightTimeoutError, PlaywrightError, RuntimeError, KeyboardInterrupt) as exc:
            logging.error("Erro: %s", exc)
            return 1
        finally:
            context.close()

    return 0
