"""Internal bell writer shared by admin / client / public flows."""
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notification import Notification
from app.logging_config import get_logger

logger = get_logger(__name__)

# First message every new client sees in the bell: a short cabinet guide.
WELCOME_TEXT = (
    "Добро пожаловать в Beauty Specialist! 👋\n\n"
    "Коротко, что можно сделать в кабинете:\n"
    "• Заполнить профиль — имя, телефон, почта и адрес: «Мой профиль».\n"
    "• Выбрать мастера и услугу и записаться онлайн: «Записаться».\n"
    "• Следить за визитами и их статусами: «Мои записи».\n"
    "• Получать напоминания и ответы мастеров — в этот колокольчик.\n\n"
    "Спасибо, что вы с нами!"
)

MASTER_ACTIVATED_TEXT = (
    "Кабинет мастера активирован 🎉\n\n"
    "Ваш профиль опубликован — клиенты могут найти вас и записаться.\n\n"
    "Что сделать дальше:\n"
    "• Проверить услуги, цены и длительность.\n"
    "• Настроить расписание и часы приёма.\n"
    "• Добавить фото и сертификаты, если ещё не добавили.\n\n"
    "Оплата и бонусы:\n"
    "• 14 дней бесплатно, затем 250 ₽ × 2 месяца, далее 500 ₽/мес.\n"
    "• Предоплата за полгода — −10% и тариф «Профи», за год — −20% и тариф «Бизнес».\n"
    "• Скидка действует только на месяцы по 500 ₽.\n"
    "• Бонусы за клиентов и рефералов — в разделе «Тариф и оплата».\n\n"
    "Хороших записей!"
)


async def notify_user(
    db: AsyncSession,
    recipient_id: int,
    text: str,
    sender_id: Optional[int] = None,
    audience: str = "system",
    link: Optional[str] = None,
    *,
    kind: Optional[str] = None,
    appointment_id: Optional[int] = None,
) -> Notification:
    """Write one inbox row (flush only — caller commits)."""
    note = Notification(
        sender_id=sender_id,
        recipient_id=recipient_id,
        text=text.strip(),
        audience=audience,
        link=link,
        kind=kind,
        appointment_id=appointment_id,
        created_at=datetime.now(timezone.utc),
    )
    db.add(note)
    await db.flush()
    logger.info("Bell: to=%s audience=%s link=%s", recipient_id, audience, link)
    return note


async def send_welcome_bell(
    db: AsyncSession,
    recipient_id: int,
) -> Notification:
    """Welcome note for a freshly created account (1.80.0, owner item 5).

    Written once, right when the account is created (phone registration or
    social consent completion), and links to the cabinet («Мои записи»).
    """
    return await notify_user(
        db,
        recipient_id,
        WELCOME_TEXT,
        audience="system",
        link="appointments",
    )


async def send_master_activated_bell(
    db: AsyncSession,
    recipient_id: int,
) -> Notification:
    """Welcome-to-the-panel note written once, at self-activation.

    The draft may have lived for days, so this is the master's first message
    in the new cabinet: confirm publication and point to the next setup steps.
    """
    return await notify_user(
        db,
        recipient_id,
        MASTER_ACTIVATED_TEXT,
        audience="system",
        link="billing",
    )
