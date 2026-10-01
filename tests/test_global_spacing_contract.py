from __future__ import annotations

import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]


class GlobalSpacingContractTests(unittest.TestCase):
    def read(self, relative: str) -> str:
        return (ROOT / relative).read_text(encoding="utf-8")

    def test_public_buttons_share_one_comfortable_rhythm(self):
        common = self.read("templates/public/^core/common.css")
        vanga = self.read("templates/public/vanga/style.css")

        self.assertIn("min-height: 50px", common)
        self.assertIn("padding: 12px 22px", common)
        self.assertIn("gap: 10px", common)
        self.assertIn("padding: 12px 22px", vanga)

    def test_admin_button_definitions_are_synchronized(self):
        common = self.read("templates/dashboard/^core/common.css")
        buttons = self.read(
            "templates/dashboard/^elements/UI/Buttons/style.css"
        )
        editor = self.read("templates/dashboard/publication/style.css")

        signature = "min-height:42px;padding:10px 16px"
        self.assertIn(signature, common)
        self.assertIn(signature, buttons)
        self.assertNotIn("padding:0 13px", editor)

    def test_dense_admin_blocks_have_real_spacing(self):
        ui = self.read("templates/dashboard/^core/ui.css")
        control = self.read("templates/dashboard/control_plane/style.css")
        inbox = self.read("templates/dashboard/inbox/style.css")
        media = self.read("templates/dashboard/media/style.css")
        dashboard = self.read("templates/dashboard/main/style.css")

        self.assertIn(".admin-grid{display:grid;gap:20px}", ui)
        self.assertIn(
            ".admin-grid + .admin-grid{margin-top:20px}",
            ui,
        )
        self.assertIn(
            ".operator-section+.operator-section{margin-top:14px}",
            control,
        )
        self.assertIn(
            ".control-registry{display:flex;flex-direction:column;gap:14px}",
            control,
        )
        self.assertIn(
            ".inbox-detail-main,.inbox-detail-side{display:grid;gap:18px}",
            inbox,
        )
        self.assertIn(".media-library{display:grid;gap:20px}", media)
        self.assertIn(
            ".admin-card__body>.admin-actions+.admin-form-note"
            "{margin-top:16px}",
            dashboard,
        )


if __name__ == "__main__":
    unittest.main()
