from __future__ import annotations


def is_admin_actor(admin_id: int | None) -> bool:
    return bool(admin_id and admin_id > 0)
