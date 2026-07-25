"""Printing: covers every scenario named in docs/print-layout.md's own
testing section, plus the pure helper functions directly."""

import re

import pytest

from app.models import Doctor, Summary
from app.printing import layout
from app.printing.printer import PrintUnsupportedError, print_pdf


def page_count(pdf_bytes):
    return len(re.findall(rb"/Type\s*/Page[^s]", pdf_bytes))


def test_format_date():
    assert layout.format_date("2026-01-22") == "22/01/2026"
    assert layout.format_date("") == "" and layout.format_date(None) == ""


def test_format_investigations():
    assert (
        layout.format_investigations([{"label": "FBS", "value": "86"}, {"label": "SCr", "value": "40"}])
        == "FBS 86 · SCr 40"
    )
    assert (
        layout.format_investigations(
            [{"label": "FBS", "value": "86"}, {"label": "K", "value": ""}, {"label": "Hb", "value": "11.7"}]
        )
        == "FBS 86 · Hb 11.7"
    ), "blank values skipped entirely"
    assert layout.format_investigations([]) == ""


def test_has_clinical_history():
    blank_summary = Summary(patient_name="", bht_number="")
    assert layout.has_clinical_history(blank_summary) is False

    one_filled = Summary(patient_name="", bht_number="", allergies="NKDA")
    assert layout.has_clinical_history(one_filled) is True

    findings_only = Summary(patient_name="", bht_number="", findings="Something found")
    assert layout.has_clinical_history(findings_only) is False, "Findings isn't part of the 5-field group"


def test_chunk_long_text():
    assert layout._chunk_long_text("short") == ["short"]
    long_text = "word " * 1000
    chunks = layout._chunk_long_text(long_text)
    assert len(chunks) > 1
    assert all(len(c) <= layout._MAX_CHARS_PER_ROW_CHUNK for c in chunks)
    assert abs(len("".join(chunks)) - len(long_text)) < len(chunks) * 2, "doesn't lose content"


@pytest.fixture
def full_summary():
    return Summary(
        id=1,
        patient_name="W.D. Kusuma Wijerathna",
        age=54,
        sex="Female",
        bht_number="10178",
        ward="45",
        telephone="0771234567",
        blood_group="O+",
        date_admission="2026-01-10",
        date_surgery="2026-01-12",
        date_discharge="2026-01-22",
        procedure_title="complete thyroidectomy under ga",
        surgical_team="Dr. S. Herath, Dr. N. Ratnayake",
        indication="Multinodular goitre",
        procedure_steps="1. GA induced.\n2. Collar incision.\n3. Both lobes mobilised.",
        findings="Multinodular goitre, no lymphadenopathy",
        presenting_complaint="Neck swelling",
        past_medical_history="DM type 2",
        past_surgical_history="Nil",
        allergies="NKDA",
        examination="Firm, non-tender mass",
        management="T. Paracetamol 1g PO PRN",
        histology_report="Benign multinodular goitre.",
    )


def test_full_record_renders_everything(tmp_path, full_summary):
    full_investigations = [
        {"label": "FBS", "value": "86", "unit": "mg/dL"},
        {"label": "SCr", "value": "40", "unit": "µmol/L"},
        {"label": "Hb", "value": "11.7", "unit": "g/dL"},
    ]
    doctor = Doctor(id=1, name="Dr. S. Herath", designation="SR Onco-surgery")

    path = layout.render_summary(full_summary, full_investigations, doctor, tmp_path)
    assert path.exists()
    content = path.read_bytes()
    assert content[:5] == b"%PDF-"
    assert b"Wijerathna" in content
    assert b"COMPLETE THYROIDECTOMY UNDER GA" in content
    assert b"O+" in content
    assert b"FBS 86" in content and b"SCr 40" in content and b"Hb 11.7" in content
    assert b"Findings" in content, "Findings appears as its own row, not folded into clinical history"
    assert b"Allergies" in content and b"NKDA" in content
    assert b"Dr. S. Herath" in content and b"SR Onco-surgery" in content
    assert page_count(content) == 1


def test_minimal_record_and_blank_clinical_history(tmp_path):
    minimal = Summary(id=2, patient_name="A.B. Perera", bht_number="10202")
    path2 = layout.render_summary(minimal, [], None, tmp_path)
    assert path2.exists()
    content2 = path2.read_bytes()
    assert b"Perera" in content2
    assert not any(
        m in content2
        for m in [b"Presenting Complaint", b"Past Medical History", b"Past Surgical History", b"Examination"]
    ), "blank clinical history: the 5-field group is entirely omitted"
    assert b"Allergies" not in content2

    path_zero = layout.render_summary(minimal, [], None, tmp_path)
    content_zero = path_zero.read_bytes()
    assert b"Investigations" in content_zero, "zero investigations: label still shown, blank value"


def test_long_procedure_text_forces_a_second_page(tmp_path):
    long_steps = "\n".join(f"{i}. Step {i} of the operative note, describing what was done." for i in range(1, 40))
    long_summary = Summary(
        id=4, patient_name="K.M. Silva", bht_number="10166", procedure_steps=long_steps, procedure_title="long procedure"
    )
    path4 = layout.render_summary(long_summary, [], None, tmp_path)
    content4 = path4.read_bytes()
    assert page_count(content4) == 2
    assert b"Page 1 of 2" in content4
    assert b"Page 2 of 2" in content4
    assert content4.count(b"SURGICAL ONCOLOGY UNIT") == 2, "header band repeats on the second page"


def test_extremely_long_procedure_text_does_not_crash(tmp_path):
    # Previously crashed with LayoutError before the chunking fix.
    extreme_steps = "\n".join(
        f"{i}. Extremely long step {i} describing in great detail exactly what was done during this part of the operation."
        for i in range(1, 150)
    )
    extreme_summary = Summary(
        id=5, patient_name="Extreme Case", bht_number="99999", procedure_steps=extreme_steps, procedure_title="extreme"
    )
    path5 = layout.render_summary(extreme_summary, [], None, tmp_path)
    assert path5.exists()


def test_non_ascii_and_xml_sensitive_characters_dont_break_rendering(tmp_path):
    non_ascii = Summary(
        id=6,
        patient_name="José García-Peña",
        bht_number="10300",
        management="T. Amoxicillin 500mg — café-au-lait rash noted, D/C'd",
        procedure_title="excision",
    )
    path6 = layout.render_summary(non_ascii, [], None, tmp_path)
    assert path6.exists()
    content6 = path6.read_bytes()
    assert len(content6) > 1000 and content6[:5] == b"%PDF-"

    # XML-sensitive characters (&, <, >) must not break Paragraph markup parsing.
    xml_chars = Summary(id=7, patient_name="Test <Patient> & Co", bht_number="10301", management="K+ <3.5 & rising", procedure_title="x")
    path7 = layout.render_summary(xml_chars, [], None, tmp_path)
    assert path7.exists()


def test_print_pdf_raises_clear_error_on_non_windows(tmp_path, full_summary):
    path = layout.render_summary(full_summary, [], None, tmp_path)
    with pytest.raises(PrintUnsupportedError):
        print_pdf(path)
