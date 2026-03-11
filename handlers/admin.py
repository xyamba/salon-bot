from aiogram import Router, F, Bot
from aiogram.types import Message
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from datetime import datetime
import database.db as db
from config import ADMIN_IDS, SALON_PHONE

router = Router()


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


class BroadcastState(StatesGroup):
    waiting_message = State()


# ─── /admin — ГЛАВНОЕ МЕНЮ ─────────────────────────────────

@router.message(Command("admin"))
async def admin_panel(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("❌ Нет доступа.")
        return

    clients_count = await db.get_clients_count()
    appointments_count = await db.get_appointments_count()

    await message.answer(
        f"🔧 <b>Панель администратора</b>\n\n"
        f"👥 Клиентов в базе: <b>{clients_count}</b>\n"
        f"📅 Всего записей: <b>{appointments_count}</b>\n\n"
        f"<b>Команды:</b>\n\n"
        f"/appointments — последние 20 записей\n"
        f"/today — записи на сегодня\n"
        f"/clients — список клиентов\n"
        f"/broadcast — рассылка всем\n"
        f"/cancel_app [ID] — отменить запись",
        parse_mode="HTML"
    )


# ─── /appointments ──────────────────────────────────────────

@router.message(Command("appointments"))
async def all_appointments(message: Message):
    if not is_admin(message.from_user.id):
        return

    appointments = await db.get_all_appointments(limit=20)
    if not appointments:
        await message.answer("📋 Записей пока нет.")
        return

    text = "📋 <b>Последние 20 записей:</b>\n\n"
    for app in appointments:
        app_id, name, phone, tg_id, service, date, time, status, created = app
        icons = {"pending": "⏳", "confirmed": "✅", "cancelled": "❌", "done": "🎉"}
        icon = icons.get(status, "⏳")
        text += (
            f"{icon} <b>#{app_id}</b> | {date} {time}\n"
            f"   👤 {name} | 📱 {phone or 'нет'}\n"
            f"   💇 {service}\n\n"
        )

    if len(text) > 4000:
        text = text[:4000] + "\n\n... (показаны не все)"

    await message.answer(text, parse_mode="HTML")


# ─── /today ─────────────────────────────────────────────────

@router.message(Command("today"))
async def today_appointments(message: Message):
    if not is_admin(message.from_user.id):
        return

    today = datetime.now().strftime("%Y-%m-%d")
    today_display = datetime.now().strftime("%d.%m.%Y")
    appointments = await db.get_today_appointments(today)

    if not appointments:
        await message.answer(f"📅 На сегодня ({today_display}) записей нет.")
        return

    text = f"📅 <b>Записи на {today_display}:</b>\n\n"
    for app in appointments:
        app_id, name, phone, tg_id, service, date, time, status = app
        text += (
            f"🕐 <b>{time}</b> — {service}\n"
            f"   👤 {name}\n"
            f"   📱 {phone or 'не указан'}\n"
            f"   🆔 #{app_id}\n\n"
        )

    await message.answer(text, parse_mode="HTML")


# ─── /clients ───────────────────────────────────────────────

@router.message(Command("clients"))
async def list_clients(message: Message):
    if not is_admin(message.from_user.id):
        return

    clients = await db.get_all_clients()
    if not clients:
        await message.answer("👥 Клиентов пока нет.")
        return

    text = f"👥 <b>База клиентов ({len(clients)} чел.):</b>\n\n"
    for i, client in enumerate(clients[:30], 1):
        c_id, tg_id, username, first_name, last_name, phone, reg_date, blocked = client
        full_name = f"{first_name} {last_name}".strip() if last_name else first_name
        text += (
            f"{i}. <b>{full_name}</b>\n"
            f"   📱 {phone or 'нет'} | @{username or 'нет'}\n"
            f"   📅 С {reg_date[:10]}\n\n"
        )

    if len(clients) > 30:
        text += f"... и ещё {len(clients) - 30} клиентов"

    await message.answer(text, parse_mode="HTML")


# ─── /cancel_app ────────────────────────────────────────────

@router.message(Command("cancel_app"))
async def cancel_appointment(message: Message, bot: Bot):
    if not is_admin(message.from_user.id):
        return

    args = message.text.split()
    if len(args) < 2 or not args[1].isdigit():
        await message.answer("❌ Использование: /cancel_app [ID]\nПример: /cancel_app 5")
        return

    app_id = int(args[1])

    # Ищем запись ДО отмены
    target = await db.get_appointment_by_id(app_id)

    if not target:
        await message.answer(f"❌ Запись #{app_id} не найдена.")
        return

    if target[7] == "cancelled":
        await message.answer(f"⚠️ Запись #{app_id} уже была отменена ранее.")
        return

    await db.cancel_appointment(app_id)
    await message.answer(f"✅ Запись #{app_id} отменена.")

    # Уведомляем клиента
    client_tg_id = target[3]
    service = target[4]
    date = target[5]
    time = target[6]
    date_display = datetime.strptime(date, "%Y-%m-%d").strftime("%d.%m.%Y")

    try:
        await bot.send_message(
            client_tg_id,
            f"⚠️ <b>Ваша запись отменена</b>\n\n"
            f"💇 {service}\n"
            f"📅 {date_display} в {time}\n\n"
            f"Для переноса свяжитесь с нами:\n📞 {SALON_PHONE}",
            parse_mode="HTML"
        )
    except Exception:
        await message.answer("⚠️ Не удалось отправить уведомление клиенту (возможно, заблокировал бота).")


# ─── /broadcast ─────────────────────────────────────────────

@router.message(Command("broadcast"))
async def start_broadcast(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return

    clients_count = await db.get_clients_count()
    await message.answer(
        f"📢 <b>Создание рассылки</b>\n\n"
        f"👥 Получателей: <b>{clients_count}</b>\n\n"
        f"Отправьте сообщение для рассылки.\n"
        f"Можно:\n"
        f"• Просто текст\n"
        f"• Фото с подписью\n"
        f"• Фото без подписи\n\n"
        f"Для отмены: /cancel",
        parse_mode="HTML"
    )
    await state.set_state(BroadcastState.waiting_message)


@router.message(BroadcastState.waiting_message, Command("cancel"))
async def cancel_broadcast(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("❌ Рассылка отменена.")


@router.message(BroadcastState.waiting_message, F.photo)
async def send_broadcast_photo(message: Message, state: FSMContext, bot: Bot):
    caption = message.caption or ""
    photo_id = message.photo[-1].file_id
    full_caption = f"📢 <b>Сообщение от салона</b>\n\n{caption}" if caption else "📢 <b>Сообщение от салона</b>"

    clients = await db.get_all_clients()
    await state.clear()

    sent = 0
    failed = 0
    status_msg = await message.answer(f"📤 Отправляем фото... 0/{len(clients)}")

    for i, client in enumerate(clients):
        tg_id = client[1]
        try:
            await bot.send_photo(
                tg_id,
                photo=photo_id,
                caption=full_caption,
                parse_mode="HTML"
            )
            sent += 1
        except Exception:
            failed += 1

        if (i + 1) % 10 == 0:
            try:
                await status_msg.edit_text(f"📤 Отправляем фото... {i+1}/{len(clients)}")
            except Exception:
                pass

    await db.save_broadcast(f"[ФОТО] {caption}", sent)
    await status_msg.edit_text(
        f"✅ <b>Рассылка завершена!</b>\n\n"
        f"📨 Отправлено: <b>{sent}</b>\n"
        f"❌ Ошибок: <b>{failed}</b>",
        parse_mode="HTML"
    )


@router.message(BroadcastState.waiting_message)
async def send_broadcast_text(message: Message, state: FSMContext, bot: Bot):
    broadcast_text = message.text or ""
    if not broadcast_text:
        await message.answer("❌ Отправьте текст или фото:")
        return

    clients = await db.get_all_clients()
    await state.clear()

    sent = 0
    failed = 0
    status_msg = await message.answer(f"📤 Отправляем... 0/{len(clients)}")

    for i, client in enumerate(clients):
        tg_id = client[1]
        try:
            await bot.send_message(
                tg_id,
                f"📢 <b>Сообщение от салона</b>\n\n{broadcast_text}",
                parse_mode="HTML"
            )
            sent += 1
        except Exception:
            failed += 1

        if (i + 1) % 10 == 0:
            try:
                await status_msg.edit_text(f"📤 Отправляем... {i+1}/{len(clients)}")
            except Exception:
                pass

    await db.save_broadcast(broadcast_text, sent)
    await status_msg.edit_text(
        f"✅ <b>Рассылка завершена!</b>\n\n"
        f"📨 Отправлено: <b>{sent}</b>\n"
        f"❌ Ошибок: <b>{failed}</b>",
        parse_mode="HTML"
    )