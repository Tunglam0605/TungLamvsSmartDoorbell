from PySide6 import QtCore, QtWidgets

try:
    import config as _config
except Exception:
    _config = None


class AboutTab(QtWidgets.QWidget):
    def __init__(self, live_tab, parent=None):
        super().__init__(parent)
        self._live_tab = live_tab
        self._label_cache = {}
        self._toggle_cache = {}

        self.url_label = QtWidgets.QLabel("Tunnel URL")
        self.url_label.setProperty("role", "muted")
        self.url_value = QtWidgets.QLabel("-")
        self.url_value.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)

        self.message_box = QtWidgets.QTextEdit()
        self.message_box.setReadOnly(True)

        self.btn_copy = QtWidgets.QPushButton("Copy URL")
        self.btn_copy.clicked.connect(self.copy_url)

        self.btn_copy_message = QtWidgets.QPushButton("Copy Message")
        self.btn_copy_message.setProperty("kind", "secondary")
        self.btn_copy_message.clicked.connect(self.copy_message)

        self.btn_refresh = QtWidgets.QPushButton("Refresh")
        self.btn_refresh.setProperty("kind", "secondary")
        self.btn_refresh.clicked.connect(self.refresh)

        self.status_label = QtWidgets.QLabel("Ready")
        self.status_label.setProperty("role", "muted")

        header = QtWidgets.QLabel("About")
        header.setObjectName("Title")
        sub = QtWidgets.QLabel("Tunnel status, diagnostics, and admin controls")
        sub.setObjectName("Subtitle")

        top = QtWidgets.QVBoxLayout()
        top.addWidget(header)
        top.addWidget(sub)

        meta = QtWidgets.QHBoxLayout()
        meta.addWidget(self.url_label)
        meta.addWidget(self.url_value)
        meta.addStretch()
        meta.addWidget(self.btn_copy)
        meta.addWidget(self.btn_copy_message)
        meta.addWidget(self.btn_refresh)

        diagnostics_card = self._build_diagnostics_card()
        policy_card = self._build_policy_card()

        info_row = QtWidgets.QHBoxLayout()
        info_row.addWidget(diagnostics_card, 3)
        info_row.addWidget(policy_card, 2)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addLayout(top)
        layout.addSpacing(6)
        layout.addLayout(meta)
        layout.addWidget(self.message_box)
        layout.addSpacing(6)
        layout.addLayout(info_row)
        layout.addWidget(self.status_label)
        layout.addStretch()

        self.refresh()

    def _live_label(self, name, fallback):
        if name in self._label_cache:
            return self._label_cache[name]
        label = getattr(self._live_tab, name, None)
        if label is None:
            label = QtWidgets.QLabel(fallback)
        self._label_cache[name] = label
        return label

    def _live_toggle(self, name, fallback_text):
        if name in self._toggle_cache:
            return self._toggle_cache[name]
        toggle = getattr(self._live_tab, name, None)
        if toggle is None:
            toggle = QtWidgets.QCheckBox(fallback_text)
            toggle.setEnabled(False)
        self._toggle_cache[name] = toggle
        return toggle

    def _build_diagnostics_card(self):
        card = QtWidgets.QFrame()
        card.setProperty("card", True)
        card_layout = QtWidgets.QVBoxLayout(card)
        card_layout.setContentsMargins(12, 12, 12, 12)
        card_layout.setSpacing(8)

        title = QtWidgets.QLabel("Diagnostics")
        title.setProperty("role", "section")
        card_layout.addWidget(title)

        grid = QtWidgets.QGridLayout()
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(6)
        card_layout.addLayout(grid)

        def add_row(row, label, value):
            key = QtWidgets.QLabel(label)
            key.setProperty("role", "muted")
            value.setProperty("chip", True)
            grid.addWidget(key, row, 0)
            grid.addWidget(value, row, 1)

        add_row(0, "Liveness", self._live_label("liveness_value", "n/a"))
        add_row(1, "Stability", self._live_label("stability_value", "n/a"))
        add_row(2, "Inference", self._live_label("latency_value", "n/a"))
        add_row(3, "API", self._live_label("api_value", "n/a"))
        add_row(4, "Capture", self._live_label("capture_value", "n/a"))

        return card

    def _build_policy_card(self):
        card = QtWidgets.QFrame()
        card.setProperty("card", True)
        card_layout = QtWidgets.QVBoxLayout(card)
        card_layout.setContentsMargins(12, 12, 12, 12)
        card_layout.setSpacing(6)

        title = QtWidgets.QLabel("Automation & Policies")
        title.setProperty("role", "section")
        card_layout.addWidget(title)

        automation_title = QtWidgets.QLabel("Automation")
        automation_title.setProperty("role", "section")
        card_layout.addWidget(automation_title)
        card_layout.addWidget(self._live_toggle("toggle_auto_infer", "Auto recognition"))
        card_layout.addWidget(self._live_toggle("toggle_event_capture", "Auto capture"))

        card_layout.addSpacing(6)

        door_title = QtWidgets.QLabel("Door policies")
        door_title.setProperty("role", "section")
        card_layout.addWidget(door_title)
        card_layout.addWidget(self._live_toggle("toggle_hold_on_face", "Hold door while face present"))
        card_layout.addWidget(self._live_toggle("toggle_require_known", "Require known identity"))
        card_layout.addWidget(self._live_toggle("toggle_require_real", "Require live face"))
        card_layout.addStretch()

        return card

    def _get_url(self):
        url = None
        try:
            import os
            url = os.getenv("DOORBELL_TUNNEL_URL") or os.getenv("PUBLIC_BASE_URL")
        except Exception:
            url = None
        if not url and _config is not None:
            url = getattr(_config, "PUBLIC_BASE_URL", None)
        return url

    def _build_message(self, url):
        if not url:
            return "Tunnel URL not available yet."
        lines = [
            "Your quick Tunnel has been created! Visit it at (it may take some time to be reachable):",
            url,
            "",
            f"[tunnel] {url}",
            f"Tunnel URL: {url} (copy to app)",
        ]
        return "\n".join(lines)

    def refresh(self):
        url = self._get_url()
        self.url_value.setText(url or "-")
        self.message_box.setPlainText(self._build_message(url))
        self.status_label.setText("Ready" if url else "Waiting for tunnel...")

    def copy_url(self):
        url = self._get_url()
        if not url:
            self.status_label.setText("No URL to copy")
            return
        QtWidgets.QApplication.clipboard().setText(url)
        self.status_label.setText("URL copied")

    def copy_message(self):
        text = self.message_box.toPlainText().strip()
        if not text:
            self.status_label.setText("No message to copy")
            return
        QtWidgets.QApplication.clipboard().setText(text)
        self.status_label.setText("Message copied")
