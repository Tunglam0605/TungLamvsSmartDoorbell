import cv2
from PySide6 import QtCore, QtWidgets

from face.face_db import FaceDB
from gui.dialogs import PersonDialog, EditPersonDialog, EnrollmentDialog


class AddPersonWorker(QtCore.QObject):
    finished = QtCore.Signal(bool, str, str, str)

    def __init__(self, runtime, name, frame=None, face_crop=None, embedding=None):
        super().__init__()
        self.runtime = runtime
        self.name = name
        self.frame = frame
        self.face_crop = face_crop
        self.embedding = embedding

    @QtCore.Slot()
    def run(self):
        if self.runtime is None or not getattr(self.runtime, "enable_face", True):
            self.finished.emit(False, "Face module unavailable", "", "")
            return

        def _work():
            embedding = self.embedding
            if embedding is None:
                result = self.runtime.extract_embedding(
                    frame=self.frame,
                    face_crop=self.face_crop,
                )
                if not result.get("ok"):
                    return False, result.get("error", "Embedding failed"), "", ""
                embedding = result.get("embedding")

            result = self.runtime.add_person(self.name, embedding)
            if not result.get("ok"):
                return False, result.get("error", "Add failed"), "", ""
            self.runtime.reload_db()
            pid = result.get("id", "")
            pname = result.get("name", "")
            state = result.get("state", "new")
            message = f"{state}: {pname} (id={pid})"
            return True, message, pid, pname

        lock = getattr(self.runtime, "infer_lock", None)
        try:
            if lock is not None:
                with lock:
                    ok, message, pid, pname = _work()
            else:
                ok, message, pid, pname = _work()
        except Exception as exc:
            ok, message, pid, pname = False, f"Add failed: {exc}", "", ""

        self.finished.emit(ok, message, pid, pname)




class UpdatePersonWorker(QtCore.QObject):
    finished = QtCore.Signal(bool, str)

    def __init__(self, runtime, db, person_id, name, frame=None, face_crop=None, embedding=None, update_embedding=False):
        super().__init__()
        self.runtime = runtime
        self.db = db
        self.person_id = person_id
        self.name = name
        self.frame = frame
        self.face_crop = face_crop
        self.embedding = embedding
        self.update_embedding = update_embedding

    @QtCore.Slot()
    def run(self):
        if not self.name:
            self.finished.emit(False, "Name is required")
            return
        embedding = self.embedding

        if self.update_embedding:
            if self.runtime is None or not getattr(self.runtime, "enable_face", True):
                self.finished.emit(False, "Face module unavailable")
                return
            if embedding is None:
                result = self.runtime.extract_embedding(
                    frame=self.frame,
                    face_crop=self.face_crop,
                )
                if not result.get("ok"):
                    self.finished.emit(False, result.get("error", "Embedding failed"))
                    return
                embedding = result.get("embedding")

        lock = getattr(self.runtime, "infer_lock", None) if self.runtime is not None else None
        try:
            if lock is not None and self.update_embedding:
                with lock:
                    ok = self.db.update_person(self.person_id, name=self.name, embedding=embedding if self.update_embedding else None)
            else:
                ok = self.db.update_person(self.person_id, name=self.name, embedding=embedding if self.update_embedding else None)
        except Exception as exc:
            self.finished.emit(False, f"Update failed: {exc}")
            return

        if not ok:
            self.finished.emit(False, "Person not found")
            return
        if self.runtime is not None:
            self.runtime.reload_db()
        self.finished.emit(True, f"Updated id={self.person_id}")


