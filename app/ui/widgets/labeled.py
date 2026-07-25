"""Label-above-input pairing. Every field label must be persistent and
visible — no placeholder-only labelling (docs/ui-spec.md §8).
"""

from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from app import theme


class LabeledField(QWidget):
    def __init__(self, label_text, input_widget, required=False, parent=None):
        super().__init__(parent)
        self.input = input_widget

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        text = label_text
        if required:
            text += f' <span style="color:{theme.DANGER}">*</span>'

        self.label = QLabel(text)
        self.label.setObjectName("Muted")  # "Field label 13px Regular, muted" — docs/ui-spec.md §6
        layout.addWidget(self.label)
        layout.addWidget(input_widget)
