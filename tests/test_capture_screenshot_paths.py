"""capture_screenshot.py only writes inside the current or home directory.

The old check compared string prefixes, so a sibling such as /home/user2
passed for /home/user, and a symlinked home never matched a resolved path.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

pytest.importorskip("playwright")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import capture_screenshot  # noqa: E402


@pytest.fixture
def roots(tmp_path, monkeypatch):
    home = tmp_path / "home" / "user"
    work = home / "project"
    work.mkdir(parents=True)
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    monkeypatch.chdir(work)
    return tmp_path, home, work


def test_paths_inside_cwd_or_home_are_allowed(roots):
    _tmp, home, work = roots
    assert capture_screenshot.safe_output_dir("screenshots") == os.path.realpath(work / "screenshots")
    assert capture_screenshot.safe_output_dir(str(home / "shots")) == os.path.realpath(home / "shots")
    assert capture_screenshot.safe_output_dir(str(home)) == os.path.realpath(home)


def test_sibling_with_a_shared_prefix_is_refused(roots):
    tmp, _home, _work = roots
    assert capture_screenshot.safe_output_dir(str(tmp / "home" / "user2" / "shots")) is None
    assert capture_screenshot.safe_output_dir(str(tmp / "home" / "user-evil")) is None


def test_traversal_out_of_the_roots_is_refused(roots):
    assert capture_screenshot.safe_output_dir("../../../outside") is None


@pytest.mark.skipif(os.name != "posix", reason="symlinks need POSIX here")
def test_symlinked_home_still_matches(tmp_path, monkeypatch):
    real = tmp_path / "var" / "home" / "user"
    real.mkdir(parents=True)
    (tmp_path / "home").symlink_to(tmp_path / "var" / "home")
    monkeypatch.setenv("HOME", str(tmp_path / "home" / "user"))
    monkeypatch.chdir(tmp_path)
    assert capture_screenshot.safe_output_dir(str(tmp_path / "home" / "user" / "shots")) == str(real / "shots")


def test_main_writes_into_the_resolved_directory(roots, monkeypatch):
    _tmp, _home, work = roots
    calls = []
    monkeypatch.setattr(
        capture_screenshot, "capture_screenshot",
        lambda url, path, **kw: calls.append(path) or {"success": True, "error": None},
    )
    monkeypatch.setattr(sys, "argv", ["capture_screenshot.py", "https://example.com", "-o", "shots"])
    capture_screenshot.main()
    assert calls == [os.path.join(os.path.realpath(work / "shots"), "example_com_desktop.png")]
    assert (work / "shots").is_dir()
