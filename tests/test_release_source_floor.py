from __future__ import annotations

import unittest

from services.github_release_automation import _source_floor_for_version
from services.notes_control_plane import ControlPlaneError


class ReleaseSourceFloorTests(unittest.TestCase):
    def test_legacy_bridge_remains_available_for_105(self):
        self.assertEqual(_source_floor_for_version(10005), 10003)

    def test_emergency_1014_release_accepts_1012(self):
        self.assertEqual(_source_floor_for_version(10014), 10012)

    def test_post_bridge_releases_require_immediately_previous_version(self):
        cases = [
            (10006, 10005),
            (10007, 10006),
            (10013, 10012),
            (10015, 10014),
            (10099, 10098),
            (10100, 10099),
            (10200, 10199),
        ]
        for version_code, expected_source in cases:
            with self.subTest(version_code=version_code):
                self.assertEqual(
                    _source_floor_for_version(version_code),
                    expected_source,
                )

    def test_generic_versions_are_also_sequential(self):
        self.assertEqual(_source_floor_for_version(2), 1)
        self.assertEqual(_source_floor_for_version(42), 41)

    def test_invalid_version_code_is_rejected(self):
        with self.assertRaises(ControlPlaneError):
            _source_floor_for_version(1)


if __name__ == "__main__":
    unittest.main()
