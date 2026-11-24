"""Pre-commit claim gate: refuse a commit on a branch another session holds."""

from __future__ import annotations


def blocked(branch: str, session: str, claims: list[dict]) -> str | None:
    """Return a message naming the holder when a claim has `branch` and a different `session`, else None.

    An empty `session` is never blocked.
    """
    if not session:
        return None
    for claim in claims:
        if claim["branch"] == branch and claim["session"] != session:
            return (
                f"Commit blocked: branch {branch} is held by session {claim['session']} (checkout {claim['checkout']})."
            )
    return None
