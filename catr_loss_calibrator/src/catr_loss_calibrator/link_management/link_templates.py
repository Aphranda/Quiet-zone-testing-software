from __future__ import annotations


def link_command(*ports: str) -> str:
    normalized = ", ".join(port.strip().upper() for port in ports if port.strip())
    if not normalized:
        raise ValueError("At least one link port is required.")
    return f"CONFigure:LINK {normalized}"

