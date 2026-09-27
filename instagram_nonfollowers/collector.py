from __future__ import annotations

import json
import logging
import random
import time
from pathlib import Path
from typing import Iterable
from urllib.parse import urljoin, urlparse

from .browser import (
    close_modal,
    get_modal_scroll_position,
    get_scroll_candidates,
    has_scrollable_area,
    open_modal,
    scroll_modal,
)
from .constants import BASE_URL, BLOCKLIST, COUNT_RE, USERNAME_RE
from .models import ModalConfig

logger = logging.getLogger(__name__)


def normalize_username(href: str) -> str | None:
    parsed = urlparse(urljoin(BASE_URL, href))
    if parsed.netloc and "instagram.com" not in parsed.netloc:
        return None

    path = parsed.path.strip("/")
    if not path:
        return None

    username = path.split("/")[0].lstrip("@")
    if username.lower() in BLOCKLIST:
        return None
    if not USERNAME_RE.fullmatch(username):
        return None
    return username


def extract_usernames_from_dialog(dialog, exclude_usernames: set[str] | None = None) -> set[str]:
    hrefs = dialog.locator("a[href]").evaluate_all(
        """els => els.map(el => el.getAttribute('href') || '')"""
    )
    usernames = set()
    excluded = {name.lower() for name in (exclude_usernames or set())}
    for href in hrefs:
        username = normalize_username(href)
        if username is not None and username.lower() not in excluded:
            usernames.add(username)
    return usernames


def random_delay(min_delay: float, max_delay: float) -> None:
    time.sleep(random.uniform(min_delay, max_delay))


def parse_visible_count(text: str) -> int | None:
    match = COUNT_RE.search(text or "")
    if not match:
        return None
    normalized = match.group(1).replace(".", "").replace(",", "")
    if normalized.isdigit():
        return int(normalized)
    return None


def capture_modal(
    page,
    config: ModalConfig,
    min_delay: float,
    max_delay: float,
    exclude_usernames: set[str] | None = None,
    expected_count: int | None = None,
) -> set[str]:
    logger.info("Abrindo modal de %s...", config.label.lower())
    dialog = open_modal(page, config)
    if not has_scrollable_area(dialog):
        raise RuntimeError(f"Modal de {config.label.lower()} carregou sem area rolavel detectavel.")

    scroll_candidates = get_scroll_candidates(dialog)
    logger.info(
        "%s: candidatos de scroll detectados=%s", config.label, len(scroll_candidates)
    )
    collected: set[str] = set()
    idle_rounds = 0
    bottom_rounds = 0
    max_iterations = max(400, (expected_count or 0) * 3)
    count_hint = expected_count or parse_visible_count(dialog.inner_text(timeout=5000))

    for _ in range(max_iterations):
        current = extract_usernames_from_dialog(dialog, exclude_usernames=exclude_usernames)
        before = len(collected)
        collected |= current
        after = len(collected)

        if after > before:
            if count_hint is not None:
                logger.info("%s capturados: %s/%s...", config.label, after, count_hint)
            else:
                logger.info("%s capturados: %s...", config.label, after)
            idle_rounds = 0
        else:
            idle_rounds += 1

        scroll_top, scroll_height, client_height = get_modal_scroll_position(dialog)
        at_bottom = scroll_top + client_height >= scroll_height - 8
        if at_bottom:
            bottom_rounds += 1
        else:
            bottom_rounds = 0

        if count_hint is not None and after >= count_hint and bottom_rounds >= 3:
            break
        if expected_count is not None and after < expected_count and bottom_rounds >= 3 and idle_rounds >= 6:
            logger.warning(
                "%s ainda abaixo do esperado: %s/%s.", config.label, after, expected_count
            )
            break
        if at_bottom and idle_rounds >= 8:
            break
        if idle_rounds >= 20:
            logger.warning("Parando apos muitas iteracoes sem novos usernames em %s.", config.label.lower())
            break

        moved = scroll_modal(page, dialog)
        if not moved:
            logger.warning("Nao consegui mover o scroll em %s nesta iteracao.", config.label.lower())
        random_delay(min_delay, max_delay)
    else:
        logger.warning("Limite de iteracoes atingido ao capturar %s.", config.label.lower())

    close_modal(page)
    return collected


def build_payload(
    followers: Iterable[str],
    following: Iterable[str],
    expected_followers: int | None = None,
    expected_following: int | None = None,
) -> dict:
    followers_set = set(followers)
    following_set = set(following)
    non_followers = sorted(following_set - followers_set, key=str.lower)

    followers_count = len(followers_set)
    following_count = len(following_set)

    payload = {
        "total_seguindo": following_count,
        "total_seguidores": followers_count,
        "total_nao_seguidores": len(non_followers),
        "nao_seguidores": [
            {
                "insta": f"@{username}",
                "link": f"{BASE_URL}{username}",
            }
            for username in non_followers
        ],
    }

    if expected_followers is not None or expected_following is not None:
        payload["validacao"] = {
            "esperado_seguidores": expected_followers,
            "encontrado_seguidores": followers_count,
            "esperado_seguindo": expected_following,
            "encontrado_seguindo": following_count,
            "bate_seguidores": expected_followers is None or followers_count == expected_followers,
            "bate_seguindo": expected_following is None or following_count == expected_following,
        }

    return payload


def save_payload(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