class PeopleTab(QtWidgets.QWidget):
    def __init__(self, runtime, live_tab, parent=None):
        super().__init__(parent)
        self.runtime = runtime
        self.live_tab = live_tab
        self.db = FaceDB()
        self.people = []
        self._closing = False
        self._add_thread = None
        self._add_worker = None
        self._edit_thread = None
        self._edit_worker = None
        self._busy = False
        self.thread_infer = bool(getattr(live_tab, "thread_infer", False))

        self.title_label = QtWidgets.QLabel("People Manager")
        self.title_label.setObjectName("Title")
        self.subtitle_label = QtWidgets.QLabel("Manage enrolled identities and access list")
        self.subtitle_label.setObjectName("Subtitle")

        self.total_value = QtWidgets.QLabel("0")
        self.total_value.setProperty("chip", True)
        self.db_value = QtWidgets.QLabel("face_db.json")
        self.db_value.setProperty("chip", True)

        self.search_input = QtWidgets.QLineEdit()
        self.search_input.setPlaceholderText("Search by name")
        self.search_input.textChanged.connect(self.refresh_table)

        self.table = QtWidgets.QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels(["ID", "Name"])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setSelectionBehavior(QtWidgets.QTableWidget.SelectRows)
        self.table.setSelectionMode(QtWidgets.QTableWidget.SingleSelection)
        self.table.setEditTriggers(QtWidgets.QTableWidget.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.setSortingEnabled(True)

        self.btn_add = QtWidgets.QPushButton("Add")
        self.btn_edit = QtWidgets.QPushButton("Edit")
        self.btn_delete = QtWidgets.QPushButton("Delete")
        self.btn_refresh = QtWidgets.QPushButton("Refresh")

        self.btn_edit.setProperty("kind", "secondary")
        self.btn_delete.setProperty("kind", "danger")
        self.btn_refresh.setProperty("kind", "secondary")

        self.btn_add.clicked.connect(self.add_from_dialog)
        self.btn_edit.clicked.connect(self.edit_selected)
        self.btn_delete.clicked.connect(self.delete_selected)
        self.btn_refresh.clicked.connect(lambda: self.refresh_table(force_reload=True))
        self.btn_edit.setEnabled(False)
        self.table.itemSelectionChanged.connect(self._update_action_buttons)

        self.status_label = QtWidgets.QLabel("Ready.")
        self.status_label.setProperty("role", "muted")

        header_row = QtWidgets.QHBoxLayout()
        title_col = QtWidgets.QVBoxLayout()
        title_col.addWidget(self.title_label)
        title_col.addWidget(self.subtitle_label)
        header_row.addLayout(title_col)
        header_row.addStretch()

        header_meta = QtWidgets.QHBoxLayout()
        total_label = QtWidgets.QLabel("Total")
        total_label.setProperty("role", "muted")
        db_label = QtWidgets.QLabel("DB")
        db_label.setProperty("role", "muted")
        header_meta.addWidget(total_label)
        header_meta.addWidget(self.total_value)
        header_meta.addSpacing(8)
        header_meta.addWidget(db_label)
        header_meta.addWidget(self.db_value)
        header_row.addLayout(header_meta)

        toolbar_card = QtWidgets.QFrame()
        toolbar_card.setProperty("card", True)
        toolbar = QtWidgets.QHBoxLayout(toolbar_card)
        toolbar.setContentsMargins(12, 8, 12, 8)
        toolbar.addWidget(self.search_input)
        toolbar.addStretch()
        toolbar.addWidget(self.btn_add)
        toolbar.addWidget(self.btn_edit)
        toolbar.addWidget(self.btn_delete)
        toolbar.addWidget(self.btn_refresh)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addLayout(header_row)
        layout.addSpacing(6)
        layout.addWidget(toolbar_card)
        layout.addWidget(self.table)
        layout.addWidget(self.status_label)

        self.refresh_table(force_reload=True)


    def _update_action_buttons(self):
        if self._busy:
            self.btn_edit.setEnabled(False)
            self.btn_delete.setEnabled(False)
            return
        has_row = self.table.currentRow() >= 0
        self.btn_edit.setEnabled(has_row)
        self.btn_delete.setEnabled(has_row)

    def add_from_live(self):
        self.add_from_dialog(default_source="live")

    def add_from_dialog(self, default_source="live"):
        dialog = PersonDialog(self)
        dialog.set_source_mode(default_source)
        if dialog.exec() != QtWidgets.QDialog.Accepted:
            return

        data = dialog.get_data()
        name = data.get("name", "").strip()
        if not name:
            QtWidgets.QMessageBox.warning(self, "Validation", "Name is required.")
            return

        source = data.get("source")
        if source == "file":
            path = data.get("file_path")
            if not path:
                QtWidgets.QMessageBox.warning(
                    self, "Validation", "Please select an image file."
                )
                return
            frame = cv2.imread(path)
            if frame is None:
                QtWidgets.QMessageBox.warning(
                    self, "Validation", "Failed to load image file."
                )
                return
            self._start_add_worker(name=name, frame=frame)
        else:
            if self.runtime is None or not getattr(self.runtime, "enable_face", True):
                QtWidgets.QMessageBox.warning(
                    self,
                    "Validation",
                    "Face module unavailable. Enable face recognition first.",
                )
                return
            enroll = EnrollmentDialog(self.runtime, self.live_tab, self)
            if enroll.exec() != QtWidgets.QDialog.Accepted:
                return
            embedding = enroll.get_embedding()
            if embedding is None:
                QtWidgets.QMessageBox.warning(
                    self,
                    "Validation",
                    "Enrollment failed. Please try again.",
                )
                return
            self._start_add_worker(name=name, embedding=embedding)

    def _get_latest_face_crop(self):
        if self.live_tab:
            latest_result = getattr(self.live_tab, "latest_result", None)
            if latest_result and latest_result.get("face_crop") is not None:
                return latest_result.get("face_crop").copy()
        if self.runtime and getattr(self.runtime, "last_face_crop", None) is not None:
            return self.runtime.last_face_crop.copy()
        return None

    def _get_latest_frame(self):
        if self.live_tab and getattr(self.live_tab, "latest_frame", None) is not None:
            return self.live_tab.latest_frame.copy()
        if self.runtime and getattr(self.runtime, "last_frame", None) is not None:
            return self.runtime.last_frame.copy()
        return None

    def _get_latest_embedding(self):
        if self.runtime and getattr(self.runtime, "last_embedding", None) is not None:
            return self.runtime.last_embedding
        return None

    def _start_add_worker(self, name, frame=None, face_crop=None, embedding=None):
        if self._closing:
            return
        self._set_busy(True, "Adding person...")
        worker = AddPersonWorker(
            self.runtime,
            name=name,
            frame=frame.copy() if frame is not None else None,
            face_crop=face_crop.copy() if face_crop is not None else None,
            embedding=embedding,
        )

        if not self.thread_infer:
            self._add_worker = worker
            worker.finished.connect(self._on_add_finished)
            worker.run()
            return

        thread = QtCore.QThread(self)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.finished.connect(self._on_add_finished)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(self._on_add_thread_finished)
        thread.finished.connect(thread.deleteLater)
        self._add_thread = thread
        self._add_worker = worker
        thread.start()

    def _on_add_thread_finished(self):
        self._add_thread = None

    def _on_add_finished(self, ok, message, pid, pname):
        if self._closing:
            return
        self._add_thread = None
        self._add_worker = None
        self._edit_thread = None
        self._edit_worker = None
        self._busy = False
        self._set_busy(False, message)
        if not ok:
            QtWidgets.QMessageBox.warning(self, "Add failed", message)
            return
        self.refresh_table(force_reload=True)


    def _start_update_worker(self, person_id, name, frame=None, face_crop=None, embedding=None, update_embedding=False):
        if self._closing:
            return
        self._set_busy(True, "Updating person...")
        worker = UpdatePersonWorker(
            self.runtime,
            self.db,
            person_id=person_id,
            name=name,
            frame=frame.copy() if frame is not None else None,
            face_crop=face_crop.copy() if face_crop is not None else None,
            embedding=embedding,
            update_embedding=update_embedding,
        )

        if not self.thread_infer:
            self._edit_worker = worker
            worker.finished.connect(self._on_update_finished)
            worker.run()
            return

        thread = QtCore.QThread(self)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.finished.connect(self._on_update_finished)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(self._on_edit_thread_finished)
        thread.finished.connect(thread.deleteLater)
        self._edit_thread = thread
        self._edit_worker = worker
        thread.start()

    def _on_edit_thread_finished(self):
        self._edit_thread = None

    def _on_update_finished(self, ok, message):
        if self._closing:
            return
        self._edit_thread = None
        self._edit_worker = None
        self._set_busy(False, message)
        if not ok:
            QtWidgets.QMessageBox.warning(self, "Update failed", message)
            return
        self.refresh_table(force_reload=True)

    def delete_selected(self):
        row = self.table.currentRow()
        if row < 0:
            QtWidgets.QMessageBox.warning(self, "Delete", "Select a person first.")
            return
        pid_item = self.table.item(row, 0)
        if pid_item is None:
            return
        pid = pid_item.text().strip()
        if not pid:
            return
        confirm = QtWidgets.QMessageBox.question(
            self,
            "Delete",
            f"Delete person id={pid}?",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
        )
        if confirm != QtWidgets.QMessageBox.Yes:
            return
        if self.db.delete_person(pid):
            if self.runtime:
                self.runtime.reload_db()
            self.refresh_table(force_reload=True)
            self._set_status(f"Deleted id={pid}")
        else:
            QtWidgets.QMessageBox.warning(self, "Delete", "Person not found.")


    def edit_selected(self):
        row = self.table.currentRow()
        if row < 0:
            QtWidgets.QMessageBox.warning(self, "Edit", "Select a person first.")
            return
        pid_item = self.table.item(row, 0)
        name_item = self.table.item(row, 1)
        if pid_item is None:
            return
        pid = pid_item.text().strip()
        current_name = name_item.text().strip() if name_item is not None else ""
        if not pid:
            return

        dialog = EditPersonDialog(current_name, self)
        if dialog.exec() != QtWidgets.QDialog.Accepted:
            return

        data = dialog.get_data()
        new_name = data.get("name", "").strip()
        if not new_name:
            QtWidgets.QMessageBox.warning(self, "Validation", "Name is required.")
            return

        update_embedding = bool(data.get("update_embedding"))
        source = data.get("source")
        frame = None
        face_crop = None
        embedding = None

        if update_embedding:
            if source == "file":
                path = data.get("file_path")
                if not path:
                    QtWidgets.QMessageBox.warning(
                        self, "Validation", "Please select an image file."
                    )
                    return
                frame = cv2.imread(path)
                if frame is None:
                    QtWidgets.QMessageBox.warning(
                        self, "Validation", "Failed to load image file."
                    )
                    return
            else:
                if self.runtime is None or not getattr(self.runtime, "enable_face", True):
                    QtWidgets.QMessageBox.warning(
                        self,
                        "Validation",
                        "Face module unavailable. Enable face recognition first.",
                    )
                    return
                enroll = EnrollmentDialog(self.runtime, self.live_tab, self)
                if enroll.exec() != QtWidgets.QDialog.Accepted:
                    return
                embedding = enroll.get_embedding()
                if embedding is None:
                    QtWidgets.QMessageBox.warning(
                        self,
                        "Validation",
                        "Enrollment failed. Please try again.",
                    )
                    return

        self._start_update_worker(
            person_id=pid,
            name=new_name,
            frame=frame,
            face_crop=face_crop,
            embedding=embedding,
            update_embedding=update_embedding,
        )

    def refresh_table(self, force_reload=False):
        if force_reload:
            self.db.load()
            self.people = self.db.list_people()
            if self.runtime is not None:
                self.runtime.reload_db()

        filter_text = self.search_input.text().strip().lower()
        rows = []
        for person in self.people:
            name = str(person.get("name", ""))
            if filter_text and filter_text not in name.lower():
                continue
            rows.append(person)

        self.table.setRowCount(len(rows))
        for idx, person in enumerate(rows):
            pid = str(person.get("id", ""))
            name = str(person.get("name", ""))
            self.table.setItem(idx, 0, QtWidgets.QTableWidgetItem(pid))
            self.table.setItem(idx, 1, QtWidgets.QTableWidgetItem(name))

        self.table.resizeColumnsToContents()
        self.total_value.setText(str(len(self.people)))
        self._set_status(f"Showing {len(rows)} of {len(self.people)}")
        self._update_action_buttons()

    def _set_busy(self, busy, message=""):
        self._busy = bool(busy)
        self.btn_add.setEnabled(not busy)
        self.btn_edit.setEnabled(not busy and self.table.currentRow() >= 0)
        self.btn_delete.setEnabled(not busy and self.table.currentRow() >= 0)
        self.btn_refresh.setEnabled(not busy)
        if message:
            self._set_status(message)

    def _set_status(self, message):
        self.status_label.setText(message)

    def shutdown(self):
        self._closing = True
        thread = self._add_thread
        if thread is not None and thread.isRunning():
            thread.quit()
            thread.wait(5000)
            if thread.isRunning():
                thread.terminate()
                thread.wait(1000)
        thread = self._edit_thread
        if thread is not None and thread.isRunning():
            thread.quit()
            thread.wait(5000)
            if thread.isRunning():
                thread.terminate()
                thread.wait(1000)
        self._add_thread = None
        self._add_worker = None
        self._edit_thread = None
        self._edit_worker = None
        self._busy = False
