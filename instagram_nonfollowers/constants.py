import re


BASE_URL = "https://www.instagram.com/"
USERNAME_RE = re.compile(r"^[A-Za-z0-9._]{1,30}$")
COUNT_RE = re.compile(r"(?<!\d)(\d[\d.,]*)")
DEFAULT_VIEWPORT = {"width": 1440, "height": 960}
DEFAULT_DELAY_RANGE = (1.5, 3.5)
BLOCKLIST = {
    "",
    "accounts",
    "about",
    "api",
    "explore",
    "developer",
    "directory",
    "graphql",
    "p",
    "reel",
    "reels",
    "stories",
    "tv",
    "direct",
    "challenge",
    "privacy",
    "terms",
    "notfound",
}
