import re

from .constants import DEFAULT_VIEWPORT
from .models import ModalConfig


def launch_context(playwright, user_data_dir: str, headless: bool):
    return playwright.chromium.launch_persistent_context(
        user_data_dir=user_data_dir,
        headless=headless,
        viewport=DEFAULT_VIEWPORT,
    )


def open_profile(page, username: str) -> None:
    open_profile_page(page, username)

    selectors = [
        "a[href*='/followers/']",
        "a[href*='/following/']",
        "header a[href]",
    ]
    last_error = None
    for selector in selectors:
        try:
            page.wait_for_selector(selector, timeout=20000)
            return
        except Exception as exc:
            last_error = exc

    raise RuntimeError(
        f"Nao consegui localizar os controles do perfil em {page.url}. "
        "Verifique se a conta esta aberta, autenticada e sem tela de login. "
        f"Ultimo erro: {last_error}"
    )


def open_profile_page(page, username: str) -> None:
    page.goto(f"https://www.instagram.com/{username}/", wait_until="domcontentloaded")
    page.wait_for_timeout(1500)

    if "accounts/login" in page.url or "challenge" in page.url:
        raise RuntimeError(
            "O navegador caiu em login/validacao. Verifique se o perfil informado esta realmente autenticado."
        )

    page.wait_for_selector("header", timeout=20000)


def get_profile_counts(page) -> dict[str, int | None]:
    header_text = page.locator("header").inner_text(timeout=5000)
    return {
        "seguidores": extract_profile_count(header_text, ("followers", "seguidores")),
        "seguindo": extract_profile_count(header_text, ("following", "seguindo")),
    }


def extract_profile_followers_count(page) -> int | None:
    header_text = page.locator("header").inner_text(timeout=5000)
    return extract_profile_count(header_text, ("followers", "seguidores"))


def extract_profile_count(text: str, labels: tuple[str, ...]) -> int | None:
    normalized = (text or "").lower()
    for label in labels:
        patterns = [
            rf"(?P<count>\d[\d.,]*\s*(?:mil|k|m|mi)?)\s*(?:{re.escape(label)})\b",
            rf"(?:{re.escape(label)})\s*(?P<count>\d[\d.,]*\s*(?:mil|k|m|mi)?)\b",
        ]
        for pattern in patterns:
            match = re.search(pattern, normalized, flags=re.IGNORECASE)
            if match:
                count = parse_instagram_count_token(match.group("count"))
                if count is not None:
                    return count
    return None


def parse_instagram_count_token(value: str) -> int | None:
    token = (value or "").strip().lower().replace(" ", "")
    if not token:
        return None

    multiplier = 1
    for suffix, suffix_multiplier in (
        ("mil", 1000),
        ("milhoes", 1_000_000),
        ("milhão", 1_000_000),
        ("milhões", 1_000_000),
        ("mi", 1_000_000),
        ("m", 1_000_000),
        ("k", 1000),
    ):
        if token.endswith(suffix):
            multiplier = suffix_multiplier
            token = token[: -len(suffix)]
            break

    token = token.strip()
    if not token:
        return None

    if multiplier in (1000, 1_000_000) and re.fullmatch(r"\d+(?:[.,]\d+)?", token):
        try:
            return int(round(float(token.replace(",", ".")) * multiplier))
        except ValueError:
            return None

    if re.fullmatch(r"\d{1,3}(?:[.,]\d{3})+", token):
        return int(token.replace(".", "").replace(",", ""))

    if re.fullmatch(r"\d+(?:[.,]\d+)?", token):
        try:
            number = float(token.replace(",", "."))
            return int(round(number * multiplier))
        except ValueError:
            return None

    digits = "".join(char for char in token if char.isdigit())
    return int(digits) if digits else None


def find_modal_link(page, config: ModalConfig):
    links = page.locator("a[href], button, div[role='button']")
    total = links.count()
    for index in range(total):
        link = links.nth(index)
        href = link.get_attribute("href") or ""
        text = (link.inner_text() or "").strip().lower()
        aria = (link.get_attribute("aria-label") or "").strip().lower()

        if config.href_suffix in href.lower():
            return link
        for hint in config.text_hints:
            if hint in text or hint in aria:
                return link

    return None


