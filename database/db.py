import aiosqlite
from config import DB_PATH


async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS clients (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER UNIQUE NOT NULL,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                phone TEXT,
                registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_blocked INTEGER DEFAULT 0
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS services (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                duration_minutes INTEGER DEFAULT 60,
                price INTEGER DEFAULT 0,
                is_active INTEGER DEFAULT 1
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS appointments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                client_id INTEGER NOT NULL,
                service_id INTEGER NOT NULL,
                appointment_date TEXT NOT NULL,
                appointment_time TEXT NOT NULL,
                status TEXT DEFAULT 'pending',
                cancel_reason TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (client_id) REFERENCES clients(id),
                FOREIGN KEY (service_id) REFERENCES services(id)
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS broadcasts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                message TEXT NOT NULL,
                sent_count INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.execute("""
            INSERT OR IGNORE INTO services (id, name, duration_minutes, price) VALUES
            -- Косметологические услуги
            (1,  '🤨 Коррекция бровей',            30,  500),
            (2,  '🎨 Окрашивание бровей',           45,  700),
            (3,  '👁 Окрашивание ресниц',            30,  500),
            -- Парикмахерские услуги
            (4,  '✂️ Стрижка женская',              60,  1500),
            (5,  '✂️ Стрижка мужская',              45,  800),
            (6,  '👧 Стрижка детская',              30,  600),
            (7,  '🎨 Окрашивание волос',            120, 3500),
            (8,  '🌈 Тонирование',                   90, 2500),
            (9,  '✨ Мелирование',                  120, 3000),
            (10, '🌅 Омбре',                        150, 4000),
            (11, '🎭 Колорирование',                120, 3500),
            (12, '🔥 Сложное окрашивание',          180, 6000),
            (13, '💎 Кератиновое выпрямление',      180, 5000),
            (14, '🌀 Химическая завивка',           150, 4000),
            (15, '🌿 Биохимия',                    150, 4500),
            (16, '💆 Укладка',                      60,  1000),
            (17, '🌙 Вечерняя/свадебная укладка',  120, 3000),
            (18, '🌀 Локоны/керли',                  90, 2000),
            (19, '💧 Мытьё волос',                   30,  400),
            -- Ногтевой сервис
            (20, '💅 Маникюр женский',               90, 1500),
            (21, '🧔 Маникюр мужской',               60, 1000),
            (22, '👶 Маникюр детский',               45,  700),
            (23, '🦾 Маникюр аппаратный',            90, 1800),
            (24, '🦶 Педикюр женский',              120, 2000),
            (25, '🧔 Педикюр мужской',              100, 1500),
            (26, '🦾 Педикюр аппаратный',           120, 2200),
            (27, '💎 Дизайн ногтей',                 60, 1000),
            -- Услуги салона
            (28, '💄 Макияж',                        90, 2500),
            (29, '✒️ Перманентный макияж',           180, 8000),
            (30, '💆 Массаж',                        60, 2000),
            (31, '🌿 Уход за телом',                  90, 2500)
        """)
        await db.commit()


# ─── КЛИЕНТЫ ───────────────────────────────────────────────

async def add_client(telegram_id: int, username: str, first_name: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT OR IGNORE INTO clients (telegram_id, username, first_name)
            VALUES (?, ?, ?)
        """, (telegram_id, username, first_name))
        await db.commit()


async def update_client_name(telegram_id: int, first_name: str, last_name: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE clients SET first_name=?, last_name=? WHERE telegram_id=?",
            (first_name, last_name, telegram_id)
        )
        await db.commit()


async def save_phone(telegram_id: int, phone: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE clients SET phone=? WHERE telegram_id=?",
            (phone, telegram_id)
        )
        await db.commit()


async def is_registered(telegram_id: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT phone, first_name, last_name FROM clients WHERE telegram_id=?",
            (telegram_id,)
        ) as cursor:
            row = await cursor.fetchone()
            if not row:
                return False
            phone, first_name, last_name = row
            return bool(phone and last_name)


async def get_client(telegram_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT * FROM clients WHERE telegram_id=?", (telegram_id,)
        ) as cursor:
            return await cursor.fetchone()


async def get_all_clients():
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT * FROM clients WHERE is_blocked=0 ORDER BY registered_at DESC"
        ) as cursor:
            return await cursor.fetchall()


async def get_clients_count():
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT COUNT(*) FROM clients") as cursor:
            return (await cursor.fetchone())[0]


async def search_clients(query: str):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("""
            SELECT * FROM clients
            WHERE first_name LIKE ? OR last_name LIKE ? OR phone LIKE ?
        """, (f"%{query}%", f"%{query}%", f"%{query}%")) as cursor:
            return await cursor.fetchall()


# ─── УСЛУГИ ────────────────────────────────────────────────

async def get_services():
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT * FROM services WHERE is_active=1") as cursor:
            return await cursor.fetchall()


async def get_service(service_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT * FROM services WHERE id=?", (service_id,)) as cursor:
            return await cursor.fetchone()


# ─── ЗАПИСИ ────────────────────────────────────────────────

async def create_appointment(client_id: int, service_id: int, date: str, time: str):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("""
            INSERT INTO appointments (client_id, service_id, appointment_date, appointment_time)
            VALUES (?, ?, ?, ?)
        """, (client_id, service_id, date, time))
        await db.commit()
        return cursor.lastrowid


async def get_booked_slots(date: str):
    """Возвращает список (время_начала, длительность_минут) для занятых слотов"""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("""
            SELECT a.appointment_time, s.duration_minutes
            FROM appointments a
            JOIN services s ON a.service_id = s.id
            WHERE a.appointment_date=? AND a.status != 'cancelled'
        """, (date,)) as cursor:
            return await cursor.fetchall()


async def get_appointment_by_id(appointment_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("""
            SELECT a.id, c.first_name || ' ' || COALESCE(c.last_name,'') as name,
                   c.phone, c.telegram_id,
                   s.name, a.appointment_date, a.appointment_time, a.status,
                   s.duration_minutes, a.cancel_reason
            FROM appointments a
            JOIN clients c ON a.client_id=c.id
            JOIN services s ON a.service_id=s.id
            WHERE a.id=?
        """, (appointment_id,)) as cursor:
            return await cursor.fetchone()


async def get_all_appointments(limit: int = 20):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("""
            SELECT a.id,
                   c.first_name || ' ' || COALESCE(c.last_name,'') as name,
                   c.phone, c.telegram_id,
                   s.name, a.appointment_date, a.appointment_time, a.status, a.created_at
            FROM appointments a
            JOIN clients c ON a.client_id=c.id
            JOIN services s ON a.service_id=s.id
            ORDER BY a.appointment_date DESC, a.appointment_time DESC
            LIMIT ?
        """, (limit,)) as cursor:
            return await cursor.fetchall()


async def get_today_appointments(today: str):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("""
            SELECT a.id,
                   c.first_name || ' ' || COALESCE(c.last_name,'') as name,
                   c.phone, c.telegram_id,
                   s.name, a.appointment_date, a.appointment_time, a.status
            FROM appointments a
            JOIN clients c ON a.client_id=c.id
            JOIN services s ON a.service_id=s.id
            WHERE a.appointment_date=? AND a.status != 'cancelled'
            ORDER BY a.appointment_time
        """, (today,)) as cursor:
            return await cursor.fetchall()


async def cancel_appointment(appointment_id: int, reason: str = ""):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE appointments SET status='cancelled', cancel_reason=? WHERE id=?",
            (reason, appointment_id)
        )
        await db.commit()


async def confirm_appointment(appointment_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE appointments SET status='confirmed' WHERE id=?",
            (appointment_id,)
        )
        await db.commit()


async def get_client_appointments(telegram_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("""
            SELECT a.id, s.name, a.appointment_date, a.appointment_time, a.status
            FROM appointments a
            JOIN clients c ON a.client_id=c.id
            JOIN services s ON a.service_id=s.id
            WHERE c.telegram_id=? AND a.status != 'cancelled'
            ORDER BY a.appointment_date ASC, a.appointment_time ASC
            LIMIT 5
        """, (telegram_id,)) as cursor:
            return await cursor.fetchall()


async def get_appointments_count():
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT COUNT(*) FROM appointments WHERE status != 'cancelled'"
        ) as cursor:
            return (await cursor.fetchone())[0]


async def delete_old_appointments():
    """Удаляет записи которые уже прошли (дата+время окончания < сейчас)"""
    from datetime import datetime, timedelta
    async with aiosqlite.connect(DB_PATH) as db:
        # Получаем все записи с датой/временем и длительностью
        async with db.execute("""
            SELECT a.id, a.appointment_date, a.appointment_time, s.duration_minutes
            FROM appointments a
            JOIN services s ON a.service_id=s.id
        """) as cursor:
            rows = await cursor.fetchall()

        now = datetime.now()
        to_delete = []
        for row in rows:
            app_id, date_str, time_str, duration = row
            try:
                start = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
                end = start + timedelta(minutes=duration)
                if end < now:
                    to_delete.append(app_id)
            except Exception:
                pass

        if to_delete:
            await db.execute(
                f"DELETE FROM appointments WHERE id IN ({','.join('?' * len(to_delete))})",
                to_delete
            )
            await db.commit()
            return len(to_delete)
        return 0


async def get_service_stats():
    """Статистика по услугам — сколько раз заказывали"""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("""
            SELECT s.name, COUNT(a.id) as cnt, SUM(s.price) as revenue
            FROM appointments a
            JOIN services s ON a.service_id=s.id
            WHERE a.status != 'cancelled'
            GROUP BY s.id
            ORDER BY cnt DESC
        """) as cursor:
            return await cursor.fetchall()


# ─── РАССЫЛКИ ──────────────────────────────────────────────

async def save_broadcast(message: str, sent_count: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO broadcasts (message, sent_count) VALUES (?, ?)",
            (message, sent_count)
        )
        await db.commit()