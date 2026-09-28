import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]


class ContentWorkspaceContractTests(unittest.TestCase):
    def read(self, relative: str) -> str:
        return (ROOT / relative).read_text(encoding="utf-8")

    def test_sidebar_has_single_content_entry(self):
        sidebar = self.read("templates/dashboard/^shared/sidebar/index.html")
        self.assertIn("<span>Контент</span>", sidebar)
        self.assertNotIn("<span>Каталог</span>", sidebar)

    def test_content_workspace_manages_categories_inline(self):
        template = self.read("templates/dashboard/publication/index.html")
        self.assertIn('name="action" value="create_category"', template)
        self.assertIn('name="action" value="update_category"', template)
        self.assertIn('name="action" value="delete_category"', template)
        self.assertIn("Рубрики и публикации разделены по сайтам", template)

    def test_content_workspace_is_site_scoped(self):
        template = self.read("templates/dashboard/publication/index.html")
        controller = self.read("views/dashboard/blog/views.py")
        self.assertIn('name="site_id"', template)
        self.assertIn('filters: dict = {"site_id": selected_site.id', controller)
        self.assertIn("Category.site_id == selected_site.id", controller)

    def test_publication_controller_handles_category_crud(self):
        controller = self.read("views/dashboard/blog/views.py")
        self.assertIn('if action == "create_category"', controller)
        self.assertIn('if action == "update_category"', controller)
        self.assertIn('if action == "delete_category"', controller)
        self.assertIn('filters["category_ids"]', controller)

    def test_parent_category_filter_includes_descendants(self):
        model = self.read("models/publication.py")
        self.assertIn('elif key == "category_ids" and value:', model)
        self.assertIn("cls.category_id.in_(value)", model)

    def test_publication_editor_is_focused_on_writing(self):
        template = self.read("templates/dashboard/publication/edit.html")
        controller = self.read("views/dashboard/blog/views.py")
        styles = self.read("templates/dashboard/publication/style.css")

        self.assertIn("publication-writing__document", template)
        self.assertIn("publication-settings-group", template)
        self.assertIn("publication-state-pill", template)
        self.assertIn("Предпросмотр", template)
        self.assertIn("<details class=\"publication-settings-group\" open>", template)
        self.assertIn("publication-body-field .ql-toolbar.ql-snow", styles)
        self.assertIn('url_for("admin.publication.preview"', controller)
        self.assertIn("data-open-media", template)
        self.assertIn("data-profile-settings", template)
        self.assertIn("beforeunload", template)

    def test_legacy_catalog_redirects_to_content(self):
        legacy = self.read("views/dashboard/catalog/views.py")
        self.assertIn('url_for("admin.publication.index"', legacy)


if __name__ == "__main__":
    unittest.main()
