"""Главное окно ChatList — каркас GUI (этап 4)."""

from __future__ import annotations

import sys

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

import db
import models as models_svc
import network
from models import TempResultsTable


class ModelsDialog(QDialog):
    """Диалог управления моделями нейросетей."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Модели")
        self.resize(700, 360)

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(
            ["ID", "Имя", "API URL", "Переменная ключа", "Активна"]
        )
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)

        self.name_edit = QLineEdit()
        self.url_edit = QLineEdit()
        self.key_env_edit = QLineEdit()
        self.active_check = QCheckBox("Активна")
        self.active_check.setChecked(True)

        form = QFormLayout()
        form.addRow("Имя:", self.name_edit)
        form.addRow("API URL:", self.url_edit)
        form.addRow("Переменная ключа:", self.key_env_edit)
        form.addRow("", self.active_check)

        add_btn = QPushButton("Добавить")
        add_btn.clicked.connect(self.add_model)
        toggle_btn = QPushButton("Вкл/выкл выбранную")
        toggle_btn.clicked.connect(self.toggle_selected)
        refresh_btn = QPushButton("Обновить")
        refresh_btn.clicked.connect(self.reload)

        buttons = QHBoxLayout()
        buttons.addWidget(add_btn)
        buttons.addWidget(toggle_btn)
        buttons.addWidget(refresh_btn)
        buttons.addStretch()

        close_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        close_box.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(self.table)
        layout.addLayout(form)
        layout.addLayout(buttons)
        layout.addWidget(close_box)

        self.reload()

    def reload(self) -> None:
        rows = models_svc.get_all_models()
        self.table.setRowCount(len(rows))
        for i, model in enumerate(rows):
            self.table.setItem(i, 0, QTableWidgetItem(str(model.id)))
            self.table.setItem(i, 1, QTableWidgetItem(model.name))
            self.table.setItem(i, 2, QTableWidgetItem(model.api_url))
            self.table.setItem(i, 3, QTableWidgetItem(model.api_key_env))
            self.table.setItem(i, 4, QTableWidgetItem("да" if model.is_active else "нет"))

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
        self.url_edit.clear()
        self.key_env_edit.clear()
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


class SavedResultsDialog(QDialog):
    """Просмотр сохранённых результатов."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Сохранённые результаты")
        self.resize(800, 400)

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(
            ["Дата", "Модель", "Промт", "Ответ", "ID"]
        )
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)

        close_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        close_box.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(self.table)
        layout.addWidget(close_box)
        self.reload()

    def reload(self) -> None:
        rows = db.list_results()
        self.table.setRowCount(len(rows))
        for i, item in enumerate(rows):
            prompt_preview = (item["prompt_text"] or "")[:80]
            response_preview = (item["response"] or "")[:120]
            self.table.setItem(i, 0, QTableWidgetItem(item["created_at"]))
            self.table.setItem(i, 1, QTableWidgetItem(item["model_name"]))
            self.table.setItem(i, 2, QTableWidgetItem(prompt_preview))
            self.table.setItem(i, 3, QTableWidgetItem(response_preview))
            self.table.setItem(i, 4, QTableWidgetItem(str(item["id"])))


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("ChatList")
        self.resize(900, 640)

        db.init_db()
        self.temp_results = TempResultsTable()

        self.prompt_combo = QComboBox()
        self.prompt_combo.setEditable(False)
        self.prompt_combo.currentIndexChanged.connect(self.on_prompt_selected)

        self.prompt_edit = QTextEdit()
        self.prompt_edit.setPlaceholderText("Введите промт…")

        self.tags_edit = QLineEdit()
        self.tags_edit.setPlaceholderText("Теги (через запятую), необязательно")

        send_btn = QPushButton("Отправить")
        send_btn.clicked.connect(self.on_send)
        save_btn = QPushButton("Сохранить")
        save_btn.clicked.connect(self.on_save)
        models_btn = QPushButton("Модели…")
        models_btn.clicked.connect(self.open_models)
        results_btn = QPushButton("Сохранённые…")
        results_btn.clicked.connect(self.open_saved_results)

        top_buttons = QHBoxLayout()
        top_buttons.addWidget(send_btn)
        top_buttons.addWidget(save_btn)
        top_buttons.addStretch()
        top_buttons.addWidget(models_btn)
        top_buttons.addWidget(results_btn)

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

        self.status_label = QLabel("Готово")

        central = QWidget()
        layout = QVBoxLayout(central)
        layout.addWidget(QLabel("Сохранённые промты:"))
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

    def reload_prompts(self) -> None:
        self.prompt_combo.blockSignals(True)
        self.prompt_combo.clear()
        self.prompt_combo.addItem("— новый промт —", None)
        for item in db.list_prompts():
            preview = item["text"].replace("\n", " ")[:60]
            self.prompt_combo.addItem(f"#{item['id']}: {preview}", item["id"])
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

        self.status_label.setText("Отправка запросов…")
        QApplication.processEvents()

        # Новый запрос — временная таблица очищается и создаётся заново.
        self.temp_results.clear()
        self.render_temp_results()

        responses = network.send_prompt_to_models(active, prompt_text)
        self.temp_results.load_from_responses(prompt_text, responses)
        self.render_temp_results()
        self.status_label.setText(f"Получено ответов: {len(responses)}")

    def on_save(self) -> None:
        selected = self.temp_results.to_save_items()
        if not selected:
            QMessageBox.information(
                self,
                "ChatList",
                "Отметьте хотя бы один успешный результат.",
            )
            return

        prompt_text = self.temp_results.prompt_text or self.prompt_edit.toPlainText().strip()
        tags = self.tags_edit.text().strip() or None
        prompt_id = self.temp_results.prompt_id
        if prompt_id is None:
            prompt_id = db.add_prompt(prompt_text, tags=tags)
            self.temp_results.prompt_id = prompt_id

        db.save_results(prompt_id, selected)
        self.temp_results.clear()
        self.render_temp_results()
        self.reload_prompts()
        self.status_label.setText(f"Сохранено в results, prompt_id={prompt_id}")
        QMessageBox.information(self, "ChatList", "Выбранные результаты сохранены.")

    def render_temp_results(self) -> None:
        rows = self.temp_results.rows
        self.results_table.setRowCount(len(rows))
        for i, row in enumerate(rows):
            name_item = QTableWidgetItem(row.model_name)
            name_item.setFlags(name_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            response_item = QTableWidgetItem(row.response)
            response_item.setFlags(response_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
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

    def open_models(self) -> None:
        dialog = ModelsDialog(self)
        dialog.exec()

    def open_saved_results(self) -> None:
        dialog = SavedResultsDialog(self)
        dialog.exec()


def main() -> None:
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
