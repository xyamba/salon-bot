from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from datetime import datetime
import database.db as db
from config import ADMIN_IDS, SALON_PHONE

router = Router()


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


class BroadcastState(StatesGroup):
    waiting_message = State()


class CancelState(StatesGroup):
    waiting_reason = State()


# ─── /admin ─────────────────────────────────────────────────

@router.message(Command("admin"))
async def admin_panel(message: Message):
    if not is_admin(message.from_user.id):
        return

    clients_count = await db.get_clients_count()
    appointments_count = await db.get_appointments_count()
    stats = await db.get_service_stats()

    top_service = f"{stats[0][0]} ({stats[0][1]} раз)" if stats else "нет данных"

    await message.answer(
        f"🔧 <b>Панель администратора</b>\n\n"
        f"👥 Клиентов: <b>{clients_count}</b>\n"
        f"📅 Активных записей: <b>{appointments_count}</b>\n"
        f"🏆 Топ услуга: <b>{top_service}</b>\n\n"
        f"<b>Команды:</b>\n"
        f"/appointments — последние записи\n"
        f"/today — расписание на сегодня\n"
        f"/clients — база клиентов\n"
        f"/search [имя/телефон] — поиск клиента\n"
        f"/stats — статистика по услугам\n"
        f"/confirm [ID] — подтвердить запись\n"
        f"/cancel_app [ID] — отменить запись\n"
        f"/broadcast — рассылка всем\n"
        f"/cleanup — удалить прошедшие записи",
        parse_mode="HTML"
    )


# ─── /appointments ──────────────────────────────────────────

