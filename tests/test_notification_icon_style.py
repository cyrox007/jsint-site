from __future__ import annotations

import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]


class NotificationIconStyleTests(unittest.TestCase):
    def read(self, relative: str) -> str:
        return (ROOT / relative).read_text(encoding="utf-8")

    def test_notification_icon_is_monochrome_svg_not_emoji(self):
        header = self.read("templates/dashboard/^shared/header/index.html")
        sidebar = self.read("templates/dashboard/^shared/sidebar/index.html")
        styles = self.read("templates/dashboard/^shared/header/style.css")

        self.assertNotIn("🔔", header)
        self.assertNotIn("🔔", sidebar)
        self.assertIn("notification-icon-svg", header)
        self.assertIn("notification-icon-svg", sidebar)
        self.assertIn('stroke="currentColor"', header)
        self.assertIn(".notification-icon-svg", styles)


if __name__ == "__main__":
    unittest.main()
