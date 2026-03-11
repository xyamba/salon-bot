from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from datetime import datetime, timedelta
import database.db as db
from config import ADMIN_IDS, SALON_NAME, SALON_ADDRESS, SALON_PHONE, WORK_START_HOUR, WORK_END_HOUR

router = Router()

DAYS_RU = {
    "Monday": "Пн", "Tuesday": "Вт", "Wednesday": "Ср",
    "Thursday": "Чт", "Friday": "Пт", "Saturday": "Сб", "Sunday": "Вс"
}

MAIN_KB = ReplyKeyboardMarkup(keyboard=[
    [KeyboardButton(text="📅 Записаться")],
    [KeyboardButton(text="📋 Мои записи")],
    [KeyboardButton(text="ℹ️ О салоне")],
], resize_keyboard=True)


class BookingStates(StatesGroup):
    choosing_service = State()
    choosing_date = State()
    choosing_time = State()
    sharing_phone = State()
    confirming = State()


class RegStates(StatesGroup):
    waiting_name = State()
    waiting_phone = State()


# ─── /start ────────────────────────────────────────────────

@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    await db.add_client(
        telegram_id=message.from_user.id,
        username=message.from_user.username or "",
        first_name=message.from_user.first_name or "Клиент"
    )

    already_registered = await db.is_registered(message.from_user.id)

    if already_registered:
        client = await db.get_client(message.from_user.id)
        first = client[3] or ""
        last = client[4] or ""
        await message.answer(
            f"👋 С возвращением, <b>{first} {last}</b>!\n\nВыберите действие:",
            reply_markup=MAIN_KB,
            parse_mode="HTML"
        )
    else:
        await message.answer(
            f"👋 Добро пожаловать в <b>{SALON_NAME}</b>!\n\n"
            "Для начала давайте познакомимся.\n\n"
            "Введите ваше <b>Имя и Фамилию</b>:\n"
            "<i>(например: Иван Петров)</i>",
            parse_mode="HTML"
        )
        await state.set_state(RegStates.waiting_name)


# ─── РЕГИСТРАЦИЯ: ИМЯ ──────────────────────────────────────

@router.message(RegStates.waiting_name)
async def reg_get_name(message: Message, state: FSMContext):
    text = message.text.strip()
    parts = text.split()

    if len(parts) < 2:
        await message.answer(
            "❌ Пожалуйста, введите <b>Имя и Фамилию</b> через пробел.\n"
            "<i>Например: Иван Петров</i>",
            parse_mode="HTML"
        )
        return

    first_name = parts[0]
    last_name = " ".join(parts[1:])
    await state.update_data(first_name=first_name, last_name=last_name)

    kb = ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="📱 Отправить мой номер", request_contact=True)]
    ], resize_keyboard=True, one_time_keyboard=True)

    await message.answer(
        f"Отлично, <b>{first_name}</b>! 👍\n\n"
        "Теперь введите ваш <b>номер телефона</b> или нажмите кнопку ниже:",
        reply_markup=kb,
        parse_mode="HTML"
    )
    await state.set_state(RegStates.waiting_phone)


# ─── РЕГИСТРАЦИЯ: ТЕЛЕФОН ───────────────────────────────────

@router.message(RegStates.waiting_phone, F.contact)
async def reg_phone_contact(message: Message, state: FSMContext):
    phone = message.contact.phone_number
    await finish_registration(message, state, phone)


@router.message(RegStates.waiting_phone)
async def reg_phone_text(message: Message, state: FSMContext):
    phone = message.text.strip()
    if len(phone) < 7:
        await message.answer("❌ Введите корректный номер телефона:")
        return
    await finish_registration(message, state, phone)


async def finish_registration(message: Message, state: FSMContext, phone: str):
    data = await state.get_data()
    first_name = data["first_name"]
    last_name = data["last_name"]

    await db.update_client_name(message.from_user.id, first_name, last_name)
    await db.save_phone(message.from_user.id, phone)
    await state.clear()

    await message.answer(
        f"✅ <b>Регистрация завершена!</b>\n\n"
        f"👤 {first_name} {last_name}\n"
        f"📱 {phone}\n\n"
        f"Добро пожаловать! Теперь вы можете записаться на услугу.",
        reply_markup=MAIN_KB,
        parse_mode="HTML"
    )


# ─── О салоне ──────────────────────────────────────────────

