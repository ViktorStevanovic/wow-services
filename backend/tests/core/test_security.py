import time

import pytest
from pydantic import SecretStr

from app.core.enums import Region
from app.core.security import (
    OAUTH_STATE_MAX_AGE_SECONDS,
    OAuthState,
    OAuthStateSigner,
    TokenCipher,
    generate_token,
    hash_token,
)

SECRET = SecretStr("a" * 40)
OTHER_SECRET = SecretStr("b" * 40)


def test_tokens_are_random_and_hash_is_stable() -> None:
    token = generate_token()

    assert token != generate_token()
    assert len(token) >= 43
    assert hash_token(token) == hash_token(token)
    assert hash_token(token) != token
    assert len(hash_token(token)) == 64


def test_cipher_round_trip() -> None:
    cipher = TokenCipher(SECRET)

    encrypted = cipher.encrypt("blizzard-token")

    assert "blizzard-token" not in encrypted
    assert cipher.decrypt(encrypted) == "blizzard-token"


def test_cipher_rejects_other_key_and_tampering() -> None:
    encrypted = TokenCipher(SECRET).encrypt("blizzard-token")

    assert TokenCipher(OTHER_SECRET).decrypt(encrypted) is None
    assert TokenCipher(SECRET).decrypt(encrypted[:-4] + "AAAA") is None


def test_oauth_state_round_trip() -> None:
    signer = OAuthStateSigner(SECRET)
    state = OAuthState(state="abc", region=Region.EU)

    assert signer.loads(signer.dumps(state)) == state


def test_oauth_state_rejects_tampering_and_other_secret() -> None:
    signed = OAuthStateSigner(SECRET).dumps(OAuthState(state="abc", region=Region.EU))

    assert OAuthStateSigner(SECRET).loads(signed + "x") is None
    assert OAuthStateSigner(OTHER_SECRET).loads(signed) is None
    assert OAuthStateSigner(SECRET).loads("garbage") is None


def test_oauth_state_expires(monkeypatch: pytest.MonkeyPatch) -> None:
    signer = OAuthStateSigner(SECRET)
    real_time = time.time
    with monkeypatch.context() as patched:
        patched.setattr(time, "time", lambda: real_time() - OAUTH_STATE_MAX_AGE_SECONDS - 5)
        signed = signer.dumps(OAuthState(state="abc", region=Region.EU))

    assert signer.loads(signed) is None
