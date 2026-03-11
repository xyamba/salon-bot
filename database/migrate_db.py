"""
Запусти этот скрипт ОДИН РАЗ если уже была старая база данных:
    python migrate_db.py
"""
import sqlite3
from config import DB_PATH

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

# Добавляем last_name если её нет
try:
    cursor.execute("ALTER TABLE clients ADD COLUMN last_name TEXT")
    print("✅ Колонка last_name добавлена")
except Exception:
    print("ℹ️  Колонка last_name уже есть")

conn.commit()
conn.close()
print("✅ Миграция завершена")