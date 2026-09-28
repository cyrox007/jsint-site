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
        self.assertIn("PublicationChannelService.list_for_admin", controller)
        self.assertIn("site_id=selected_site.id", controller)
        self.assertIn("Category.site_id == selected_site.id", controller)

    def test_publication_controller_handles_category_crud(self):
        controller = self.read("views/dashboard/blog/views.py")
        self.assertIn('if action == "create_category"', controller)
        self.assertIn('if action == "update_category"', controller)
        self.assertIn('if action == "delete_category"', controller)
        self.assertIn("category_ids=category_ids", controller)

    def test_parent_category_filter_includes_descendants(self):
        model = self.read("models/publication.py")
        self.assertIn('elif key == "category_ids" and value:', model)
        self.assertIn("cls.category_id.in_(value)", model)

    def test_publication_editor_is_focused_on_writing(self):
        template = self.read("templates/dashboard/publication/edit.html")
        controller = self.read("views/dashboard/blog/views.py")
        styles = self.read("templates/dashboard/publication/style.css")
        editor = self.read("templates/dashboard/^elements/UI/Editor/index.html")

        self.assertIn("publication-writing__document", template)
        self.assertIn("publication-settings-group", template)
        self.assertIn("publication-state-pill", template)
        self.assertIn("Предпросмотр", template)
        self.assertIn("<details class=\"publication-settings-group\" open>", template)
        self.assertIn("publication-body-field .ql-toolbar.ql-snow", styles)
        self.assertIn("Введите название публикации", template)
        self.assertIn("Основной текст публикации", template)
        self.assertNotIn('data-open-media>', template)
        self.assertIn("Изображение из медиатеки", editor)
        self.assertNotIn("Основные поля находятся здесь, чтобы не отвлекать от текста.", template)
        self.assertIn("min-height:360px", styles)
        self.assertNotIn("min-height:520px", styles)
        self.assertNotIn("font-size:clamp(1.9rem,3vw,2.75rem)", styles)
        self.assertIn('url_for("admin.publication.preview"', controller)
        self.assertIn("data-open-media", template)
        self.assertIn("data-profile-settings", template)
        self.assertIn("profile_schemas_by_site", controller)
        self.assertIn("placement_{{ target_site.id }}_profile_", template)
        self.assertIn("ql-undo", editor)
        self.assertIn("ql-redo", editor)
        self.assertIn('data-more-format="strike"', editor)
        self.assertIn('data-more-format="script" data-more-value="sub"', editor)
        self.assertIn('data-more-format="script" data-more-value="super"', editor)
        self.assertIn("jsint-editor-more__menu", editor)
        self.assertIn("jsint-editor-bubble", editor)
        self.assertIn('data-bubble-format="bold"', editor)
        self.assertIn("ql-media", editor)
        self.assertIn("ql-fullscreen", editor)
        self.assertIn("getSemanticHTML", editor)
        self.assertIn("data-editor-count", editor)
        self.assertIn("history:", editor)
        self.assertIn("jsint-editor-media-request", editor)
        self.assertIn("form.requestSubmit()", template)
        self.assertIn("rich-editor-fullscreen-open", styles)
        self.assertIn("jsint-editor-separator", styles)
        self.assertIn("jsint-editor-more__menu", styles)
        self.assertIn("jsint-editor-bubble", styles)
        self.assertIn("beforeunload", template)

    def test_legacy_catalog_redirects_to_content(self):
        legacy = self.read("views/dashboard/catalog/views.py")
        self.assertIn('url_for("admin.publication.index"', legacy)


if __name__ == "__main__":
    unittest.main()
