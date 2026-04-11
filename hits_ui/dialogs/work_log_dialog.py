"""Work log dialog for adding/editing work logs."""

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
    QLineEdit, QTextEdit, QPushButton, QWidget
)
from PySide6.QtCore import Qt

from ..theme.material_dark import Theme
from hits_core.models.work_log import WorkLog, WorkLogSource, WorkLogResultType


class WorkLogDialog(QDialog):
    def __init__(self, parent=None, log: Optional[WorkLog] = None):
        super().__init__(parent)
        self.log = log
        self._result_data = log.result_data if log else None
        
        self.setWindowTitle("작업 기록 편집" if log else "작업 기록 추가")
        self.setMinimumWidth(400)
        self.setAttribute(Qt.WA_InputMethodEnabled, True)
        
        self.setStyleSheet(f"""
            QDialog {{
                background: {Theme.COLORS['surface']};
            }}
            QLabel {{
                color: {Theme.COLORS['on_surface']};
                font-size: 12px;
            }}
        """)
        
        self._build_ui()
        
        if log:
            self._populate_fields()
    
    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)
        
        layout.addWidget(self._create_field("수행자:", "performed_by"))
        
        layout.addWidget(self._create_field("요청 내용:", "request_text", multiline=True))
        
        layout.addWidget(self._create_field("맥락/이유:", "context", multiline=True))
        
        layout.addWidget(self._create_field("태그 (쉼표로 구분):", "tags"))
        
        layout.addWidget(self._create_field("결과 참조:", "result_ref"))
        
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        cancel_btn = QPushButton("취소")
        cancel_btn.setStyleSheet(Theme.button_style(
            Theme.COLORS['surface2'], 
            Theme.COLORS['on_surface'],
            Theme.COLORS['surface3']
        ))
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)
        
        save_btn = QPushButton("저장")
        save_btn.setStyleSheet(Theme.button_style())
        save_btn.clicked.connect(self._on_save)
        btn_layout.addWidget(save_btn)
        
        layout.addLayout(btn_layout)
    
    def _create_field(self, label: str, field_name: str, multiline: bool = False) -> QWidget:
        widget = QWidget()
        widget.setStyleSheet("background:transparent;")
        vl = QVBoxLayout(widget)
        vl.setContentsMargins(0, 0, 0, 0)
        vl.setSpacing(4)
        
        lbl = QLabel(label)
        vl.addWidget(lbl)
        
        if multiline:
            edit = QTextEdit()
            edit.setFixedHeight(80)
            edit.setStyleSheet(Theme.input_style())
        else:
            edit = QLineEdit()
            edit.setStyleSheet(Theme.input_style())
        
        edit.setAttribute(Qt.WA_InputMethodEnabled, True)
        setattr(self, f"_{field_name}_edit", edit)
        vl.addWidget(edit)
        
        return widget
    
    def _populate_fields(self):
        if not self.log:
            return
        
        self._performed_by_edit.setText(self.log.performed_by or "")
        self._request_text_edit.setText(self.log.request_text or "")
        self._context_edit.setText(self.log.context or "")
        self._tags_edit.setText(", ".join(self.log.tags) if self.log.tags else "")
        self._result_ref_edit.setText(self.log.result_ref or "")
    
    def _on_save(self):
        performed_by = self._performed_by_edit.text().strip()
        if not performed_by:
            self._performed_by_edit.setStyleSheet(Theme.input_style() + f"border: 1px solid {Theme.COLORS['danger']};")
            return
        
        request_text = self._request_text_edit.toPlainText().strip()
        context = self._context_edit.toPlainText().strip()
        tags_text = self._tags_edit.text().strip()
        tags = [t.strip() for t in tags_text.split(",") if t.strip()]
        result_ref = self._result_ref_edit.text().strip() or None
        
        now = datetime.now()
        
        if self.log:
            log_data = self.log.model_dump()
            log_data["performed_by"] = performed_by
            log_data["request_text"] = request_text
            log_data["context"] = context
            log_data["tags"] = tags
            log_data["result_ref"] = result_ref
            log_data["result_type"] = WorkLogResultType.NONE.value if not result_ref else self.log.result_type
            log_id = self.log.id
        else:
            log_id = str(uuid.uuid4())[:8]
            log_data = {
                "id": log_id,
                "source": WorkLogSource.MANUAL.value,
                "request_text": request_text,
                "performed_by": performed_by,
                "performed_at": now.isoformat(),
                "result_type": WorkLogResultType.NONE.value,
                "result_ref": result_ref,
                "context": context,
                "tags": tags,
                "created_at": now.isoformat(),
            }
        
        self._save_log(log_id, log_data)
        self.accept()
    
    def _save_log(self, log_id: str, data: dict):
        data_path = Path("./data/work_logs")
        data_path.mkdir(parents=True, exist_ok=True)
        
        log_file = data_path / f"{log_id}.json"
        with open(log_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2, default=str)
        
        index_file = data_path / "index.json"
        if index_file.exists():
            try:
                with open(index_file, "r", encoding="utf-8") as f:
                    log_ids = json.load(f)
            except Exception:
                log_ids = []
        else:
            log_ids = []
        
        if log_id not in log_ids:
            log_ids.insert(0, log_id)
        
        with open(index_file, "w", encoding="utf-8") as f:
            json.dump(log_ids, f, ensure_ascii=False, indent=2)
