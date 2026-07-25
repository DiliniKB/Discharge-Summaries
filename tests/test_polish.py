"""Focus rings, keyboard shortcuts, and cross-section tab order
(including skipping collapsed sections) — docs/ui-spec.md §7.

qapp.processEvents() after every simulated key event/focus change is
required, not decorative — Qt needs the pump to actually settle
focus/signal state before the next assertion; omitting it caused a hard
process abort during initial conversion to pytest (calling QTest.keyClick
on a stale/None focusWidget()).

QTest.qWaitForWindowActive(win) after show() is also required, not just
show()+processEvents() — real OS-level keyboard/focus delivery only
targets the *activated* window. With only one window in a solo test run
this settles fast enough to pass by luck; once other tests in the same
session have left other top-level widgets open, activation of a freshly
shown window is no longer guaranteed without explicitly waiting for it,
and QTest.keyClick/keySequence then silently deliver to nothing (a stale
or None focusWidget()).
"""

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence
from PySide6.QtTest import QTest

from app import theme
from app.ui.widgets.autogrow_textedit import AutoGrowTextEdit


def test_autogrow_textedit_tab_changes_focus_not_inserts_a_character():
    edit = AutoGrowTextEdit()
    assert edit.tabChangesFocus() is True


def test_qtoolbutton_focus_style_exists_in_the_stylesheet():
    assert "QToolButton:focus" in theme.build_stylesheet()


def test_ctrl_p_and_ctrl_s_do_nothing_with_no_summary_open(isolated_data_dir, qapp):
    from app.ui.main_window import MainWindow

    win = MainWindow()
    win.show()
    win.raise_()
    win.activateWindow()
    QTest.qWaitForWindowActive(win)
    qapp.processEvents()

    print_clicked = {"count": 0}
    save_clicked = {"count": 0}
    win.editor.print_button.clicked.connect(lambda: print_clicked.__setitem__("count", print_clicked["count"] + 1))
    win.editor.save_button.clicked.connect(lambda: save_clicked.__setitem__("count", save_clicked["count"] + 1))

    QTest.keySequence(win, QKeySequence("Ctrl+P"))
    QTest.keySequence(win, QKeySequence("Ctrl+S"))
    qapp.processEvents()
    assert print_clicked["count"] == 0, "Print disabled with no summary open"
    assert save_clicked["count"] == 0, "Save disabled with no summary open"

    win.close()


def test_ctrl_n_opens_a_real_summary_then_ctrl_p_and_ctrl_s_fire(isolated_data_dir, qapp):
    from app.ui.main_window import MainWindow

    win = MainWindow()
    win.show()
    win.raise_()
    win.activateWindow()
    QTest.qWaitForWindowActive(win)
    qapp.processEvents()

    print_clicked = {"count": 0}
    save_clicked = {"count": 0}
    new_card_clicked = {"count": 0}
    win.editor.print_button.clicked.connect(lambda: print_clicked.__setitem__("count", print_clicked["count"] + 1))
    win.editor.save_button.clicked.connect(lambda: save_clicked.__setitem__("count", save_clicked["count"] + 1))
    win.patient_list.new_card_button.clicked.connect(lambda: new_card_clicked.__setitem__("count", new_card_clicked["count"] + 1))

    QTest.keySequence(win, QKeySequence("Ctrl+N"))
    qapp.processEvents()
    assert new_card_clicked["count"] == 1
    assert win.editor.print_button.isEnabled(), "Ctrl+N genuinely opened a summary"

    QTest.keySequence(win, QKeySequence("Ctrl+P"))
    QTest.keySequence(win, QKeySequence("Ctrl+S"))
    qapp.processEvents()
    assert print_clicked["count"] == 1
    assert save_clicked["count"] == 1

    win.close()


def test_ctrl_f_focuses_search_and_esc_clears_it(isolated_data_dir, qapp):
    from app.ui.main_window import MainWindow

    win = MainWindow()
    win.show()
    win.raise_()
    win.activateWindow()
    QTest.qWaitForWindowActive(win)
    qapp.processEvents()
    win.editor.setFocus()  # move focus away first, so Ctrl+F moving it is provable
    qapp.processEvents()

    QTest.keySequence(win, QKeySequence("Ctrl+F"))
    qapp.processEvents()
    assert qapp.focusWidget() is win.patient_list.search_box

    win.patient_list.search_box.setText("silva")
    QTest.keySequence(win, QKeySequence(Qt.Key_Escape))
    qapp.processEvents()
    assert win.patient_list.search_box.text() == ""

    win.close()


def test_cross_section_tab_order_skips_collapsed_sections(isolated_data_dir, qapp):
    from app.ui.main_window import MainWindow

    win = MainWindow()
    win.show()
    win.raise_()
    win.activateWindow()
    QTest.qWaitForWindowActive(win)
    qapp.processEvents()
    ed = win.editor

    named = {
        id(ed.patient_section.discharge_date.line): "patient:discharge_date",
        id(ed.procedure_section.template_picker): "procedure:template_picker",
        id(ed.procedure_section.title_input): "procedure:title",
        id(ed.procedure_section.team_input): "procedure:team",
        id(ed.procedure_section.indication_input): "procedure:indication",
        id(ed.procedure_section.steps_input): "procedure:steps",
        id(ed.investigations_section.analyte_inputs["FBS"]): "investigations:FBS",
    }
    for name, box in ed.clinical_history_section.__dict__.items():
        if hasattr(box, "toPlainText"):
            named[id(box)] = f"UNEXPECTED-CLINICAL-HISTORY:{name}"
    if hasattr(ed.attachments_section, "add_file_button"):
        named[id(ed.attachments_section.add_file_button)] = "UNEXPECTED-ATTACHMENTS:add_file_button"

    ed.patient_section.discharge_date.line.setFocus()
    qapp.processEvents()
    current = qapp.focusWidget()
    assert current is not None, "discharge_date must actually hold focus before tabbing from it"
    trace = ["patient:discharge_date"]
    landed_on_procedure_title = False
    for _ in range(6):
        QTest.keyClick(current, Qt.Key_Tab)
        qapp.processEvents()
        current = qapp.focusWidget()
        if current is None:
            trace.append("NONE")
            break
        label = named.get(id(current), f"UNKNOWN:{type(current).__name__}")
        trace.append(label)
        if label == "procedure:title":
            landed_on_procedure_title = True
            break

    assert landed_on_procedure_title, f"Tab from Patient's last field should reach Procedure's Title (got: {' -> '.join(trace)})"
    assert not any("UNEXPECTED-CLINICAL-HISTORY" in t for t in trace), "collapsed Clinical History must be skipped"

    for _ in range(6):
        QTest.keyClick(current, Qt.Key_Tab)
        qapp.processEvents()
        current = qapp.focusWidget()
        if current is None:
            trace.append("NONE")
            break
        label = named.get(id(current), f"UNKNOWN:{type(current).__name__}")
        trace.append(label)
        if label == "investigations:FBS":
            break

    assert trace[-1] == "investigations:FBS", f"Tab should eventually reach Investigations (got: {' -> '.join(trace)})"
    assert not any("UNEXPECTED-CLINICAL-HISTORY" in t for t in trace)

    win.close()
