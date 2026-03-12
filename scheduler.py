from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from aiogram import Bot
from datetime import datetime, timedelta
import database.db as db
import logging

logger = logging.getLogger(__name__)
scheduler = AsyncIOScheduler(timezone="Europe/Moscow")


async def send_reminders(bot: Bot):
    """Напоминания клиентам за день до записи в 18:00"""
    tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    tomorrow_display = (datetime.now() + timedelta(days=1)).strftime("%d.%m.%Y")
    appointments = await db.get_today_appointments(tomorrow)

    for app in appointments:
        app_id, name, phone, tg_id, service, date, time, status = app
        try:
            await bot.send_message(
                tg_id,
                f"⏰ <b>Напоминание о записи!</b>\n\n"
                f"Завтра, {tomorrow_display} в <b>{time}</b>\n"
                f"💇 {service}\n\nЖдём вас! 😊",
                parse_mode="HTML"
            )
        except Exception as e:
            logger.warning(f"Не удалось отправить напоминание {tg_id}: {e}")


async def auto_cleanup(bot: Bot):
    """Автоудаление прошедших записей каждую ночь в 03:00"""
    count = await db.delete_old_appointments()
    logger.info(f"Автоочистка: удалено {count} прошедших записей")


def start_scheduler(bot: Bot):
    # Напоминания каждый день в 18:00
    scheduler.add_job(
        send_reminders,
        trigger=CronTrigger(hour=18, minute=0),
        kwargs={"bot": bot},
        id="daily_reminders",
        replace_existing=True
    )

    # Автоудаление каждую ночь в 03:00
    scheduler.add_job(
        auto_cleanup,
        trigger=CronTrigger(hour=3, minute=0),
        kwargs={"bot": bot},
        id="auto_cleanup",
        replace_existing=True
    )

    scheduler.start()
    logger.info("Планировщик запущен")