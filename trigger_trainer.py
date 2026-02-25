#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Тренер триггеров — обучение на размеченных скриншотах.
Запускай отдельно или из основного приложения.
"""
import json
from pathlib import Path

TRIGGER_DB_FILE = Path("trigger_knowledge.json")

def load_trigger_db() -> dict:
    if TRIGGER_DB_FILE.exists():
        try:
            return json.loads(TRIGGER_DB_FILE.read_text(encoding="utf-8"))
        except:
            pass
    return {
        "labeled": [],      # размеченные примеры {file, cat, hosp, ocr_texts, features}
        "cat_keywords": {
            "TAB": [], "VAC": [], "PMP": []
        },
        "version": 1
    }

def save_trigger_db(db: dict):
    TRIGGER_DB_FILE.write_text(
        json.dumps(db, indent=2, ensure_ascii=False), encoding="utf-8"
    )