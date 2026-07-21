"""Human-token verification (ACIS-08 §6, master §12 asymmetry).

The token gates `acis_resume`, `acis_set_mode`, and any equity/global HALT
clear: **any agent may stop trading; only a human may start it.**

GAP-0048 residual closed here: v1 is a GENUINE credential check — a constant-time
compare against the SHA-256 digest of a human-held secret, NOT a presence check
(any-truthy-string) and NOT a plaintext config value. A non-empty-but-wrong
token is rejected (C-MCP-10). The digest is injected (tests use a known secret;
production loads the real one from the environment/secret store, out-of-band).
"""

from __future__ import annotations

import hashlib
import hmac


class HumanTokenVerifier:
    """Holds only the SHA-256 hex digest of the human secret — never the secret."""

    def __init__(self, secret_sha256_hex: str) -> None:
        if not isinstance(secret_sha256_hex, str) or len(secret_sha256_hex) != 64:
            raise ValueError(
                "HumanTokenVerifier requires a 64-char sha256 hex digest of the "
                "human secret (never the plaintext secret)")
        self._digest = secret_sha256_hex.lower()

    @classmethod
    def from_secret(cls, secret: str) -> "HumanTokenVerifier":
        """Convenience for tests/bootstrap: derive the digest from a known
        secret. Production should construct with the digest directly so the
        plaintext never lives in the process that holds the verifier."""
        return cls(hashlib.sha256(secret.encode("utf-8")).hexdigest())

    def verify(self, token: str | None) -> bool:
        """True only for the exact human token. Blank/None refused before the
        compare; the compare itself is constant-time (no timing oracle)."""
        if not isinstance(token, str) or not token.strip():
            return False
        candidate = hashlib.sha256(token.encode("utf-8")).hexdigest()
        return hmac.compare_digest(candidate, self._digest)