@router.message(F.text == "ℹ️ О салоне")
async def about_salon(message: Message):
    await message.answer(
        f"🏪 <b>{SALON_NAME}</b>\n\n"
        f"📍 Адрес: {SALON_ADDRESS}\n"
        f"📞 Телефон: {SALON_PHONE}\n"
        f"🕐 Режим работы: {WORK_START_HOUR}:00 — {WORK_END_HOUR}:00\n\n"
        "Ждём вас! 💇",
        parse_mode="HTML"
    )


# ─── МОИ ЗАПИСИ ────────────────────────────────────────────

@router.message(F.text == "📋 Мои записи")
async def my_appointments(message: Message):
    appointments = await db.get_client_appointments(message.from_user.id)
    if not appointments:
        await message.answer("У вас пока нет активных записей.\n\nНажмите «📅 Записаться».")
        return

    text = "📋 <b>Ваши записи:</b>\n\n"
    for app in appointments:
        app_id, service, date, time, status = app
        icon = "✅" if status == "confirmed" else "⏳"
        text += f"{icon} <b>{service}</b>\n📅 {date} в {time}\n\n"

    await message.answer(text, parse_mode="HTML")


# ─── ШАГ 1: ВЫБОР УСЛУГИ ───────────────────────────────────

@router.message(F.text == "📅 Записаться")
async def start_booking(message: Message, state: FSMContext):
    # Проверяем регистрацию
    registered = await db.is_registered(message.from_user.id)
    if not registered:
        await message.answer(
            "📝 Для записи нужно сначала зарегистрироваться.\n\nВведите /start"
        )
        return

    await state.clear()
    services = await db.get_services()
    if not services:
        await message.answer("К сожалению, услуги временно недоступны. Позвоните нам: " + SALON_PHONE)
        return

    builder = InlineKeyboardBuilder()
    for svc in services:
        svc_id, name, duration, price, _ = svc
        builder.button(
            text=f"{name} — {price}₽ ({duration} мин)",
            callback_data=f"svc_{svc_id}"
        )
    builder.button(text="❌ Отмена", callback_data="cancel_booking")
    builder.adjust(1)

    await message.answer(
        "💇 <b>Выберите услугу:</b>",
        reply_markup=builder.as_markup(),
        parse_mode="HTML"
    )
    await state.set_state(BookingStates.choosing_service)


@router.callback_query(BookingStates.choosing_service, F.data.startswith("svc_"))
async def choose_service(callback: CallbackQuery, state: FSMContext):
    service_id = int(callback.data.split("_")[1])
    service = await db.get_service(service_id)
    await state.update_data(service_id=service_id, service_name=service[1], service_price=service[3])
    await callback.answer()
    await show_date_picker(callback.message, service[1], edit=True)
    await state.set_state(BookingStates.choosing_date)


async def show_date_picker(message: Message, service_name: str, edit: bool = False):
    builder = InlineKeyboardBuilder()
    today = datetime.now()
    for i in range(7):
        day = today + timedelta(days=i)
        day_name = DAYS_RU.get(day.strftime("%A"), "")
        if i == 0:
            label = f"Сегодня ({day_name})"
        elif i == 1:
            label = f"Завтра ({day_name})"
        else:
            label = f"{day.strftime('%d.%m')} ({day_name})"
        builder.button(text=label, callback_data=f"date_{day.strftime('%Y-%m-%d')}")
    builder.button(text="❌ Отмена", callback_data="cancel_booking")
    builder.adjust(2)

    text = f"✅ Услуга: <b>{service_name}</b>\n\n📅 <b>Выберите дату:</b>"
    if edit:
        await message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")
    else:
        await message.answer(text, reply_markup=builder.as_markup(), parse_mode="HTML")


# ─── ШАГ 2: ВЫБОР ВРЕМЕНИ ──────────────────────────────────

