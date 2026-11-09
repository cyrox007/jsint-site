import unittest
from unittest.mock import MagicMock
from views.dashboard.control_plane.views import _release_preflight
from settings import config


class ReleaseRCPreflightTests(unittest.TestCase):
    def prepared(self):
        return dict(version='1.2.0-rc.1', version_code=12000, channel='stable',
                    package_status='rc', github_prerelease=False,
                    repository=config.NOTES_RELEASE_GITHUB_REPOSITORY.strip())

    def session(self, head=None):
        session = MagicMock()
        session.query.return_value.filter.return_value.order_by.return_value.first.return_value = head
        return session

    def test_official_rc_regular_release_passes(self):
        self.assertTrue(_release_preflight(self.session(), self.prepared())['ready'])

    def test_manual_or_prerelease_rc_stable_remains_blocked(self):
        for changes in [dict(package_status=None), dict(github_prerelease=True),
                        dict(github_prerelease=None), dict(repository='other/repository')]:
            with self.subTest(changes=changes):
                prepared = self.prepared()
                prepared.update(changes)
                self.assertFalse(_release_preflight(self.session(), prepared)['ready'])

    def test_version_order_still_blocks_even_official_rc(self):
        head = MagicMock(version_code=12001)
        self.assertFalse(_release_preflight(self.session(head), self.prepared())['ready'])
