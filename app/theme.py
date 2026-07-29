"""QSS stylesheet + palette — all colour/type tokens live here. See docs/ui-spec.md §6.

Variants are targeted by objectName, QSS's equivalent of a CSS class:
a widget wanting the "Primary" button style calls setObjectName("Primary").
Applied once via apply_theme(app) at startup — one stylesheet, one source
of truth, same reasoning as the old ttk.Style() token file.
"""

# --- Colour tokens (docs/ui-spec.md §6) ------------------------------------

BG = "#F7F8FA"
SURFACE = "#FFFFFF"
BORDER = "#D8DCE3"
TEXT = "#1A1D23"
TEXT_MUTED = "#6B7280"
PRIMARY = "#1D6FD0"
PRIMARY_TINT = "#E8F1FC"
DANGER = "#C0392B"
DANGER_TINT = "#FBEAEA"  # pairs with DANGER the same way PRIMARY_TINT pairs with PRIMARY — used once, for the Full View allergy alert
SUCCESS = "#2E7D4F"

# --- Type -------------------------------------------------------------------

FONT_FAMILY = "Segoe UI"  # ships with Windows 10; substituted on other platforms

SIZE_SECTION_HEADER = 13
SIZE_FIELD_LABEL = 13
SIZE_INPUT = 14  # was 16 — felt oversized/spacious for a form doctors fill quickly between patients (docs/decisions.md)
SIZE_PATIENT_NAME = 15
SIZE_METADATA = 13
SIZE_PROCEDURE_TITLE = 18
SIZE_HEADER_TITLE = 14

# --- Spacing ------------------------------------------------------------

SPACING_UNIT = 4
SECTION_PADDING = 20
FIELD_GAP = 16
INPUT_HEIGHT_PX = 34  # was 40 — same "denser, less air per field" reasoning as SIZE_INPUT
INPUT_PADDING_X = 12
TABLE_ITEM_PADDING_Y = 6  # QTableWidget::item's own vertical padding, below — named so
                          # app/ui/dialogs/advanced_search.py can size row height/cell
                          # widgets against it instead of a second hardcoded copy of "6".
CORNER_RADIUS = 4  # real this time — QSS supports border-radius, unlike ttk

# Field width tiers — a fixed set, not one-off pixel values per field.
# Same-class fields (Sex/Blood Group, BHT/dates) should share a tier so the
# form reads as designed rather than each field guessed independently.
WIDTH_XS = 64   # 2-digit codes: Age, Ward
WIDTH_S = 110   # short codes: Sex, Blood Group
WIDTH_M = 160   # medium identifiers: BHT Number, date fields
WIDTH_TELEPHONE = 220  # phone numbers don't fit the tiers above


def _hover(hex_color, amount=0.08):
    """Darken a hex colour slightly, for hover/pressed states."""
    hex_color = hex_color.lstrip("#")
    r, g, b = (int(hex_color[i : i + 2], 16) for i in (0, 2, 4))
    r, g, b = (max(0, int(c * (1 - amount))) for c in (r, g, b))
    return f"#{r:02X}{g:02X}{b:02X}"