@router.message(Command("appointments"))
async def all_appointments(message: Message):
    if not is_admin(message.from_user.id):
        return

    appointments = await db.get_all_appointments(20)
    if not appointments:
        await message.answer("📋 Записей пока нет.")
        return

    text = "📋 <b>Последние 20 записей:</b>\n\n"
    for app in appointments:
        icons = {"pending": "⏳", "confirmed": "✅", "cancelled": "❌", "done": "🎉"}
        icon = icons.get(app[7], "⏳")
        text += (
            f"{icon} <b>#{app[0]}</b> | {app[5]} {app[6]}\n"
            f"   👤 {app[1].strip()} | 📱 {app[2] or 'нет'}\n"
            f"   💇 {app[4]}\n\n"
        )
    if len(text) > 4000:
        text = text[:4000] + "..."
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

    text = f"📅 <b>Расписание на {today_display}:</b>\n\n"
    for app in appointments:
        icon = "✅" if app[7] == "confirmed" else "⏳"
        text += (
            f"{icon} <b>{app[6]}</b> — {app[4]}\n"
            f"   👤 {app[1].strip()} | 📱 {app[2] or 'нет'}\n"
            f"   🆔 #{app[0]}\n\n"
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
    for i, c in enumerate(clients[:30], 1):
        name = f"{c[3] or ''} {c[4] or ''}".strip() or "Без имени"
        text += f"{i}. <b>{name}</b>\n   📱 {c[5] or 'нет'} | @{c[2] or 'нет'}\n   📅 С {c[6][:10]}\n\n"

    if len(clients) > 30:
        text += f"... и ещё {len(clients) - 30}"
    await message.answer(text, parse_mode="HTML")


# ─── /search ────────────────────────────────────────────────

@router.message(Command("search"))
async def search_client(message: Message):
    if not is_admin(message.from_user.id):
        return

    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer("❌ Использование: /search [имя или телефон]\nПример: /search Иван")
        return

    query = args[1].strip()
    clients = await db.search_clients(query)

    if not clients:
        await message.answer(f"Клиенты по запросу «{query}» не найдены.")
        return

    text = f"🔍 <b>Результаты поиска «{query}»:</b>\n\n"
    for c in clients:
        name = f"{c[3] or ''} {c[4] or ''}".strip() or "Без имени"
        text += f"👤 <b>{name}</b>\n   📱 {c[5] or 'нет'} | @{c[2] or 'нет'}\n   🆔 TG: {c[1]}\n\n"
    await message.answer(text, parse_mode="HTML")


# ─── /stats ─────────────────────────────────────────────────

@router.message(Command("stats"))
async def service_stats(message: Message):
    if not is_admin(message.from_user.id):
        return

    stats = await db.get_service_stats()
    if not stats:
        await message.answer("📊 Статистики пока нет.")
        return

    text = "📊 <b>Статистика по услугам:</b>\n\n"
    total_revenue = 0
    for s in stats:
        name, count, revenue = s
        revenue = revenue or 0
        total_revenue += revenue
        text += f"💇 <b>{name}</b>\n   Заказов: {count} | Выручка: {revenue}₽\n\n"
    text += f"💰 <b>Общая выручка: {total_revenue}₽</b>"
    await message.answer(text, parse_mode="HTML")


# ─── /confirm ───────────────────────────────────────────────

@router.message(Command("confirm"))
async def confirm_appointment(message: Message, bot: Bot):
    if not is_admin(message.from_user.id):
        return

    args = message.text.split()
    if len(args) < 2 or not args[1].isdigit():
        await message.answer("❌ Использование: /confirm [ID]\nПример: /confirm 5")
        return

    app_id = int(args[1])
    target = await db.get_appointment_by_id(app_id)

    if not target:
        await message.answer(f"❌ Запись #{app_id} не найдена.")
        return

    await db.confirm_appointment(app_id)
    await message.answer(f"✅ Запись #{app_id} подтверждена.")

    date_display = datetime.strptime(target[5], "%Y-%m-%d").strftime("%d.%m.%Y")
    try:
        await bot.send_message(
            target[3],
            f"✅ <b>Ваша запись подтверждена!</b>\n\n"
            f"💇 {target[4]}\n"
            f"📅 {date_display} в {target[6]}\n\n"
            f"Ждём вас! 😊",
            parse_mode="HTML"
        )
    except Exception:
        pass


# ─── /cancel_app ────────────────────────────────────────────

@router.message(Command("cancel_app"))
async def cancel_appointment_start(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return

    args = message.text.split()
    if len(args) < 2 or not args[1].isdigit():
        await message.answer("❌ Использование: /cancel_app [ID]\nПример: /cancel_app 5")
        return

    app_id = int(args[1])
    target = await db.get_appointment_by_id(app_id)

    if not target:
        await message.answer(f"❌ Запись #{app_id} не найдена.")
        return
    if target[7] == "cancelled":
        await message.answer(f"⚠️ Запись #{app_id} уже отменена.")
        return

    date_display = datetime.strptime(target[5], "%Y-%m-%d").strftime("%d.%m.%Y")
    await state.update_data(cancel_app_id=app_id, cancel_app_tg=target[3],
                            cancel_service=target[4], cancel_date=date_display, cancel_time=target[6])

    builder = InlineKeyboardBuilder()
    builder.button(text="Без причины", callback_data="cancel_reason_none")
    builder.adjust(1)

    await message.answer(
        f"📝 Введите <b>причину отмены</b> записи #{app_id}:\n\n"
        f"👤 {target[1].strip()} | 💇 {target[4]}\n"
        f"📅 {date_display} в {target[6]}\n\n"
        f"Или нажмите кнопку если причина не нужна:",
        reply_markup=builder.as_markup(),
        parse_mode="HTML"
    )
    await state.set_state(CancelState.waiting_reason)


@router.callback_query(CancelState.waiting_reason, F.data == "cancel_reason_none")
async def cancel_no_reason(callback: CallbackQuery, state: FSMContext, bot: Bot):
    await do_cancel(callback.message, state, bot, reason="")
    await callback.answer()


@router.message(CancelState.waiting_reason)
async def cancel_with_reason(message: Message, state: FSMContext, bot: Bot):
    await do_cancel(message, state, bot, reason=message.text.strip())


async def do_cancel(message: Message, state: FSMContext, bot: Bot, reason: str):
    data = await state.get_data()
    app_id = data["cancel_app_id"]
    await state.clear()

    await db.cancel_appointment(app_id, reason=reason)
    await message.answer(f"✅ Запись #{app_id} отменена." + (f"\nПричина: {reason}" if reason else ""))

    reason_text = f"\n\n📝 Причина: {reason}" if reason else ""
    try:
        await bot.send_message(
            data["cancel_app_tg"],
            f"⚠️ <b>Ваша запись отменена</b>\n\n"
            f"💇 {data['cancel_service']}\n"
            f"📅 {data['cancel_date']} в {data['cancel_time']}"
            f"{reason_text}\n\n"
            f"Для переноса: 📞 {SALON_PHONE}",
            parse_mode="HTML"
        )
    except Exception:
        await message.answer("⚠️ Не удалось уведомить клиента.")


# ─── /cleanup ───────────────────────────────────────────────

@router.message(Command("cleanup"))
async def cleanup(message: Message):
    if not is_admin(message.from_user.id):
        return
    count = await db.delete_old_appointments()
    await message.answer(f"🗑 Удалено прошедших записей: <b>{count}</b>", parse_mode="HTML")


# ─── /broadcast ─────────────────────────────────────────────

@router.message(Command("broadcast"))
async def start_broadcast(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    count = await db.get_clients_count()
    await message.answer(
        f"📢 <b>Рассылка</b>\n\n👥 Получателей: <b>{count}</b>\n\n"
        f"Отправьте текст или фото.\nДля отмены: /cancel",
        parse_mode="HTML"
    )
    await state.set_state(BroadcastState.waiting_message)


@router.message(BroadcastState.waiting_message, Command("cancel"))
async def cancel_broadcast(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("❌ Рассылка отменена.")


@router.message(BroadcastState.waiting_message, F.photo)
async def broadcast_photo(message: Message, state: FSMContext, bot: Bot):
    caption = message.caption or ""
    photo_id = message.photo[-1].file_id
    full_caption = f"📢 <b>Сообщение от салона</b>\n\n{caption}" if caption else "📢 <b>Сообщение от салона</b>"
    clients = await db.get_all_clients()
    await state.clear()

    sent = 0
    failed = 0
    status_msg = await message.answer(f"📤 Отправляем... 0/{len(clients)}")
    for i, client in enumerate(clients):
        try:
            await bot.send_photo(client[1], photo=photo_id, caption=full_caption, parse_mode="HTML")
            sent += 1
        except Exception:
            failed += 1
        if (i + 1) % 10 == 0:
            try:
                await status_msg.edit_text(f"📤 Отправляем... {i+1}/{len(clients)}")
            except Exception:
                pass

    await db.save_broadcast(f"[ФОТО] {caption}", sent)
    await status_msg.edit_text(
        f"✅ <b>Готово!</b>\n\n📨 Отправлено: <b>{sent}</b>\n❌ Ошибок: <b>{failed}</b>",
        parse_mode="HTML"
    )


@router.message(BroadcastState.waiting_message)
async def broadcast_text(message: Message, state: FSMContext, bot: Bot):
    text = message.text or ""
    if not text:
        await message.answer("❌ Отправьте текст или фото:")
        return
    clients = await db.get_all_clients()
    await state.clear()

    sent = 0
    failed = 0
    status_msg = await message.answer(f"📤 Отправляем... 0/{len(clients)}")
    for i, client in enumerate(clients):
        try:
            await bot.send_message(client[1], f"📢 <b>Сообщение от салона</b>\n\n{text}", parse_mode="HTML")
            sent += 1
        except Exception:
            failed += 1
        if (i + 1) % 10 == 0:
            try:
                await status_msg.edit_text(f"📤 Отправляем... {i+1}/{len(clients)}")
            except Exception:
                pass

    await db.save_broadcast(text, sent)
    await status_msg.edit_text(
        f"✅ <b>Готово!</b>\n\n📨 Отправлено: <b>{sent}</b>\n❌ Ошибок: <b>{failed}</b>",
        parse_mode="HTML"
    )