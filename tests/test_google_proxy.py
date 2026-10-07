"""Google API calls honour HTTPS_PROXY.

google-api-python-client sends requests through httplib2, which tunnels
through a proxy only when the PySocks `socks` module is importable. Without
it, httplib2 drops the proxy silently on HTTPS and connects directly, which
fails wherever egress is allowed only through a proxy. These tests never
touch the network.
"""

from __future__ import annotations

import pytest

httplib2 = pytest.importorskip("httplib2")


def test_httplib2_uses_https_proxy_from_environment(monkeypatch) -> None:
    monkeypatch.delenv("no_proxy", raising=False)
    monkeypatch.delenv("NO_PROXY", raising=False)
    monkeypatch.setenv("https_proxy", "http://127.0.0.1:3128")

    proxy_info = httplib2.proxy_info_from_environment("https")

    assert proxy_info is not None
    assert proxy_info.isgood(), "httplib2 ignores the proxy: PySocks is missing"
