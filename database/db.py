import asyncpg
import os
from config import DB_PATH

# Берём URL из переменной окружения Railway
DATABASE_URL = os.getenv("DATABASE_URL", "").replace("postgres://", "postgresql://")

_pool = None


async def get_pool():
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=5)
    return _pool


async def init_db():
    pool = await get_pool()
    async with pool.acquire() as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS clients (
                id SERIAL PRIMARY KEY,
                telegram_id BIGINT UNIQUE NOT NULL,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                phone TEXT,
                registered_at TIMESTAMP DEFAULT NOW(),
                is_blocked INTEGER DEFAULT 0
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS services (
                id SERIAL PRIMARY KEY,
                name TEXT NOT NULL,
                duration_minutes INTEGER DEFAULT 60,
                price INTEGER DEFAULT 0,
                is_active INTEGER DEFAULT 1
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS appointments (
                id SERIAL PRIMARY KEY,
                client_id INTEGER NOT NULL REFERENCES clients(id),
                service_id INTEGER NOT NULL REFERENCES services(id),
                appointment_date TEXT NOT NULL,
                appointment_time TEXT NOT NULL,
                status TEXT DEFAULT 'pending',
                cancel_reason TEXT,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS broadcasts (
                id SERIAL PRIMARY KEY,
                message TEXT NOT NULL,
                sent_count INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)
        # Услуги — вставляем только если таблица пустая
        count = await db.fetchval("SELECT COUNT(*) FROM services")
        if count == 0:
            await db.execute("""
                INSERT INTO services (name, duration_minutes, price) VALUES
                ('🤨 Коррекция бровей',           30,  500),
                ('🎨 Окрашивание бровей',          45,  700),
                ('👁 Окрашивание ресниц',           30,  500),
                ('✂️ Стрижка женская',             60,  1500),
                ('✂️ Стрижка мужская',             45,  800),
                ('👧 Стрижка детская',             30,  600),
                ('🎨 Окрашивание волос',           120, 3500),
                ('🌈 Тонирование',                  90, 2500),
                ('✨ Мелирование',                 120, 3000),
                ('🌅 Омбре',                       150, 4000),
                ('🎭 Колорирование',               120, 3500),
                ('🔥 Сложное окрашивание',         180, 6000),
                ('💎 Кератиновое выпрямление',     180, 5000),
                ('🌀 Химическая завивка',          150, 4000),
                ('🌿 Биохимия',                    150, 4500),
                ('💆 Укладка',                      60, 1000),
                ('🌙 Вечерняя/свадебная укладка',  120, 3000),
                ('🌀 Локоны/керли',                 90, 2000),
                ('💧 Мытьё волос',                  30,  400),
                ('💅 Маникюр женский',              90, 1500),
                ('🧔 Маникюр мужской',              60, 1000),
                ('👶 Маникюр детский',              45,  700),
                ('🦾 Маникюр аппаратный',           90, 1800),
                ('🦶 Педикюр женский',             120, 2000),
                ('🧔 Педикюр мужской',             100, 1500),
                ('🦾 Педикюр аппаратный',          120, 2200),
                ('💎 Дизайн ногтей',                60, 1000),
                ('💄 Макияж',                       90, 2500),
                ('✒️ Перманентный макияж',         180, 8000),
                ('💆 Массаж',                       60, 2000),
                ('🌿 Уход за телом',                90, 2500)
            """)


# ─── КЛИЕНТЫ ───────────────────────────────────────────────

async def add_client(telegram_id: int, username: str, first_name: str):
    pool = await get_pool()
    async with pool.acquire() as db:
        await db.execute("""
            INSERT INTO clients (telegram_id, username, first_name)
            VALUES ($1, $2, $3)
            ON CONFLICT (telegram_id) DO NOTHING
        """, telegram_id, username, first_name)


async def update_client_name(telegram_id: int, first_name: str, last_name: str):
    pool = await get_pool()
    async with pool.acquire() as db:
        await db.execute(
            "UPDATE clients SET first_name=$1, last_name=$2 WHERE telegram_id=$3",
            first_name, last_name, telegram_id
        )


async def save_phone(telegram_id: int, phone: str):
    pool = await get_pool()
    async with pool.acquire() as db:
        await db.execute(
            "UPDATE clients SET phone=$1 WHERE telegram_id=$2",
            phone, telegram_id
        )


async def is_registered(telegram_id: int) -> bool:
    pool = await get_pool()
    async with pool.acquire() as db:
        row = await db.fetchrow(
            "SELECT phone, last_name FROM clients WHERE telegram_id=$1", telegram_id
        )
        return bool(row and row["phone"] and row["last_name"])


async def get_client(telegram_id: int):
    pool = await get_pool()
    async with pool.acquire() as db:
        return await db.fetchrow("SELECT * FROM clients WHERE telegram_id=$1", telegram_id)


async def get_all_clients():
    pool = await get_pool()
    async with pool.acquire() as db:
        return await db.fetch("SELECT * FROM clients WHERE is_blocked=0 ORDER BY registered_at DESC")


async def get_clients_count():
    pool = await get_pool()
    async with pool.acquire() as db:
        return await db.fetchval("SELECT COUNT(*) FROM clients")


async def search_clients(query: str):
    pool = await get_pool()
    async with pool.acquire() as db:
        return await db.fetch("""
            SELECT * FROM clients
            WHERE first_name ILIKE $1 OR last_name ILIKE $1 OR phone ILIKE $1
        """, f"%{query}%")


# ─── УСЛУГИ ────────────────────────────────────────────────

async def get_services():
    pool = await get_pool()
    async with pool.acquire() as db:
        return await db.fetch("SELECT * FROM services WHERE is_active=1 ORDER BY id")


async def get_service(service_id: int):
    pool = await get_pool()
    async with pool.acquire() as db:
        return await db.fetchrow("SELECT * FROM services WHERE id=$1", service_id)


# ─── ЗАПИСИ ────────────────────────────────────────────────

async def create_appointment(client_id: int, service_id: int, date: str, time: str):
    pool = await get_pool()
    async with pool.acquire() as db:
        return await db.fetchval("""
            INSERT INTO appointments (client_id, service_id, appointment_date, appointment_time)
            VALUES ($1, $2, $3, $4) RETURNING id
        """, client_id, service_id, date, time)


async def get_booked_slots(date: str):
    pool = await get_pool()
    async with pool.acquire() as db:
        return await db.fetch("""
            SELECT a.appointment_time, s.duration_minutes
            FROM appointments a
            JOIN services s ON a.service_id=s.id
            WHERE a.appointment_date=$1 AND a.status != 'cancelled'
        """, date)


async def get_appointment_by_id(appointment_id: int):
    pool = await get_pool()
    async with pool.acquire() as db:
        return await db.fetchrow("""
            SELECT a.id,
                   TRIM(c.first_name || ' ' || COALESCE(c.last_name,'')) as name,
                   c.phone, c.telegram_id,
                   s.name as service_name, a.appointment_date, a.appointment_time,
                   a.status, s.duration_minutes, a.cancel_reason
            FROM appointments a
            JOIN clients c ON a.client_id=c.id
            JOIN services s ON a.service_id=s.id
            WHERE a.id=$1
        """, appointment_id)


async def get_all_appointments(limit: int = 20):
    pool = await get_pool()
    async with pool.acquire() as db:
        return await db.fetch("""
            SELECT a.id,
                   TRIM(c.first_name || ' ' || COALESCE(c.last_name,'')) as name,
                   c.phone, c.telegram_id,
                   s.name as service_name, a.appointment_date, a.appointment_time,
                   a.status, a.created_at
            FROM appointments a
            JOIN clients c ON a.client_id=c.id
            JOIN services s ON a.service_id=s.id
            ORDER BY a.appointment_date DESC, a.appointment_time DESC
            LIMIT $1
        """, limit)


async def get_today_appointments(today: str):
    pool = await get_pool()
    async with pool.acquire() as db:
        return await db.fetch("""
            SELECT a.id,
                   TRIM(c.first_name || ' ' || COALESCE(c.last_name,'')) as name,
                   c.phone, c.telegram_id,
                   s.name as service_name, a.appointment_date, a.appointment_time, a.status
            FROM appointments a
            JOIN clients c ON a.client_id=c.id
            JOIN services s ON a.service_id=s.id
            WHERE a.appointment_date=$1 AND a.status != 'cancelled'
            ORDER BY a.appointment_time
        """, today)


async def cancel_appointment(appointment_id: int, reason: str = ""):
    pool = await get_pool()
    async with pool.acquire() as db:
        await db.execute(
            "UPDATE appointments SET status='cancelled', cancel_reason=$1 WHERE id=$2",
            reason, appointment_id
        )


async def confirm_appointment(appointment_id: int):
    pool = await get_pool()
    async with pool.acquire() as db:
        await db.execute(
            "UPDATE appointments SET status='confirmed' WHERE id=$1", appointment_id
        )


async def get_client_appointments(telegram_id: int):
    pool = await get_pool()
    async with pool.acquire() as db:
        return await db.fetch("""
            SELECT a.id, s.name, a.appointment_date, a.appointment_time, a.status
            FROM appointments a
            JOIN clients c ON a.client_id=c.id
            JOIN services s ON a.service_id=s.id
            WHERE c.telegram_id=$1 AND a.status != 'cancelled'
            ORDER BY a.appointment_date ASC, a.appointment_time ASC
            LIMIT 5
        """, telegram_id)


async def get_appointments_count():
    pool = await get_pool()
    async with pool.acquire() as db:
        return await db.fetchval(
            "SELECT COUNT(*) FROM appointments WHERE status != 'cancelled'"
        )


async def delete_old_appointments():
    from datetime import datetime, timedelta
    pool = await get_pool()
    async with pool.acquire() as db:
        rows = await db.fetch("""
            SELECT a.id, a.appointment_date, a.appointment_time, s.duration_minutes
            FROM appointments a
            JOIN services s ON a.service_id=s.id
        """)
        now = datetime.now()
        to_delete = []
        for row in rows:
            try:
                start = datetime.strptime(f"{row['appointment_date']} {row['appointment_time']}", "%Y-%m-%d %H:%M")
                if start + timedelta(minutes=row["duration_minutes"]) < now:
                    to_delete.append(row["id"])
            except Exception:
                pass
        if to_delete:
            await db.execute(
                f"DELETE FROM appointments WHERE id = ANY($1::int[])", to_delete
            )
        return len(to_delete)


async def get_service_stats():
    pool = await get_pool()
    async with pool.acquire() as db:
        return await db.fetch("""
            SELECT s.name, COUNT(a.id) as cnt, SUM(s.price) as revenue
            FROM appointments a
            JOIN services s ON a.service_id=s.id
            WHERE a.status != 'cancelled'
            GROUP BY s.id, s.name
            ORDER BY cnt DESC
        """)


# ─── РАССЫЛКИ ──────────────────────────────────────────────

async def save_broadcast(message: str, sent_count: int):
    pool = await get_pool()
    async with pool.acquire() as db:
        await db.execute(
            "INSERT INTO broadcasts (message, sent_count) VALUES ($1, $2)",
            message, sent_count
        )