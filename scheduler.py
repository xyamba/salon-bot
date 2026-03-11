from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from aiogram import Bot
from datetime import datetime, timedelta
import database.db as db
import logging

logger = logging.getLogger(__name__)
scheduler = AsyncIOScheduler(timezone="Europe/Moscow")


async def send_reminders(bot: Bot):
    """Отправляет напоминания за день до записи"""
    tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    tomorrow_display = (datetime.now() + timedelta(days=1)).strftime("%d.%m.%Y")

    appointments = await db.get_today_appointments(tomorrow)
    logger.info(f"Отправка напоминаний для {len(appointments)} записей на {tomorrow_display}")

    for app in appointments:
        app_id, name, phone, tg_id, service, date, time, status = app
        try:
            await bot.send_message(
                tg_id,
                f"⏰ <b>Напоминание о записи!</b>\n\n"
                f"Завтра, {tomorrow_display} в <b>{time}</b>\n"
                f"💇 Услуга: <b>{service}</b>\n\n"
                f"Ждём вас! 😊",
                parse_mode="HTML"
            )
        except Exception as e:
            logger.warning(f"Не удалось отправить напоминание клиенту {tg_id}: {e}")


def start_scheduler(bot: Bot):
    """Запускает планировщик задач"""
    # Напоминания каждый день в 18:00
    scheduler.add_job(
        send_reminders,
        trigger=CronTrigger(hour=18, minute=0),
        kwargs={"bot": bot},
        id="daily_reminders",
        replace_existing=True
    )

    scheduler.start()
    logger.info("Планировщик задач запущен")
