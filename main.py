"""Главное окно ChatList."""

from __future__ import annotations

import sys

from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

import db
import export_util
import models as models_svc
import network
from models import ModelInfo, TempResultsTable


class SendWorker(QThread):
    finished_ok = pyqtSignal(list)
    failed = pyqtSignal(str)

    def __init__(
        self,
        models: list[ModelInfo],
        prompt: str,
        *,
        parallel: bool,
        timeout: float,
    ) -> None:
        super().__init__()
        self.models = models
        self.prompt = prompt
        self.parallel = parallel
        self.timeout = timeout

    def run(self) -> None:
        try:
            responses = network.send_prompt_to_models(
                self.models,
                self.prompt,
                parallel=self.parallel,
                timeout=self.timeout,
            )
            self.finished_ok.emit(responses)
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(str(exc))


class SettingsDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Настройки")
        self.resize(420, 240)

        self.timeout_spin = QSpinBox()
        self.timeout_spin.setRange(5, 600)
        self.timeout_spin.setValue(int(db.get_setting("request_timeout", "60") or "60"))

        self.parallel_check = QCheckBox("Параллельная отправка в модели")
        self.parallel_check.setChecked((db.get_setting("parallel_requests", "1") or "1") == "1")

        self.log_check = QCheckBox("Логировать запросы в requests.log")
        self.log_check.setChecked((db.get_setting("log_requests", "1") or "1") == "1")

        self.default_tags = QLineEdit(db.get_setting("default_tags", "") or "")
        self.referer_edit = QLineEdit(
            db.get_setting("openrouter_referer", "https://github.com/local/ChatList") or ""
        )
        self.title_edit = QLineEdit(db.get_setting("openrouter_title", "ChatList") or "ChatList")

        form = QFormLayout()
        form.addRow("Таймаут запроса (сек):", self.timeout_spin)
        form.addRow("", self.parallel_check)
        form.addRow("", self.log_check)
        form.addRow("Теги по умолчанию:", self.default_tags)
        form.addRow("OpenRouter Referer:", self.referer_edit)
        form.addRow("OpenRouter X-Title:", self.title_edit)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.save)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(
            QLabel("API-ключи хранятся только в .env; в БД — имена переменных.")
        )
        layout.addWidget(buttons)

    def save(self) -> None:
        db.set_setting("request_timeout", str(self.timeout_spin.value()))
        db.set_setting("parallel_requests", "1" if self.parallel_check.isChecked() else "0")
        db.set_setting("log_requests", "1" if self.log_check.isChecked() else "0")
        db.set_setting("default_tags", self.default_tags.text().strip())
        db.set_setting("openrouter_referer", self.referer_edit.text().strip())
        db.set_setting("openrouter_title", self.title_edit.text().strip())
        self.accept()


class ModelsDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Модели")
        self.resize(780, 420)

        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Поиск по имени / URL / переменной…")
        self.search_edit.textChanged.connect(self.reload)

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(
            ["ID", "Имя", "API URL", "Переменная ключа", "Активна"]
        )
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSortingEnabled(True)

        self.name_edit = QLineEdit()
        self.url_edit = QLineEdit()
        self.url_edit.setText(models_svc.OPENROUTER_URL)
        self.key_env_edit = QLineEdit(models_svc.resolve_openrouter_key_env())
        self.active_check = QCheckBox("Активна")
        self.active_check.setChecked(True)

        form = QFormLayout()
        form.addRow("Имя (id модели):", self.name_edit)
        form.addRow("API URL:", self.url_edit)
        form.addRow("Переменная ключа:", self.key_env_edit)
        form.addRow("", self.active_check)

        add_btn = QPushButton("Добавить")
        add_btn.clicked.connect(self.add_model)
        toggle_btn = QPushButton("Вкл/выкл выбранную")
        toggle_btn.clicked.connect(self.toggle_selected)
        delete_btn = QPushButton("Удалить выбранную")
        delete_btn.clicked.connect(self.delete_selected)

        buttons = QHBoxLayout()
        buttons.addWidget(add_btn)
        buttons.addWidget(toggle_btn)
        buttons.addWidget(delete_btn)
        buttons.addStretch()

        close_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        close_box.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(self.search_edit)
        layout.addWidget(self.table)
        layout.addLayout(form)
        layout.addLayout(buttons)
        layout.addWidget(close_box)
        self.reload()

    def reload(self) -> None:
        query = self.search_edit.text().strip()
        rows = db.search_models(query) if query else db.list_models()
        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(rows))
        for i, model in enumerate(rows):
            self.table.setItem(i, 0, QTableWidgetItem(str(model["id"])))
            self.table.setItem(i, 1, QTableWidgetItem(model["name"]))
            self.table.setItem(i, 2, QTableWidgetItem(model["api_url"]))
            self.table.setItem(i, 3, QTableWidgetItem(model["api_key_env"]))
            self.table.setItem(i, 4, QTableWidgetItem("да" if model["is_active"] else "нет"))
        self.table.setSortingEnabled(True)

    def add_model(self) -> None:
        name = self.name_edit.text().strip()
        url = self.url_edit.text().strip()
        key_env = self.key_env_edit.text().strip()
        if not name or not url or not key_env:
            QMessageBox.warning(self, "Модели", "Заполните имя, URL и переменную ключа.")
            return
        try:
            models_svc.create_model(
                name=name,
                api_url=url,
                api_key_env=key_env,
                is_active=self.active_check.isChecked(),
            )
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Модели", str(exc))
            return
        self.name_edit.clear()
        self.reload()

    def toggle_selected(self) -> None:
        row = self.table.currentRow()
        if row < 0:
            return
        model_id = int(self.table.item(row, 0).text())
        model = db.get_model(model_id)
        if model is None:
            return
        models_svc.edit_model(model_id, is_active=not bool(model["is_active"]))
        self.reload()

    def delete_selected(self) -> None:
        row = self.table.currentRow()
        if row < 0:
            return
        model_id = int(self.table.item(row, 0).text())
        models_svc.remove_model(model_id)
        self.reload()


class SavedResultsDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Сохранённые результаты")
        self.resize(860, 460)
        self._rows: list[dict] = []

        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Поиск по промту / модели / ответу…")
        self.search_edit.textChanged.connect(self.reload)

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["Дата", "Модель", "Промт", "Ответ", "ID"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setSortingEnabled(True)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)

        export_md_btn = QPushButton("Экспорт Markdown")
        export_md_btn.clicked.connect(lambda: self.export_selected(".md"))
        export_json_btn = QPushButton("Экспорт JSON")
        export_json_btn.clicked.connect(lambda: self.export_selected(".json"))

        buttons = QHBoxLayout()
        buttons.addWidget(export_md_btn)
        buttons.addWidget(export_json_btn)
        buttons.addStretch()

        close_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        close_box.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(self.search_edit)
        layout.addWidget(self.table)
        layout.addLayout(buttons)
        layout.addWidget(close_box)
        self.reload()

    def reload(self) -> None:
        query = self.search_edit.text().strip()
        self._rows = db.search_results(query) if query else db.list_results()
        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(self._rows))
        for i, item in enumerate(self._rows):
            self.table.setItem(i, 0, QTableWidgetItem(item["created_at"]))
            self.table.setItem(i, 1, QTableWidgetItem(item["model_name"]))
            self.table.setItem(i, 2, QTableWidgetItem((item["prompt_text"] or "")[:80]))
            self.table.setItem(i, 3, QTableWidgetItem((item["response"] or "")[:120]))
            self.table.setItem(i, 4, QTableWidgetItem(str(item["id"])))
        self.table.setSortingEnabled(True)

    def export_selected(self, suffix: str) -> None:
        rows = self.table.selectionModel().selectedRows()
        if rows:
            ids = {int(self.table.item(r.row(), 4).text()) for r in rows}
            data = [item for item in self._rows if item["id"] in ids]
        else:
            data = list(self._rows)
        if not data:
            QMessageBox.information(self, "Экспорт", "Нет данных для экспорта.")
            return
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Сохранить файл",
            f"chatlist_results{suffix}",
            "Markdown (*.md);;JSON (*.json)" if suffix == ".md" else "JSON (*.json);;Markdown (*.md)",
        )
        if not path:
            return
        if not path.lower().endswith((".md", ".json")):
            path += suffix
        try:
            export_util.export_results(path, data, prompt_text="")
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Экспорт", str(exc))
            return
        QMessageBox.information(self, "Экспорт", f"Сохранено: {path}")


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("ChatList")
        self.resize(960, 700)

        db.init_db()
        models_svc.ensure_default_models()
        self.temp_results = TempResultsTable()
        self._worker: SendWorker | None = None

        self.prompt_search = QLineEdit()
        self.prompt_search.setPlaceholderText("Поиск сохранённых промтов…")
        self.prompt_search.textChanged.connect(self.reload_prompts)

        self.prompt_combo = QComboBox()
        self.prompt_combo.currentIndexChanged.connect(self.on_prompt_selected)

        self.prompt_edit = QTextEdit()
        self.prompt_edit.setPlaceholderText("Введите промт…")

        self.tags_edit = QLineEdit()
        self.tags_edit.setPlaceholderText("Теги (через запятую), необязательно")
        self.tags_edit.setText(db.get_setting("default_tags", "") or "")

        self.send_btn = QPushButton("Отправить")
        self.send_btn.clicked.connect(self.on_send)
        save_btn = QPushButton("Сохранить")
        save_btn.clicked.connect(self.on_save)
        export_btn = QPushButton("Экспорт…")
        export_btn.clicked.connect(self.on_export_temp)
        models_btn = QPushButton("Модели…")
        models_btn.clicked.connect(self.open_models)
        results_btn = QPushButton("Сохранённые…")
        results_btn.clicked.connect(self.open_saved_results)
        settings_btn = QPushButton("Настройки…")
        settings_btn.clicked.connect(self.open_settings)

        top_buttons = QHBoxLayout()
        top_buttons.addWidget(self.send_btn)
        top_buttons.addWidget(save_btn)
        top_buttons.addWidget(export_btn)
        top_buttons.addStretch()
        top_buttons.addWidget(models_btn)
        top_buttons.addWidget(results_btn)
        top_buttons.addWidget(settings_btn)

        self.results_table = QTableWidget(0, 3)
        self.results_table.setHorizontalHeaderLabels(["Модель", "Ответ", "Выбрать"])
        self.results_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.ResizeToContents
        )
        self.results_table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch
        )
        self.results_table.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.ResizeMode.ResizeToContents
        )
        self.results_table.setSortingEnabled(True)

        self.status_label = QLabel("Готово")

        central = QWidget()
        layout = QVBoxLayout(central)
        layout.addWidget(QLabel("Сохранённые промты:"))
        layout.addWidget(self.prompt_search)
        layout.addWidget(self.prompt_combo)
        layout.addWidget(QLabel("Промт:"))
        layout.addWidget(self.prompt_edit)
        layout.addWidget(self.tags_edit)
        layout.addLayout(top_buttons)
        layout.addWidget(QLabel("Результаты (временная таблица):"))
        layout.addWidget(self.results_table)
        layout.addWidget(self.status_label)
        self.setCentralWidget(central)

        self.reload_prompts()
        missing = models_svc.models_missing_keys()
        if missing:
            names = ", ".join(sorted({m.api_key_env for m in missing}))
            self.status_label.setText(f"Нет ключей в .env: {names}")

    def reload_prompts(self) -> None:
        query = self.prompt_search.text().strip()
        items = db.search_prompts(query) if query else db.list_prompts()
        current_id = self.prompt_combo.currentData()
        self.prompt_combo.blockSignals(True)
        self.prompt_combo.clear()
        self.prompt_combo.addItem("— новый промт —", None)
        selected_index = 0
        for item in items:
            preview = item["text"].replace("\n", " ")[:60]
            self.prompt_combo.addItem(f"#{item['id']}: {preview}", item["id"])
            if current_id is not None and item["id"] == current_id:
                selected_index = self.prompt_combo.count() - 1
        self.prompt_combo.setCurrentIndex(selected_index)
        self.prompt_combo.blockSignals(False)

    def on_prompt_selected(self, index: int) -> None:
        prompt_id = self.prompt_combo.itemData(index)
        if prompt_id is None:
            return
        prompt = db.get_prompt(int(prompt_id))
        if prompt is None:
            return
        self.prompt_edit.setPlainText(prompt["text"])
        self.tags_edit.setText(prompt.get("tags") or "")

    def on_send(self) -> None:
        if self._worker is not None and self._worker.isRunning():
            return

        prompt_text = self.prompt_edit.toPlainText().strip()
        if not prompt_text:
            QMessageBox.warning(self, "ChatList", "Введите текст промта.")
            return

        active = models_svc.get_active_models()
        if not active:
            QMessageBox.warning(
                self,
                "ChatList",
                "Нет активных моделей. Добавьте их в диалоге «Модели».",
            )
            return

        missing = models_svc.models_missing_keys(active)
        if missing:
            envs = ", ".join(sorted({m.api_key_env for m in missing}))
            answer = QMessageBox.question(
                self,
                "Нет API-ключа",
                (
                    f"Для части моделей не заданы ключи в .env ({envs}).\n"
                    "Продолжить? Строки без ключа будут с ошибкой."
                ),
            )
            if answer != QMessageBox.StandardButton.Yes:
                return

        # Новый запрос — временная таблица очищается.
        self.temp_results.clear()
        self.render_temp_results()

        tags = self.tags_edit.text().strip() or None
        prompt_id = self.prompt_combo.currentData()
        if prompt_id is None:
            prompt_id = db.add_prompt(prompt_text, tags=tags)
            self.reload_prompts()
            # выбрать только что созданный
            for i in range(self.prompt_combo.count()):
                if self.prompt_combo.itemData(i) == prompt_id:
                    self.prompt_combo.setCurrentIndex(i)
                    break
        else:
            prompt_id = int(prompt_id)

        timeout = float(db.get_setting("request_timeout", "60") or "60")
        parallel = (db.get_setting("parallel_requests", "1") or "1") == "1"

        self.send_btn.setEnabled(False)
        self.status_label.setText("Отправка запросов…")

        self._worker = SendWorker(active, prompt_text, parallel=parallel, timeout=timeout)
        self._worker.finished_ok.connect(
            lambda responses, pid=prompt_id, text=prompt_text: self.on_send_done(
                responses, pid, text
            )
        )
        self._worker.failed.connect(self.on_send_failed)
        self._worker.start()

    def on_send_done(self, responses: list, prompt_id: int, prompt_text: str) -> None:
        self.send_btn.setEnabled(True)
        self.temp_results.load_from_responses(prompt_text, responses, prompt_id=prompt_id)
        self.render_temp_results()
        errors = sum(1 for r in responses if r.get("error"))
        self.status_label.setText(
            f"Получено ответов: {len(responses)} (ошибок: {errors}), prompt_id={prompt_id}"
        )

    def on_send_failed(self, message: str) -> None:
        self.send_btn.setEnabled(True)
        self.status_label.setText("Ошибка отправки")
        QMessageBox.critical(self, "ChatList", message)

    def on_save(self) -> None:
        selected = self.temp_results.to_save_items()
        if not selected:
            QMessageBox.information(
                self,
                "ChatList",
                "Отметьте хотя бы один успешный результат.",
            )
            return

        prompt_id = self.temp_results.prompt_id
        if prompt_id is None:
            prompt_text = self.temp_results.prompt_text or self.prompt_edit.toPlainText().strip()
            tags = self.tags_edit.text().strip() or None
            prompt_id = db.add_prompt(prompt_text, tags=tags)
            self.temp_results.prompt_id = prompt_id

        db.save_results(prompt_id, selected)
        self.temp_results.clear()
        self.render_temp_results()
        self.reload_prompts()
        self.status_label.setText(f"Сохранено в results, prompt_id={prompt_id}")
        QMessageBox.information(self, "ChatList", "Выбранные результаты сохранены.")

    def on_export_temp(self) -> None:
        rows = self.temp_results.to_export_rows(only_selected=True)
        if not rows:
            rows = self.temp_results.to_export_rows(only_selected=False)
        if not rows:
            QMessageBox.information(self, "Экспорт", "Нет результатов для экспорта.")
            return
        path, selected_filter = QFileDialog.getSaveFileName(
            self,
            "Экспорт результатов",
            "chatlist_export.md",
            "Markdown (*.md);;JSON (*.json)",
        )
        if not path:
            return
        if path.lower().endswith((".md", ".json")):
            pass
        elif "JSON" in selected_filter:
            path += ".json"
        else:
            path += ".md"
        try:
            export_util.export_results(path, rows, prompt_text=self.temp_results.prompt_text)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Экспорт", str(exc))
            return
        QMessageBox.information(self, "Экспорт", f"Сохранено: {path}")

    def render_temp_results(self) -> None:
        rows = self.temp_results.rows
        self.results_table.setSortingEnabled(False)
        self.results_table.setRowCount(len(rows))
        for i, row in enumerate(rows):
            name_item = QTableWidgetItem(row.model_name)
            name_item.setFlags(name_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            response_item = QTableWidgetItem(row.response)
            response_item.setFlags(response_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            if row.error:
                response_item.setForeground(Qt.GlobalColor.red)
            self.results_table.setItem(i, 0, name_item)
            self.results_table.setItem(i, 1, response_item)

            checkbox = QCheckBox()
            checkbox.setChecked(row.selected)
            checkbox.setEnabled(not row.error)
            checkbox.toggled.connect(
                lambda checked, index=i: self.temp_results.set_selected(index, checked)
            )
            wrapper = QWidget()
            box = QHBoxLayout(wrapper)
            box.addWidget(checkbox)
            box.setAlignment(Qt.AlignmentFlag.AlignCenter)
            box.setContentsMargins(0, 0, 0, 0)
            self.results_table.setCellWidget(i, 2, wrapper)
        self.results_table.setSortingEnabled(True)

    def open_models(self) -> None:
        ModelsDialog(self).exec()

    def open_saved_results(self) -> None:
        SavedResultsDialog(self).exec()

    def open_settings(self) -> None:
        if SettingsDialog(self).exec():
            self.status_label.setText("Настройки сохранены")


def main() -> None:
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
