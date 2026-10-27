from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from types import SimpleNamespace
import unittest

from jinja2 import ChoiceLoader, DictLoader, Environment, FileSystemLoader, select_autoescape
from config.notes_features import LICENSE_FEATURE_OPTIONS


class FeatureInputs(HTMLParser):
    def __init__(self):
        super().__init__()
        self.features = {}

    def handle_starttag(self, tag, attrs):
        fields = dict(attrs)
        if tag == 'input' and fields.get('name') == 'license_feature':
            self.features[fields['value']] = 'checked' in fields


class LicenseFeatureSelectionTests(unittest.TestCase):
    def render(self, record=None):
        root = Path(__file__).resolve().parents[1]
        environment = Environment(
            loader=ChoiceLoader([
                DictLoader({'/dashboard/^core/base.html': '{% block content %}{% endblock %}{% block extra_js %}{% endblock %}'}),
                FileSystemLoader(root / 'templates'),
            ]),
            autoescape=select_autoescape(['html']),
        )
        environment.globals.update(url_for=lambda *args, **kwargs: '/test', csrf_token=lambda: 'test-csrf')
        return environment.get_template('dashboard/control_plane/licenses.html').render(
            tab='issue', stats={'total': 0}, reissue_license=record,
            license_feature_options=LICENSE_FEATURE_OPTIONS,
            license_trusted_keys={}, suggested_license_id='lic-new',
        )

    def test_new_license_includes_all_nine_modules(self):
        parser = FeatureInputs()
        parser.feed(self.render())
        self.assertEqual(len(parser.features), 9)
        self.assertTrue(all(parser.features.values()))
        self.assertTrue(parser.features['workspace.calendar'])
        self.assertTrue(parser.features['workspace.defects'])
        self.assertTrue(parser.features['workspace.work-permits'])

    def test_reissue_preserves_modules_and_prefills_identity(self):
        record = SimpleNamespace(
            id='00000000-0000-4000-8000-000000000002',
            license_id='lic-existing', installation_id='00000000-0000-4000-8000-000000000001',
            customer='Example <owner>', edition='team', max_users=20,
            features=['workspace.notes', 'custom.integration'],
            license_not_before=datetime(2026, 1, 1, tzinfo=timezone.utc),
            license_expires_at=datetime(2030, 1, 1, tzinfo=timezone.utc),
        )
        html = self.render(record)
        parser = FeatureInputs()
        parser.feed(html)
        self.assertEqual(parser.features, {
            **{code: code == 'workspace.notes' for code, _ in LICENSE_FEATURE_OPTIONS},
            'custom.integration': True,
        })
        self.assertIn('value="lic-existing"', html)
        self.assertIn('value="2030-01-01T00:00"', html)
        self.assertIn('Example &lt;owner&gt;', html)
        self.assertIn('features: selectedFeatures', html)
        self.assertNotIn('features: standardFeatures', html)

    def test_reissue_preserves_new_module_entitlements(self):
        record = SimpleNamespace(
            id='00000000-0000-4000-8000-000000000002',
            license_id='lic-12', installation_id='00000000-0000-4000-8000-000000000001',
            customer='Owner', edition='team', max_users=20,
            features=['workspace.defects', 'workspace.work-permits'],
            license_not_before=None, license_expires_at=None,
        )
        parser = FeatureInputs()
        parser.feed(self.render(record))
        self.assertEqual({code for code, checked in parser.features.items() if checked}, set(record.features))


if __name__ == '__main__':
    unittest.main()
