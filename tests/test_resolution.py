"""Full-window integration check at the actual target resolution,
1366x768 — not a maximized dev-machine window. docs/deployment.md /
CLAUDE.md: the target is a 1366x768 laptop."""

from app.db import connection, summaries
from app.models import Summary


def _seed_one(isolated_data_dir):
    conn = connection.connect()
    summaries.create(conn, Summary(patient_name="Test Patient", bht_number="10178", ward="45"))
    connection.close(conn)


def test_window_actually_resizes_to_1366x768_above_the_enforced_minimum(isolated_data_dir):
    from app.ui.main_window import MIN_HEIGHT, MIN_WIDTH, MainWindow

    win = MainWindow()
    win.resize(1366, 768)
    win.show()

    assert win.width() == 1366 and win.height() == 768
    assert 1366 >= MIN_WIDTH and 768 >= MIN_HEIGHT

    win.close()


def test_no_horizontal_overflow_with_every_section_open_at_target_resolution(isolated_data_dir):
    _seed_one(isolated_data_dir)
    from app.ui.main_window import MainWindow

    win = MainWindow()
    win.resize(1366, 768)
    win.show()

    card = win.patient_list._cards[0]
    win.patient_list._on_card_clicked(card)

    ed = win.editor
    if not ed.clinical_history_section.expanded:
        ed.clinical_history_section._toggle()
    if not ed.attachments_section.expanded:
        ed.attachments_section._toggle()

    # No horizontal scrollbar should ever appear — confirming the policy
    # itself, since Qt would just clip rather than show one, silently
    # hiding an overflow bug.
    assert ed.sections_area.horizontalScrollBarPolicy().name == "ScrollBarAlwaysOff"

    assert win.list_pane.width() == 280

    widest_row_widgets = [
        ("Patient identity row (Age/Sex/BHT/Ward)", ed.patient_section.ward_input),
        ("Patient contact row (Telephone/Blood Group)", ed.patient_section.blood_group_input),
        ("Patient dates row", ed.patient_section.discharge_date),
        ("Investigations row 2 (K/S Ca/Hb/+Other)", ed.investigations_section.add_other_button),
    ]
    for label, rightmost_widget in widest_row_widgets:
        right_edge = rightmost_widget.mapTo(ed.sections_area.body, rightmost_widget.rect().bottomRight()).x()
        assert right_edge <= ed.sections_area.viewport().width(), f"{label} overflows the viewport"

    assert win.header.height() == 56, "header holds its fixed height at any resolution above minimum"
    assert ed.action_bar.height() == 64

    # With 5 sections open at once, content should genuinely exceed the
    # viewport — confirms scrolling is actually exercised, not just
    # theoretically available.
    assert ed.sections_area.body.height() > ed.sections_area.viewport().height()

    win.close()


def test_holds_at_the_absolute_minimum_size_too(isolated_data_dir):
    _seed_one(isolated_data_dir)
    from app.ui.main_window import MainWindow

    win = MainWindow()
    win.resize(1280, 720)
    win.show()
    card = win.patient_list._cards[0]
    win.patient_list._on_card_clicked(card)

    assert win.width() == 1280 and win.height() == 720
    assert win.list_pane.width() == 280

    win.close()
