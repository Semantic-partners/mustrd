"""The Anzo TLS escape hatch.

These need no Anzo — every Anzo test in test_mustrd_anzo.py is skipped unless one is
configured, which is exactly why the cipher behaviour needs pinning here instead. The
old global urllib3 DEFAULT_CIPHERS mutation disappeared with urllib3 2.x, and nothing
in CI would have noticed.
"""
import ssl

import pytest

from mustrd import anzo_utils
from mustrd.anzo_utils import SSL_CIPHERS_ENV, _CipherAdapter, anzo_session


@pytest.fixture(autouse=True)
def _clear_cached_session():
    """The session is cached, so it must not leak between these tests."""
    anzo_utils._session = None
    yield
    anzo_utils._session = None


def test_no_tls_adapter_by_default(monkeypatch):
    monkeypatch.delenv(SSL_CIPHERS_ENV, raising=False)

    session = anzo_session()

    assert not any(isinstance(a, _CipherAdapter) for a in session.adapters.values())


def test_ciphers_env_mounts_an_adapter_on_https(monkeypatch):
    monkeypatch.setenv(SSL_CIPHERS_ENV, "DEFAULT:@SECLEVEL=1")

    session = anzo_session()

    adapter = session.adapters["https://"]
    assert isinstance(adapter, _CipherAdapter)
    # http:// is left alone — there is no TLS to negotiate.
    assert not isinstance(session.adapters["http://"], _CipherAdapter)


def test_the_context_actually_carries_the_cipher_string():
    # The point of the exercise: the string reaches an SSLContext. Asserting the
    # adapter exists would not prove the ciphers were applied.
    permissive = _CipherAdapter("DEFAULT:@SECLEVEL=1")
    restrictive = _CipherAdapter("ECDHE-RSA-AES256-GCM-SHA384")

    def ciphers_of(adapter):
        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        context.set_ciphers(adapter._ciphers)
        # TLS 1.3 suites are named TLS_* and are not selectable via set_ciphers — they
        # are always offered and configured separately. Only the TLS 1.2-and-below
        # list responds to the cipher string, so compare on that.
        return {c["name"] for c in context.get_ciphers()
                if not c["name"].startswith("TLS_")}

    assert ciphers_of(restrictive) == {"ECDHE-RSA-AES256-GCM-SHA384"}
    # A lowered security level admits strictly more than one hand-picked suite.
    assert len(ciphers_of(permissive)) > len(ciphers_of(restrictive))


def test_session_is_cached(monkeypatch):
    monkeypatch.delenv(SSL_CIPHERS_ENV, raising=False)

    assert anzo_session() is anzo_session()
