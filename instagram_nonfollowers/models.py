from dataclasses import dataclass


@dataclass(frozen=True)
class ModalConfig:
    label: str
    href_suffix: str
    text_hints: tuple[str, ...]


FOLLOWERS = ModalConfig("Seguidores", "followers", ("followers", "seguidores"))
FOLLOWING = ModalConfig("Seguindo", "following", ("following", "seguindo"))
