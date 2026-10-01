from __future__ import annotations

import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]


class InboxDetailUiContractTests(unittest.TestCase):
    def read(self, relative: str) -> str:
        return (ROOT / relative).read_text(encoding="utf-8")

    def test_detail_uses_compact_two_column_layout(self):
        template = self.read("templates/dashboard/inbox/detail.html")
        styles = self.read("templates/dashboard/inbox/style.css")

        self.assertIn("inbox-detail-layout", template)
        self.assertIn("inbox-detail-main", template)
        self.assertIn("inbox-detail-side", template)
        self.assertIn("inbox-sender", template)
        self.assertIn("inbox-info-card", template)
        self.assertIn("inbox-actions-card", template)
        self.assertIn(
            "grid-template-columns:minmax(0,1fr) 292px",
            styles,
        )
        self.assertIn("@media(max-width:900px)", styles)

    def test_contact_subject_is_not_duplicated_inside_message_card(self):
        template = self.read("templates/dashboard/inbox/detail.html")

        self.assertEqual(
            template.count("<h1>{{ notification.title }}</h1>"),
            1,
        )
        self.assertNotIn(
            "<h2>{{ source.subject or 'Без темы' }}</h2>",
            template,
        )
        self.assertIn("Сообщение", template)
        self.assertIn("Отправитель", template)

    def test_raw_internal_status_line_is_not_rendered(self):
        template = self.read("templates/dashboard/inbox/detail.html")

        self.assertNotIn("Статус: {{ notification.status }}", template)
        self.assertNotIn("Push: {{ notification.push_status }}", template)
        self.assertIn("status_labels", template)
        self.assertIn("push_labels", template)


if __name__ == "__main__":
    unittest.main()
