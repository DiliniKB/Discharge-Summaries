"""Procedure section: template insert (from the real DB), the
overwrite-confirmation guard, and Steps' auto-grow behavior."""

from PySide6.QtWidgets import QMessageBox

from app.db import templates as templates_db
from app.ui.sections import procedure as procedure_module
from app.ui.sections.procedure import TEMPLATE_PLACEHOLDER, ProcedureSection


def test_picker_starts_with_only_the_placeholder_until_set_templates(db_conn):
    sec = ProcedureSection()
    sec.show()

    assert sec._title.text() == "PROCEDURE"
    assert sec.expanded is True
    assert sec.template_picker.currentText() == TEMPLATE_PLACEHOLDER
    assert sec.template_picker.count() == 1, "no fixtures baked in — only the placeholder"
    assert sec.template_picker.parent() is sec.header_layout.parentWidget(), "picker lives in the header, not the body"
    assert sec.steps_input.toPlainText() == ""


def test_set_templates_populates_from_real_db_rows(db_conn):
    templates_db.seed_if_empty(db_conn)
    real_templates = templates_db.list_active(db_conn)
    assert len(real_templates) == 3

    sec = ProcedureSection()
    sec.set_templates(real_templates)

    assert sec.template_picker.count() == 1 + len(real_templates) + 1, "placeholder + templates + Manage sentinel"
    assert sec.template_picker.currentText() == TEMPLATE_PLACEHOLDER


def test_selecting_a_template_inserts_its_body_and_resets_the_picker(db_conn):
    templates_db.seed_if_empty(db_conn)
    real_templates = templates_db.list_active(db_conn)
    templates_by_name = {t.name: t.body for t in real_templates}

    sec = ProcedureSection()
    sec.set_templates(real_templates)
    sec.show()

    sec.template_picker.setCurrentText("Thyroid lobectomy")
    assert sec.steps_input.toPlainText() == templates_by_name["Thyroid lobectomy"]
    assert sec.template_picker.currentText() == TEMPLATE_PLACEHOLDER, "action, not a persistent selection"

    # Templates insert, they don't link — editing Steps afterward doesn't touch the DB row.
    sec.steps_input.setPlainText("edited by the user, freely")
    template_id = [t for t in real_templates if t.name == "Thyroid lobectomy"][0].id
    still_in_db = templates_db.get(db_conn, template_id)
    assert still_in_db.body == templates_by_name["Thyroid lobectomy"]


def test_overwrite_guard_asks_before_replacing_existing_steps(db_conn, monkeypatch):
    templates_db.seed_if_empty(db_conn)
    real_templates = templates_db.list_active(db_conn)
    templates_by_name = {t.name: t.body for t in real_templates}

    sec = ProcedureSection()
    sec.set_templates(real_templates)
    sec.show()
    sec.steps_input.setPlainText("doctor's own typed notes, not from a template")

    monkeypatch.setattr(procedure_module.QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.No))
    sec.template_picker.setCurrentText("Total mastectomy")
    assert sec.steps_input.toPlainText() == "doctor's own typed notes, not from a template", "declining leaves Steps untouched"
    assert sec.template_picker.currentText() == TEMPLATE_PLACEHOLDER, "picker resets even after declining"

    monkeypatch.setattr(procedure_module.QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.Yes))
    sec.template_picker.setCurrentText("Total mastectomy")
    assert sec.steps_input.toPlainText() == templates_by_name["Total mastectomy"], "accepting replaces Steps"


def test_steps_auto_grow_grows_floors_and_caps():
    sec = ProcedureSection()
    sec.show()
    height_empty = sec.steps_input.height()

    sec.steps_input.setPlainText("\n".join(f"line{i}" for i in range(1, 11)))
    height_full = sec.steps_input.height()
    assert height_full > height_empty, "grows taller as more lines are typed"

    sec2 = ProcedureSection()
    sec2.show()
    sec2.steps_input.setPlainText("just one line")
    # Floor is approximate (QFontMetrics estimate vs QTextEdit's actual
    # document rendering diverge by a few px) — what matters is it stays
    # near the floor for short content, not the 6-line cap.
    assert sec2.steps_input.height() < height_empty + 15

    sec3 = ProcedureSection()
    sec3.show()
    sec3.steps_input.setPlainText("\n".join(f"line{i}" for i in range(1, 30)))
    assert sec3.steps_input.height() == height_full, "capped, doesn't grow unbounded"
