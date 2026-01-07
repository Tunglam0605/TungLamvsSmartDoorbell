from PySide6 import QtWidgets

try:
    from config import (
        GUI_ENABLE_LIVENESS,
        GUI_ENABLE_FACE,
        ABOUT_ACCESS_ID,
        ABOUT_ACCESS_PASSWORD,
    )
except Exception:
    GUI_ENABLE_LIVENESS = False
    GUI_ENABLE_FACE = True
    ABOUT_ACCESS_ID = "admin"
    ABOUT_ACCESS_PASSWORD = "admin"

from gui.tab_live import LiveTab
from gui.tab_people import PeopleTab
from gui.tab_about import AboutTab
from runtime import DoorbellRuntime


class AboutAuthDialog(QtWidgets.QDialog):
    def __init__(self, parent=None, title="Access required"):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumWidth(320)

        self.id_input = QtWidgets.QLineEdit()
        self.pw_input = QtWidgets.QLineEdit()
        self.pw_input.setEchoMode(QtWidgets.QLineEdit.Password)

        form = QtWidgets.QFormLayout()
        form.addRow("ID", self.id_input)
        form.addRow("Password", self.pw_input)

        buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)


class AppWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Smart Doorbell")
        self._closing = False

        self._tabs = QtWidgets.QTabWidget()
        self._last_tab_index = 0
        self._about_unlocked = False
        self._about_tab_index = None
        self._people_unlocked = False
        self._people_tab_index = None

        enable_liveness = GUI_ENABLE_LIVENESS
        enable_face = GUI_ENABLE_FACE

        self.runtime = DoorbellRuntime(
            enable_liveness=enable_liveness,
            enable_face=enable_face,
        )

        self.live_tab = LiveTab(self.runtime)
        self.people_tab = PeopleTab(self.runtime, self.live_tab)
        self.live_tab.request_add_from_frame.connect(self.people_tab.add_from_live)

        self._tabs.addTab(self.live_tab, "Live")
        self._tabs.addTab(self.people_tab, "People")
        self._people_tab_index = self._tabs.indexOf(self.people_tab)
        self.about_tab = AboutTab(self.live_tab)
        self._tabs.addTab(self.about_tab, "About")
        self._about_tab_index = self._tabs.indexOf(self.about_tab)

        self._tabs.currentChanged.connect(self._on_tab_changed)

        self.setCentralWidget(self._tabs)
        self.resize(1200, 760)

    def _check_protected_auth(self, title="Access required"):
        expected_id = str(ABOUT_ACCESS_ID or "").strip()
        expected_pw = str(ABOUT_ACCESS_PASSWORD or "")
        if not expected_id and not expected_pw:
            return True

        dialog = AboutAuthDialog(self, title=title)
        if dialog.exec() != QtWidgets.QDialog.Accepted:
            return False

        entered_id = dialog.id_input.text().strip()
        entered_pw = dialog.pw_input.text()
        if entered_id == expected_id and entered_pw == expected_pw:
            return True

        QtWidgets.QMessageBox.warning(self, "Access denied", "Invalid ID or password.")
        return False

    def _on_tab_changed(self, index):
        if index == self._people_tab_index and not self._people_unlocked:
            if not self._check_protected_auth(title="People access"):
                self._tabs.blockSignals(True)
                self._tabs.setCurrentIndex(self._last_tab_index)
                self._tabs.blockSignals(False)
                return
            self._people_unlocked = True
        if index == self._about_tab_index and not self._about_unlocked:
            if not self._check_protected_auth(title="About access"):
                self._tabs.blockSignals(True)
                self._tabs.setCurrentIndex(self._last_tab_index)
                self._tabs.blockSignals(False)
                return
            self._about_unlocked = True
        self._last_tab_index = index

    def shutdown(self):
        if self._closing:
            return
        self._closing = True
        if getattr(self, "live_tab", None) is not None:
            self.live_tab.shutdown()
        if getattr(self, "people_tab", None) is not None:
            self.people_tab.shutdown()
        if getattr(self, "runtime", None) is not None:
            self.runtime.close()

    def closeEvent(self, event):
        self.shutdown()
        super().closeEvent(event)
