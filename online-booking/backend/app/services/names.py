"""FIO storage rules — the single source of truth.

`users.name` is the display full name ("Имя Фамилия") every list, badge
and CSV already renders. `users.last_name` mirrors the surname for the
structured profile forms. Both are always written together so the two
representations (one string vs two fields) can never drift.
"""
from typing import Optional, Tuple


def split_full_name(full: Optional[str]) -> Tuple[str, str]:
    """("Иван Петров Сидоров") -> ("Иван", "Петров Сидоров")."""
    parts = (full or "").strip().split()
    if not parts:
        return "", ""
    if len(parts) == 1:
        return parts[0], ""
    return parts[0], " ".join(parts[1:])


def compose_full_name(first: Optional[str], last: Optional[str] = None) -> str:
    """("Иван", "Петров") -> "Иван Петров"."""
    first = (first or "").strip()
    last = (last or "").strip()
    return f"{first} {last}".strip()


def name_fields(full: Optional[str]) -> Tuple[str, Optional[str]]:
    """Constructor values for a one-string full name: (name, last_name)."""
    name = " ".join((full or "").split())
    _, last = split_full_name(name)
    return name, last or None


def set_full_name(user, full: str) -> None:
    """Assign a name edited as ONE string and re-sync last_name.

    Also flags the name as human-set (name_source="user") so social logins
    never overwrite it — see app.services.social_merge.
    """
    name, last = name_fields(full)
    user.name = name
    user.last_name = last
    user.name_source = "user"


def set_names(user, first: Optional[str], last: Optional[str] = None) -> None:
    """Assign name from separate first/last fields (profile forms).

    Flags the name as human-set (name_source="user") — social logins leave it
    alone. Registration/creation paths use name_fields + a direct constructor
    instead, so a brand-new account is not marked as human-edited.
    """
    user.name = compose_full_name(first, last)
    user.last_name = (last or "").strip() or None
    user.name_source = "user"
