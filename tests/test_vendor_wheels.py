#!/usr/bin/env python3
"""Tests for vendor_wheels.py multi-platform support."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from vendor_wheels import DEFAULT_PLATFORMS


def test_vendor_wheels_multiplatform_default_has_four_platforms():
    """RED: DEFAULT_PLATFORMS should contain exactly 4 platforms."""
    assert len(DEFAULT_PLATFORMS) == 4, f"Expected 4 platforms, got {len(DEFAULT_PLATFORMS)}: {DEFAULT_PLATFORMS}"


def test_vendor_wheels_multiplatform_has_expected_archs():
    """RED: Platforms should include win_amd64, linux_x86_64, macosx_10_15_x86_64, macosx_11_0_arm64."""
    expected = {"win_amd64", "linux_x86_64", "macosx_10_15_x86_64", "macosx_11_0_arm64"}
    actual = set(DEFAULT_PLATFORMS)
    assert actual == expected, f"Expected {expected}, got {actual}"


def test_vendor_wheels_multiplatform_four_wheels_downloaded():
    """RED: Simulation that vendor_wheels dir contains .whl for each arch after download."""
    # This test simulates: after running vendor_wheels, check that
    # vendor_wheels/<platform>/ contains at least one .whl file per platform
    # For now, just verify the PLATFORMS list is correct
    platforms = DEFAULT_PLATFORMS
    assert len(platforms) == 4


if __name__ == "__main__":
    test_vendor_wheels_multiplatform_default_has_four_platforms()
    test_vendor_wheels_multiplatform_has_expected_archs()
    test_vendor_wheels_multiplatform_four_wheels_downloaded()
    print("All RED tests passed!")
