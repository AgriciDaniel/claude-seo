"""Keeps the suite independent of the developer's own claude-seo profile.

Removed before pytest imports any test module: a rejected value would
otherwise stop the import of google_auth and abort collection, and the
installer tests in test_matomo_report.py expect the default directory.
"""

import os

os.environ.pop("CLAUDE_SEO_PROFILE_DIR", None)
