"""A keyless PSI 429 must tell the user to add an API key, not just to wait.

Without a key every caller shares Google's public quota, which is often spent,
so "wait and retry" rarely helps.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

requests = pytest.importorskip("requests")

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import pagespeed_check  # noqa: E402


def _rate_limited(*_a, **_k):
    resp = MagicMock(status_code=429)
    resp.raise_for_status.side_effect = requests.exceptions.HTTPError("429")
    return resp


@pytest.mark.parametrize(("api_key", "needle"), [(None, "Add a Google API key"), ("k" * 39, "Wait and retry")])
def test_rate_limit_message_depends_on_api_key(api_key, needle) -> None:
    with patch.object(pagespeed_check, "validate_url", return_value=True), \
         patch.object(pagespeed_check.requests, "get", side_effect=_rate_limited):
        result = pagespeed_check.run_pagespeed("https://example.com/", api_key=api_key)
    assert needle in result["error"]