def open_modal(page, config: ModalConfig):
    link = find_modal_link(page, config)
    if link is None:
        available = page.locator("a[href], button, div[role='button']").evaluate_all(
            """els => els.slice(0, 30).map(el => ({
                href: el.getAttribute('href') || '',
                text: (el.textContent || '').trim(),
                aria: (el.getAttribute('aria-label') || '').trim()
            }))"""
        )
        raise RuntimeError(
            f"Link de {config.label.lower()} nao encontrado no perfil. "
            f"Primeiros links visiveis: {available}"
        )

    link.wait_for(state="visible", timeout=15000)
    link.click()
    dialog = page.locator("div[role='dialog']").first
    dialog.wait_for(state="visible", timeout=15000)
    return dialog


def close_modal(page) -> None:
    page.keyboard.press("Escape")
    page.wait_for_timeout(500)


def get_modal_scroll_position(dialog) -> tuple[int, int, int]:
    return dialog.evaluate(
        """node => {
            const candidates = [node, ...node.querySelectorAll('*')];
            let best = null;
            let bestDelta = -1;

            for (const candidate of candidates) {
                const style = window.getComputedStyle(candidate);
                const overflowY = style.overflowY;
                const delta = candidate.scrollHeight - candidate.clientHeight;
                if ((overflowY === 'auto' || overflowY === 'scroll' || overflowY === 'overlay') && delta > bestDelta) {
                    best = candidate;
                    bestDelta = delta;
                }
            }

            const target = best || node;
            return [target.scrollTop, target.scrollHeight, target.clientHeight];
        }"""
    )


def get_scroll_candidates(dialog) -> list[int]:
    return dialog.evaluate(
        """node => {
            const candidates = [node, ...node.querySelectorAll('*')];
            return candidates
                .map((candidate, index) => {
                    const style = window.getComputedStyle(candidate);
                    const overflowY = style.overflowY;
                    const delta = candidate.scrollHeight - candidate.clientHeight;
                    return {
                        index,
                        delta,
                        overflowY,
                        top: candidate.scrollTop,
                        height: candidate.clientHeight,
                    };
                })
                .filter(item => (
                    (item.overflowY === 'auto' || item.overflowY === 'scroll' || item.overflowY === 'overlay') &&
                    item.delta > 10
                ))
                .sort((a, b) => b.delta - a.delta)
                .map(item => item.index);
        }"""
    )


def has_scrollable_area(dialog) -> bool:
    return dialog.evaluate(
        """node => {
            const candidates = [node, ...node.querySelectorAll('*')];
            for (const candidate of candidates) {
                const style = window.getComputedStyle(candidate);
                const overflowY = style.overflowY;
                if ((overflowY === 'auto' || overflowY === 'scroll' || overflowY === 'overlay') &&
                    candidate.scrollHeight > candidate.clientHeight + 10) {
                    return true;
                }
            }
            return false;
        }"""
    )


def scroll_modal(page, dialog) -> bool:
    candidates = get_scroll_candidates(dialog)
    if not candidates:
        return False

    for index in candidates[:5]:
        target = dialog if index == 0 else dialog.locator("*").nth(index - 1)
        before = target.evaluate(
            """node => [node.scrollTop, node.scrollHeight, node.clientHeight]"""
        )
        target.evaluate(
            """node => {
                const step = Math.max(240, Math.floor(node.clientHeight * 0.9));
                node.scrollTop = Math.min(node.scrollTop + step, node.scrollHeight);
            }"""
        )
        after = target.evaluate(
            """node => [node.scrollTop, node.scrollHeight, node.clientHeight]"""
        )
        if after[0] > before[0]:
            return True

    index = candidates[0]
    target = dialog if index == 0 else dialog.locator("*").nth(index - 1)
    box = target.bounding_box()
    if box is None:
        return False

    before = target.evaluate(
        """node => [node.scrollTop, node.scrollHeight, node.clientHeight]"""
    )
    page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
    page.mouse.wheel(0, 1200)
    page.wait_for_timeout(750)

    after = target.evaluate(
        """node => [node.scrollTop, node.scrollHeight, node.clientHeight]"""
    )
    return after[0] > before[0]
