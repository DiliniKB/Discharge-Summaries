# Print layout

The A4 discharge card. This is the deliverable the unit actually cares about — everything else exists to produce it.

Implemented in `app/printing/layout.py` using ReportLab. Dispatched to the printer by `app/printing/printer.py`.

---

## Status

**Not signed off.** The layout below is a redesign of the original green form, not a pixel reproduction. It needs checking against a real paper card by ward staff before the unit adopts it. See "Divergences" below for exactly what changed and why.

If staff reject it, reverting to an exact reproduction is a change confined to `layout.py`.

---

## Page setup

| Property | Value |
|---|---|
| Size | A4 portrait (210 × 297 mm) |
| Margins | 15 mm all sides |
| Body font | Helvetica 9.5 pt |
| Label font | Helvetica 9.5 pt on light grey fill |
| Heading font | Helvetica-Bold 11 pt |
| Line spacing | 1.45 |

Helvetica is a ReportLab base font — no font file to embed, nothing to install on the target machine.

---

## Structure

```
┌────────────────────────────────────────────────────────────┐
│   SURGICAL ONCOLOGY UNIT — TEACHING HOSPITAL, KURUNEGALA   │  bordered band
├──────────────────────────────────┬─────────────────────────┤
│        DISCHARGE SUMMARY         │        WARD 45          │  two bordered cells
└──────────────────────────────────┴─────────────────────────┘

┌───────────────┬──────────────┬────────────────┬────────────┐
│ Name          │ ...          │ Date of adm.   │ ...        │  two-column
│ Telephone     │ ...          │ Date of disch. │ ...        │  identity block
│ Age           │ ...          │ Date of surg.  │ ...        │
│ Sex           │ ...          │ Blood group    │ ...        │
│ BHT number    │ ...          │                │            │
└───────────────┴──────────────┴────────────────┴────────────┘

              COMPLETE THYROIDECTOMY UNDER GA                    centred, bold

┌───────────────┬────────────────────────────────────────────┐
│ Surgical team │ ...                                        │
│ Indication    │ ...                                        │
│ Procedure     │ (multi-line, wraps)                        │
│ Presenting…   │ (omitted if blank)                         │
│ Past medical… │ (omitted if blank)                         │
│ …             │                                            │
│ Investigations│ FBS 86 · SCr 40 · AST 20 · Na 138 …        │
│ Management    │ (multi-line)                               │
│ Histology     │ ...                                        │
└───────────────┴────────────────────────────────────────────┘

                                    ─────────────────────
                                    Dr. S. Herath
                                    SR Onco-surgery

Printed on 24/07/2026 14:32                        Page 1 of 1
```

Label column: 34 mm. Value column: remainder.

---

## Field mapping

Paper form field → database column.

| On the card | Column | Notes |
|---|---|---|
| Name | `patient_name` | |
| Telephone Number | `telephone` | |
| Age | `age` | |
| Sex | `sex` | |
| BHT Number | `bht_number` | |
| Date of Admission | `date_admission` | ISO → DD/MM/YYYY |
| Date of Discharge | `date_discharge` | ISO → DD/MM/YYYY |
| Date of Surgery | `date_surgery` | ISO → DD/MM/YYYY |
| Blood group | `blood_group` | **New** — was handwritten in the margin |
| *(operation title)* | `procedure_title` | Centred, bold, uppercase |
| Surgical Team | `surgical_team` | |
| Indication | `indication` | |
| Procedure | `procedure_steps` | Line breaks preserved |
| Findings | `findings` | |
| Presenting Complaint | `presenting_complaint` | |
| Past Medical History | `past_medical_history` | |
| Past Surgical History | `past_surgical_history` | |
| Allergies | `allergies` | |
| Examination | `examination` | |
| Investigations | `investigations` table | Joined, blanks skipped |
| Management | `management` | Line breaks preserved |
| Histology Report | `histology_report` | |
| *(signature)* | `created_by` → doctors | Name + designation |

Row order follows the paper form so staff can read old and new cards interchangeably. **Don't reorder without asking the unit.**

---

## Divergences from the green form

Four deliberate changes. Each needs sign-off.

### 1. Blank fields collapse

**Paper:** every field gets fixed vertical space whether filled or not. On the sample card, six clinical-history rows were empty and consumed roughly a third of the page.

**Here:** a blank field prints as a thin labelled row, or is omitted entirely if the whole clinical-history block is empty.

**Why:** keeps a typical summary on one page. The paper version risks spilling to a second.

**Risk:** staff who scan for a field by its position on the page lose that muscle memory. Worth asking about directly.

### 2. Blood group added

Handwritten into the margin on the sample card, which means the form was missing something people need. Now a proper field in the identity block.

### 3. Investigations print inline

**Paper:** free-text block, one analyte per line, seven lines.

**Here:** `FBS 86 · SCr 40 · AST 20 · Na 138 · K 4 · Hb 11.7`, wrapping as needed. Blank analytes are skipped.

**Why:** saves five or six lines with no loss of information.

**Revert easily:** one line in `layout.py` switches back to one-per-line.

### 4. Signature block

**Paper:** no printed signing officer.

**Here:** the doctor from the header dropdown prints with a rule above the name.

**Why:** this is the app's accountability mechanism — attribution as a field on the record rather than a login system. See `decisions.md`.

---

## Overflow

A long procedure note or histology report can exceed one page.

- ReportLab flows to a second page automatically.
- The header band repeats.
- The footer reads `Page 2 of 2`.
- **Never split a label row from its value.** Use `KeepTogether` on each row.

---

## Printing

```python
pdf_path = render_summary(summary, tmp_dir)
os.startfile(pdf_path, "print")
```

`os.startfile` with the `print` verb hands the file to the shell, which uses the default PDF handler and the default printer. No printer driver code, no dialog to maintain.

**Trade-offs, accepted:**
- Requires a default printer to be set. If none is, nothing happens — hence the troubleshooting entry in `deployment.md`.
- Copies and printer selection in the preview dialog are advisory; the shell handler decides.
- Windows-only. Fine — the target is one Windows laptop.

PDFs render to a temp file, not to memory, and are released after dispatch. On a 4 GB machine, holding rendered pages is avoidable waste.

---

## Preview

`app/ui/dialogs/print_preview.py` renders **the actual generated PDF**, scaled to fit, not an HTML approximation. What's on screen is what leaves the printer.

The current paper process has no preview at all, so a misprint wastes a form. This is the highest-value addition beyond storage.

---

## Testing

`tests/test_printing.py` covers, with fictional data:

- A summary with every field populated
- A summary with only the required fields
- Clinical history entirely blank (the common case)
- Procedure text long enough to force a second page
- Names and drug lists containing non-ASCII characters
- Zero investigations

Render to PDF and assert page count and that key strings are present. Rendering is fast; there's no reason to skip these.

---

## Open questions

1. **Does the unit accept a redesigned layout, or must it reproduce the green form exactly?** Blocks sign-off.
2. **S Ca units** — mmol/L assumed. Confirm with the lab.
3. **Does the card need a hospital logo or letterhead?** Not on the sample.
4. **Is one copy enough,** or does the unit file a duplicate?
