"""Editor action bar + real DB wiring (card clicks -> load_summary,
+ New Card -> a real new row). Print itself has its own dedicated tests
in test_print_preview.py — not repeated here beyond confirming the shell
handlers (Duplicate/Delete) don't raise.
"""

from app.db import connection, summaries
from app.models import Summary
from app.ui.main_window import MainWindow


def _seed_two(isolated_data_dir):
    conn = connection.connect()
    first = summaries.create(conn, Summary(patient_name="W.D. Kusuma Wijerathna", bht_number="10178", ward="45", date_discharge="2026-01-22"))
    second = summaries.create(conn, Summary(patient_name="K.M. Silva", bht_number="10166", ward="45", date_discharge="2026-01-19"))
    connection.close(conn)
    return first, second


def test_action_bar_starts_with_no_summary_open(isolated_data_dir):
    _seed_two(isolated_data_dir)
    win = MainWindow()
    win.show()
    ed = win.editor

    assert ed.action_bar.height() == 64
    assert ed._name_label.text() == "No summary open"
    assert ed.print_button.isEnabled() is False
    assert ed.save_button.isEnabled() is False
    assert ed.overflow_button.isEnabled() is False
    assert ed._save_state_label.text() == ""
    assert len(win.patient_list._cards) == 2, "the 2 seeded summaries show on startup"

    win.close()


def test_clicking_a_card_loads_the_real_record_into_every_field(isolated_data_dir):
    _seed_two(isolated_data_dir)
    win = MainWindow()
    win.show()
    ed = win.editor

    card = win.patient_list._cards[0]
    win.patient_list._on_card_clicked(card)

    assert ed._name_label.text() == card.patient["patient_name"]
    assert ed._meta_label.text() == f"BHT {card.patient['bht_number']} · Ward {card.patient['ward']}"
    assert ed.print_button.isEnabled() is True
    assert ed.save_button.isEnabled() is True
    assert ed.overflow_button.isEnabled() is True
    assert ed._save_state_label.text() == "Not saved"

    assert ed.patient_section.name_input.text() == card.patient["patient_name"], "Name field populated from the real DB record"
    assert ed.patient_section.bht_input.text() == card.patient["bht_number"]

    # Select a different real card — breadcrumb and fields must update, not stick.
    card2 = win.patient_list._cards[1]
    win.patient_list._on_card_clicked(card2)
    assert ed._name_label.text() == card2.patient["patient_name"]
    assert ed.patient_section.name_input.text() == card2.patient["patient_name"]

    win.close()


def test_new_card_creates_a_real_row_loads_and_selects_it(isolated_data_dir):
    _seed_two(isolated_data_dir)
    win = MainWindow()
    win.show()
    ed = win.editor

    count_before = len(win.patient_list._cards)
    win._on_new_card()

    assert len(win.patient_list._cards) == count_before + 1
    assert ed._name_label.text() == "(unnamed)", "the new card is genuinely blank"
    assert win.patient_list._selected_id is not None, "selected in the list immediately"
    assert ed.print_button.isEnabled() and ed.save_button.isEnabled()

    row = summaries.get(win._conn, win.patient_list._selected_id)
    assert row is not None, "the new card is a genuine DB row, not just in-memory"

    win.close()


def test_overflow_menu_shells_dont_raise(isolated_data_dir):
    _seed_two(isolated_data_dir)
    win = MainWindow()
    win.show()
    ed = win.editor

    win.patient_list._on_card_clicked(win.patient_list._cards[0])

    menu = ed.overflow_button.menu()
    actions = [a.text() for a in menu.actions()]
    assert actions == ["Duplicate", "Delete"]

    ed._on_duplicate()
    ed._on_delete()  # documented no-ops for now — must not raise

    win.close()