@router.callback_query(BookingStates.choosing_date, F.data.startswith("date_"))
async def choose_date(callback: CallbackQuery, state: FSMContext):
    date_str = callback.data[5:]
    await state.update_data(date=date_str)
    await callback.answer()

    booked = await db.get_booked_times(date_str)

    builder = InlineKeyboardBuilder()
    slots = []
    hour = WORK_START_HOUR
    while hour < WORK_END_HOUR:
        time_str = f"{hour:02d}:00"
        if time_str not in booked:
            slots.append(time_str)
            builder.button(text=f"🕐 {time_str}", callback_data=f"time_{time_str}")
        hour += 1

    if not slots:
        builder_empty = InlineKeyboardBuilder()
        builder_empty.button(text="⬅️ Другой день", callback_data="back_to_date")
        builder_empty.button(text="❌ Отмена", callback_data="cancel_booking")
        builder_empty.adjust(2)
        await callback.message.edit_text(
            "😔 На выбранную дату все слоты заняты.\nВыберите другой день:",
            reply_markup=builder_empty.as_markup()
        )
        return

    builder.button(text="⬅️ Назад", callback_data="back_to_date")
    builder.button(text="❌ Отмена", callback_data="cancel_booking")
    builder.adjust(3)

    date_display = datetime.strptime(date_str, "%Y-%m-%d").strftime("%d.%m.%Y")
    await callback.message.edit_text(
        f"📅 Дата: <b>{date_display}</b>\n\n🕐 <b>Выберите время:</b>",
        reply_markup=builder.as_markup(),
        parse_mode="HTML"
    )
    await state.set_state(BookingStates.choosing_time)


@router.callback_query(F.data == "back_to_date")
async def back_to_date(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    data = await state.get_data()
    await show_date_picker(callback.message, data.get("service_name", ""), edit=True)
    await state.set_state(BookingStates.choosing_date)


# ─── ШАГ 3: ПОДТВЕРЖДЕНИЕ ──────────────────────────────────

@router.callback_query(BookingStates.choosing_time, F.data.startswith("time_"))
async def choose_time(callback: CallbackQuery, state: FSMContext):
    time_str = callback.data[5:]
    await state.update_data(time=time_str)
    await callback.answer()

    # Телефон уже есть из регистрации
    client = await db.get_client(callback.from_user.id)
    await state.update_data(phone=client[5] or "не указан")
    await show_confirmation(callback.message, state, edit=True)
    await state.set_state(BookingStates.confirming)


async def show_confirmation(message: Message, state: FSMContext, edit: bool = False):
    data = await state.get_data()
    date_display = datetime.strptime(data["date"], "%Y-%m-%d").strftime("%d.%m.%Y")

    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Подтвердить", callback_data="confirm_booking")
    builder.button(text="❌ Отмена", callback_data="cancel_booking")
    builder.adjust(2)

    text = (
        f"📋 <b>Подтвердите запись:</b>\n\n"
        f"💇 Услуга: <b>{data['service_name']}</b>\n"
        f"📅 Дата: <b>{date_display}</b>\n"
        f"🕐 Время: <b>{data['time']}</b>\n"
        f"💰 Стоимость: <b>{data['service_price']}₽</b>\n"
        f"📱 Телефон: <b>{data.get('phone', 'не указан')}</b>"
    )

    if edit:
        await message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")
    else:
        await message.answer(text, reply_markup=builder.as_markup(), parse_mode="HTML")


@router.callback_query(BookingStates.confirming, F.data == "confirm_booking")
async def confirm_booking(callback: CallbackQuery, state: FSMContext, bot: Bot):
    data = await state.get_data()
    client = await db.get_client(callback.from_user.id)
    await callback.answer()

    appointment_id = await db.create_appointment(
        client_id=client[0],
        service_id=data["service_id"],
        date=data["date"],
        time=data["time"]
    )

    date_display = datetime.strptime(data["date"], "%Y-%m-%d").strftime("%d.%m.%Y")
    first = client[3] or ""
    last = client[4] or ""
    await state.clear()

    await callback.message.edit_text(
        f"✅ <b>Запись подтверждена!</b>\n\n"
        f"💇 {data['service_name']}\n"
        f"📅 {date_display} в {data['time']}\n\n"
        f"Ждём вас! 😊\n📞 {SALON_PHONE}",
        parse_mode="HTML"
    )
    await callback.message.answer("Главное меню:", reply_markup=MAIN_KB)

    admin_text = (
        f"🔔 <b>Новая запись #{appointment_id}!</b>\n\n"
        f"👤 {first} {last}\n"
        f"🆔 @{callback.from_user.username or 'нет'} (ID: {callback.from_user.id})\n"
        f"📱 {data.get('phone', 'нет')}\n"
        f"💇 {data['service_name']}\n"
        f"📅 {date_display} в {data['time']}\n"
        f"💰 {data['service_price']}₽"
    )
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(admin_id, admin_text, parse_mode="HTML")
        except Exception:
            pass


# ─── ОТМЕНА (универсальная) ─────────────────────────────────

@router.callback_query(F.data == "cancel_booking")
async def cancel_booking_cb(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.answer("Отменено")
    await callback.message.edit_text("❌ Запись отменена.")
    await callback.message.answer("Главное меню:", reply_markup=MAIN_KB)