def build_stylesheet():
    return f"""
    QWidget {{
        background: {BG};
        color: {TEXT};
        font-family: "{FONT_FAMILY}";
        font-size: {SIZE_INPUT}px;
    }}

    QFrame#Surface, QWidget#Surface {{
        background: {SURFACE};
    }}
    QFrame#Header {{
        background: {SURFACE};
        border: none;
        border-bottom: 1px solid {BORDER};
    }}

    QLabel {{
        background: transparent;
        font-size: {SIZE_FIELD_LABEL}px;
    }}
    QLabel#Muted {{
        color: {TEXT_MUTED};
        font-size: {SIZE_METADATA}px;
    }}
    QLabel#Danger {{
        color: {DANGER};
        font-size: {SIZE_METADATA}px;
    }}
    QLabel#SectionHeader {{
        color: {TEXT};
        font-size: {SIZE_SECTION_HEADER}px;
        font-weight: 600;
        letter-spacing: 1px;
    }}
    QLabel#HeaderTitle {{
        background: {SURFACE};
        color: {TEXT};
        font-size: {SIZE_HEADER_TITLE}px;
        font-weight: 600;
    }}
    QLabel#PatientName {{
        color: {TEXT};
        font-size: {SIZE_PATIENT_NAME}px;
        font-weight: 600;
    }}
    QLabel#ProcedureTitle {{
        color: {TEXT};
        font-size: {SIZE_PROCEDURE_TITLE}px;
        font-weight: 600;
    }}

    /* Full View dialog only (app/ui/dialogs/summary_full_view.py) — the
       one place in the app that gets a "hero" treatment, since it's a
       dedicated detail view, not a form to fill in. */
    QFrame#HeroCard {{
        background: {PRIMARY_TINT};
        border-radius: {CORNER_RADIUS * 2}px;
        border: none;
    }}
    QLabel#HeroName {{
        color: {TEXT};
        font-size: 20px;
        font-weight: 700;
    }}
    QFrame#AlertCard {{
        background: {DANGER_TINT};
        border: 1px solid {DANGER};
        border-radius: {CORNER_RADIUS}px;
    }}
    QLabel#AlertText {{
        color: {DANGER};
        font-size: {SIZE_INPUT}px;
        font-weight: 600;
    }}

    QLineEdit, QComboBox {{
        background: {SURFACE};
        color: {TEXT};
        border: 1px solid {BORDER};
        border-radius: {CORNER_RADIUS}px;
        padding: 0 {INPUT_PADDING_X}px;
        min-height: {INPUT_HEIGHT_PX}px;
        selection-background-color: {PRIMARY_TINT};
        selection-color: {TEXT};
    }}
    QLineEdit:focus, QComboBox:focus {{
        border: 2px solid {PRIMARY};
    }}
    /* Investigations section only (app/ui/sections/investigations.py) —
       a value outside the general adult reference range (app/util/lab_ranges.py).
       A prompt to double-check, not a block on saving — the field still
       accepts and persists whatever was typed. */
    QLineEdit[abnormal="true"] {{
        border: 2px solid {DANGER};
        background: {DANGER_TINT};
    }}
    /* Name/Telephone/BHT format validation (app/ui/sections/patient.py,
       app/util/validators.py) — unlike [abnormal], this one DOES block
       the save for that field until fixed, a deliberate departure from
       this app's usual warn-don't-block precedent (docs/decisions.md).
       Same visual language as [abnormal] since both mean "look at this
       field," just a different property name for a different meaning. */
    QLineEdit[invalid="true"] {{
        border: 2px solid {DANGER};
        background: {DANGER_TINT};
    }}
    /* Narrow numeric boxes (DateField) — the standard 12px input padding
       above leaves almost no room for 2-4 digits at this width. */
    QLineEdit#DateBox {{
        background: {SURFACE};
        color: {TEXT};
        border: 1px solid {BORDER};
        border-radius: {CORNER_RADIUS}px;
        padding: 0 6px;
        min-height: {INPUT_HEIGHT_PX}px;
        selection-background-color: {PRIMARY_TINT};
        selection-color: {TEXT};
    }}
    QLineEdit#DateBox:focus {{
        border: 2px solid {PRIMARY};
    }}

    /* "Procedure title input 18px Semibold" — docs/ui-spec.md §6 */
    QLineEdit#ProcedureTitleInput {{
        background: {SURFACE};
        color: {TEXT};
        border: 1px solid {BORDER};
        border-radius: {CORNER_RADIUS}px;
        padding: 0 {INPUT_PADDING_X}px;
        min-height: {INPUT_HEIGHT_PX}px;
        font-size: {SIZE_PROCEDURE_TITLE}px;
        font-weight: 600;
        selection-background-color: {PRIMARY_TINT};
        selection-color: {TEXT};
    }}
    QLineEdit#ProcedureTitleInput:focus {{
        border: 2px solid {PRIMARY};
    }}

    QTextEdit {{
        background: {SURFACE};
        color: {TEXT};
        border: 1px solid {BORDER};
        border-radius: {CORNER_RADIUS}px;
        padding: 8px {INPUT_PADDING_X}px;
        selection-background-color: {PRIMARY_TINT};
        selection-color: {TEXT};
    }}
    QTextEdit:focus {{
        border: 2px solid {PRIMARY};
    }}

    QComboBox::drop-down {{
        border: none;
        width: 24px;
    }}
    QComboBox QAbstractItemView {{
        background: {SURFACE};
        border: 1px solid {BORDER};
        selection-background-color: {PRIMARY_TINT};
        selection-color: {TEXT};
        outline: none;
    }}

    QPushButton {{
        border-radius: {CORNER_RADIUS}px;
        padding: 8px {INPUT_PADDING_X}px;
        font-size: {SIZE_FIELD_LABEL}px;
        border: 1px solid transparent;
    }}
    QPushButton#Primary {{
        background: {PRIMARY};
        color: {SURFACE};
    }}
    QPushButton#Primary:hover {{
        background: {_hover(PRIMARY)};
    }}
    QPushButton#Primary:pressed {{
        background: {_hover(PRIMARY, 0.16)};
    }}
    QPushButton#Secondary {{
        background: {SURFACE};
        color: {TEXT};
        border: 1px solid {BORDER};
    }}
    QPushButton#Secondary:hover {{
        background: {_hover(SURFACE, 0.04)};
    }}
    QPushButton#Danger {{
        background: {SURFACE};
        color: {DANGER};
        border: 1px solid {DANGER};
    }}
    QPushButton#Danger:hover {{
        background: {_hover(SURFACE, 0.04)};
    }}
    QPushButton:focus {{
        border: 2px solid {PRIMARY};
    }}

    /* Compact variants — action bars with two stacked rows in a fixed
       height (docs/ui-spec.md §3.3) can't afford the standard 40px input
       height's padding. #Primary/#Secondary stay full-size for New Card. */
    QPushButton#PrimaryCompact {{
        background: {PRIMARY};
        color: {SURFACE};
        border-radius: {CORNER_RADIUS}px;
        padding: 4px {INPUT_PADDING_X}px;
        font-size: {SIZE_FIELD_LABEL}px;
        border: 1px solid transparent;
    }}
    QPushButton#PrimaryCompact:hover {{
        background: {_hover(PRIMARY)};
    }}
    QPushButton#PrimaryCompact:pressed {{
        background: {_hover(PRIMARY, 0.16)};
    }}
    QPushButton#SecondaryCompact {{
        background: {SURFACE};
        color: {TEXT};
        border: 1px solid {BORDER};
        border-radius: {CORNER_RADIUS}px;
        padding: 4px {INPUT_PADDING_X}px;
        font-size: {SIZE_FIELD_LABEL}px;
    }}
    QPushButton#SecondaryCompact:hover {{
        background: {_hover(SURFACE, 0.04)};
    }}
    QPushButton#PrimaryCompact:disabled, QPushButton#SecondaryCompact:disabled {{
        background: {BG};
        color: {TEXT_MUTED};
        border-color: {BORDER};
    }}
    QPushButton#PrimaryCompact:focus, QPushButton#SecondaryCompact:focus {{
        border: 2px solid {PRIMARY};
    }}

    QToolButton {{
        background: transparent;
        border: none;
        border-radius: {CORNER_RADIUS}px;
        padding: 4px 8px;
        font-size: {SIZE_PROCEDURE_TITLE}px;
        color: {TEXT_MUTED};
    }}
    QToolButton:hover {{
        background: {BG};
    }}
    QToolButton:disabled {{
        color: {BORDER};
    }}
    QToolButton:focus {{
        border: 2px solid {PRIMARY};
    }}
    QToolButton::menu-indicator {{
        image: none;
        width: 0;
    }}

    QFrame#Card {{
        background: {SURFACE};
        border: 1px solid {BORDER};
        border-radius: {CORNER_RADIUS}px;
    }}

    QFrame#DropZone {{
        background: {BG};
        border: 1px dashed {BORDER};
        border-radius: {CORNER_RADIUS}px;
    }}

    QFrame#PatientCard {{
        background: {SURFACE};
        border: none;
        border-bottom: 1px solid {BORDER};
        border-left: 3px solid transparent;
    }}
    QFrame#PatientCard:hover {{
        background: {BG};
    }}
    QFrame#PatientCard[selected="true"] {{
        background: {PRIMARY_TINT};
        border-left: 3px solid {PRIMARY};
    }}

    QTableWidget {{
        background: {SURFACE};
        border: 1px solid {BORDER};
        border-radius: {CORNER_RADIUS}px;
        gridline-color: {BORDER};
        selection-background-color: {PRIMARY_TINT};
        selection-color: {TEXT};
    }}
    QTableWidget::item {{
        padding: {TABLE_ITEM_PADDING_Y}px {INPUT_PADDING_X}px;
        border: none;
    }}
    QTableWidget::item:alternate {{
        background: {BG};
    }}
    QHeaderView::section {{
        background: {SURFACE};
        color: {TEXT_MUTED};
        font-size: {SIZE_METADATA}px;
        font-weight: 600;
        padding: 8px {INPUT_PADDING_X}px;
        border: none;
        border-bottom: 1px solid {BORDER};
        border-right: 1px solid {BORDER};
    }}
    QHeaderView::section:last {{
        border-right: none;
    }}

    QScrollArea {{
        border: none;
    }}
    QScrollBar:vertical {{
        background: {BG};
        width: 12px;
        margin: 0;
    }}
    QScrollBar::handle:vertical {{
        background: {BORDER};
        border-radius: {CORNER_RADIUS}px;
        min-height: 24px;
    }}
    QScrollBar::handle:vertical:hover {{
        background: {TEXT_MUTED};
    }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
        height: 0;
    }}
    """


def apply_theme(app):
    """Apply the token set to a QApplication. Call once at startup."""
    app.setStyleSheet(build_stylesheet())
