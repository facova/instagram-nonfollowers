from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

from .browser import get_profile_counts, launch_context, open_profile
from .collector import build_payload, capture_modal, save_payload
from .models import FOLLOWERS, FOLLOWING


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Identifica usuarios que voce segue no Instagram, mas que nao seguem de volta."
    )
    parser.add_argument("--username", required=True, help="Seu username do Instagram.")
    parser.add_argument(
        "--user-data-dir",
        required=True,
        help="Caminho para o perfil persistente do navegador ja autenticado.",
    )
    parser.add_argument(
        "--output",
        default="nao_seguidores.json",
        help="Arquivo JSON de saida.",
    )
    parser.add_argument("--min-delay", type=float, default=1.5, help="Delay minimo entre rolagens.")
    parser.add_argument("--max-delay", type=float, default=3.5, help="Delay maximo entre rolagens.")
    parser.add_argument("--headless", action="store_true", help="Executa o navegador em modo headless.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.min_delay < 0 or args.max_delay < 0 or args.min_delay > args.max_delay:
        raise ValueError("--min-delay e --max-delay precisam ser positivos e min <= max.")

    logging.basicConfig(level=logging.INFO, format="%(message)s")

    user_data_dir = Path(args.user_data_dir).expanduser().resolve()
    output_path = Path(args.output).expanduser().resolve()

    with sync_playwright() as playwright:
        context = launch_context(playwright, str(user_data_dir), args.headless)
        page = context.pages[0] if context.pages else context.new_page()

        try:
            open_profile(page, args.username)
            expected_counts = get_profile_counts(page)
            logging.info(
                "Contagens no perfil: seguidores=%s, seguindo=%s",
                expected_counts["seguidores"],
                expected_counts["seguindo"],
            )
            followers = capture_modal(
                page,
                FOLLOWERS,
                args.min_delay,
                args.max_delay,
                exclude_usernames={args.username},
                expected_count=expected_counts["seguidores"],
            )
            following = capture_modal(
                page,
                FOLLOWING,
                args.min_delay,
                args.max_delay,
                exclude_usernames={args.username},
                expected_count=expected_counts["seguindo"],
            )
            payload = build_payload(
                followers,
                following,
                expected_followers=expected_counts["seguidores"],
                expected_following=expected_counts["seguindo"],
            )
            save_payload(output_path, payload)
            logging.info("Arquivo salvo em: %s", output_path)
            logging.info(
                "Resumo: %s seguidores, %s seguindo, %s nao seguidores.",
                payload["total_seguidores"],
                payload["total_seguindo"],
                payload["total_nao_seguidores"],
            )
            if "validacao" in payload:
                validacao = payload["validacao"]
                logging.info(
                    "Validacao: seguidores %s/%s, seguindo %s/%s.",
                    validacao["encontrado_seguidores"],
                    validacao["esperado_seguidores"],
                    validacao["encontrado_seguindo"],
                    validacao["esperado_seguindo"],
                )
        except (PlaywrightTimeoutError, PlaywrightError, RuntimeError, KeyboardInterrupt) as exc:
            logging.error("Erro: %s", exc)
            return 1
        finally:
            context.close()

    return 0
