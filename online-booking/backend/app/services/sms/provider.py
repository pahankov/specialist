"""SMS provider abstraction."""
import logging
from abc import ABC, abstractmethod
from typing import Protocol

logger = logging.getLogger(__name__)


class SmsProvider(Protocol):
    """Protocol for SMS providers."""
    async def send(self, phone: str, code: str) -> bool:
        """Send SMS with code to phone. Returns True on success."""
        ...


class BaseSmsProvider(ABC):
    """Abstract base class for SMS providers."""

    @abstractmethod
    async def send(self, phone: str, code: str) -> bool:
        """Send SMS with code to phone. Returns True on success."""
        ...


class FakeSmsProvider(BaseSmsProvider):
    """Fake SMS provider for development/testing.

    Logs the OTP code to the console instead of sending real SMS.
    """

    async def send(self, phone: str, code: str) -> bool:
        logger.info("FAKE SMS - OTP generated for %s (code NOT logged)", phone)
        return True


class TwilioSmsProvider(BaseSmsProvider):
    """Twilio SMS provider for production."""

    def __init__(self, account_sid: str, auth_token: str, from_number: str):
        self.account_sid = account_sid
        self.auth_token = auth_token
        self.from_number = from_number

    async def send(self, phone: str, code: str) -> bool:
        from twilio.rest import Client
        client = Client(self.account_sid, self.auth_token)
        try:
            client.messages.create(
                body=f"Ваш код подтверждения: {code}. Не сообщайте его никому.",
                to=phone,
                from_=self.from_number,
            )
            logger.info("SMS sent via Twilio to %s", phone)
            return True
        except Exception as e:
            logger.error("Failed to send SMS via Twilio to %s: %s", phone, e, exc_info=True)
            return False


class SmscRuSmsProvider(BaseSmsProvider):
    """SMS.ru provider for production."""

    def __init__(self, login: str, password: str, sender: str = "BeautySpec"):
        self.login = login
        self.password = password
        self.sender = sender

    async def send(self, phone: str, code: str) -> bool:
        import aiohttp
        url = "https://sms.ru/sms/send"
        params = {
            "api_id": self.login,
            "to": phone,
            "text": f"Ваш код подтверждения: {code}. Не сообщайте его никому.",
            "fmt": "1",
        }
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, data=params, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    result = await resp.text()
                    success = result.startswith("100|")
                    if success:
                        logger.info("SMS sent via sms.ru to %s", phone)
                    else:
                        logger.warning("sms.ru returned non-success for %s: %s", phone, result)
                    return success
        except Exception as e:
            logger.error("Failed to send SMS via sms.ru to %s: %s", phone, e, exc_info=True)
            return False


def get_sms_provider() -> BaseSmsProvider:
    """Factory function to get the configured SMS provider."""
    from app.config import settings
    provider_name = getattr(settings, 'SMS_PROVIDER', 'fake').lower()

    if provider_name == 'twilio':
        logger.info("Using Twilio SMS provider")
        return TwilioSmsProvider(
            account_sid=settings.TWILIO_ACCOUNT_SID,
            auth_token=settings.TWILIO_AUTH_TOKEN,
            from_number=settings.TWILIO_FROM_NUMBER,
        )
    elif provider_name == 'smsc':
        logger.info("Using sms.ru provider")
        return SmscRuSmsProvider(
            login=settings.SMSC_LOGIN,
            password=settings.SMSC_PASSWORD,
        )
    else:
        logger.info("Using FAKE SMS provider (development mode)")
        return FakeSmsProvider()
