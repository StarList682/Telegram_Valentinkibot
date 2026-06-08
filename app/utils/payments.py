import random
import logging
import payok
import aiohttp
from hashlib import blake2b

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, Optional

from aiogram import Bot
from aiogram.types import LabeledPrice, Message


STARS_CURRENCY = 'XTR'
STARS_PER_RUBLE = 2
PLATEGA_SUCCESS_STATUSES = {'CONFIRMED'}
PLATEGA_FAIL_STATUSES = {
    'CANCELED',
    'CANCELLED',
    'FAILED',
    'DECLINED',
    'EXPIRED',
    'CANCELED_BY_USER',
}
PLATEGA_BILL_ID_OFFSET = 1 << 62


@dataclass
class CheckResponse:
    is_paid: bool
    amount: int = 0


@dataclass
class BaseBill:
    id: str
    url: str = 'https://google.com'
    provider: str = 'external'


class BasePayment(object):
    async def check_payment(self, payment_id: str) -> CheckResponse:
        return CheckResponse(True, 1)

    async def create_payment(
        self,
        amount: int,
        *,
        description: str = 'Оплата в анонимном чате',
        payload: str = '',
    ) -> BaseBill:
        return BaseBill(id=str(self._get_id()))

    @staticmethod
    def _get_id() -> int:
        return random.getrandbits(32)


logger = logging.getLogger('payments')


@dataclass
class ParsedPaymentPayload:
    kind: str
    item_id: Optional[str] = None
    rub_amount: Optional[int] = None


def rub_to_stars(amount_rub: int) -> int:
    return amount_rub * STARS_PER_RUBLE


def make_vip_payload(item_id: str, rub_amount: Optional[int] = None) -> str:
    if rub_amount is None:
        return f'vip:{item_id}'
    return f'vip:{item_id}:{rub_amount}'


def make_balance_payload(amount_rub: int) -> str:
    return f'balance:{amount_rub}'


def parse_payment_payload(payload: str) -> Optional[ParsedPaymentPayload]:
    if payload.startswith('vip:'):
        parts = payload.split(':', 2)
        item_id = parts[1] if len(parts) > 1 else ''
        rub_amount = None
        if len(parts) == 3:
            if not parts[2].isdigit():
                return None
            rub_amount = int(parts[2])
            if rub_amount < 0:
                return None

        return ParsedPaymentPayload(
            kind='vip',
            item_id=item_id or None,
            rub_amount=rub_amount,
        )

    if payload.startswith('balance:'):
        raw_amount = payload.split(':', 1)[1]
        if not raw_amount.isdigit():
            return None

        amount_rub = int(raw_amount)
        if amount_rub < 1:
            return None

        return ParsedPaymentPayload(
            kind='balance',
            rub_amount=amount_rub,
        )

    return None


def charge_id_to_bill_id(charge_id: str) -> int:
    digest = blake2b(charge_id.encode('utf-8'), digest_size=8).digest()
    value = int.from_bytes(digest, 'big') & ((1 << 62) - 1)
    return -(value or 1)


def platega_transaction_to_bill_id(transaction_id: str) -> int:
    digest = blake2b(
        ('platega:%s' % transaction_id).encode('utf-8'),
        digest_size=8,
    ).digest()
    value = int.from_bytes(digest, 'big') & ((1 << 62) - 1)
    return PLATEGA_BILL_ID_OFFSET | value


def short_payment_error(
    exc: Exception,
    default: str = 'Ошибка платежного провайдера.',
    limit: int = 180,
) -> str:
    text = str(exc).strip() or default
    text = ' '.join(text.split())
    if len(text) <= limit:
        return text
    return text[:limit - 3].rstrip() + '...'


async def send_stars_invoice(
    bot: Bot,
    chat_id: int,
    title: str,
    description: str,
    payload: str,
    amount_stars: int,
    label: Optional[str] = None,
) -> Message:
    return await bot.send_invoice(
        chat_id=chat_id,
        title=title,
        description=description,
        payload=payload,
        provider_token='',
        currency=STARS_CURRENCY,
        prices=[
            LabeledPrice(
                label=label or title,
                amount=amount_stars,
            )
        ],
    )


class PlategaPay(BasePayment):
    def __init__(
        self,
        merchant_id: str,
        secret: str,
        return_url: str,
        failed_url: str,
        base_url: str = 'https://app.platega.io',
        currency: str = 'RUB',
        payment_method: int = 2,
    ) -> None:
        self.merchant_id = merchant_id.strip()
        self.secret = secret.strip()
        self.return_url = return_url.strip()
        self.failed_url = failed_url.strip()
        self.base_url = base_url.strip().rstrip('/')
        self.currency = currency.strip().upper()
        self.payment_method = payment_method

    def _ensure_configured(self) -> None:
        if not self.merchant_id or not self.secret:
            raise RuntimeError(
                'Platega не настроена: отсутствуют MerchantId/Secret.'
            )

        if not self.return_url or not self.failed_url:
            raise RuntimeError(
                'Platega не настроена: отсутствуют return/failed URL.'
            )

    def _headers(self) -> dict[str, str]:
        return {
            'X-MerchantId': self.merchant_id,
            'X-Secret': self.secret,
            'Content-Type': 'application/json',
        }

    async def _request(
        self,
        method: str,
        path: str,
        payload: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        self._ensure_configured()
        url = '%s%s' % (self.base_url, path)

        async with aiohttp.ClientSession(
            headers=self._headers(),
        ) as session:
            request = session.post if method == 'POST' else session.get
            kwargs = {'json': payload} if payload is not None else {}

            async with request(url, **kwargs) as response:
                status = response.status
                try:
                    result = await response.json(content_type=None)
                except Exception:
                    result = {'raw': await response.text()}

        if status >= 400:
            raise RuntimeError(
                'Platega HTTP error %s: %s' % (status, result)
            )

        if not isinstance(result, dict):
            raise RuntimeError(
                'Platega вернула неожиданный ответ: %s' % result
            )

        return result

    async def create_payment(
        self,
        amount: int,
        *,
        description: str = 'Оплата в анонимном чате',
        payload: str = '',
    ) -> BaseBill:
        result = await self._request(
            'POST',
            '/v2/transaction/process',
            {
                'paymentDetails': {
                    'amount': amount,
                    'currency': self.currency,
                },
                'description': description,
                'return': self.return_url,
                'failedUrl': self.failed_url,
                'payload': payload,
            },
        )

        transaction_id = (
            result.get('transactionId')
            or result.get('transaction_id')
            or result.get('id')
        )
        pay_url = (
            result.get('url')
            or result.get('redirect')
            or result.get('payUrl')
            or result.get('pay_url')
        )

        if not transaction_id or not pay_url:
            raise RuntimeError(
                'Platega вернула неполные данные для оплаты: %s' % result
            )

        return BaseBill(
            id=str(transaction_id),
            url=str(pay_url),
            provider='platega',
        )

    async def check_payment(self, payment_id: str) -> CheckResponse:
        result = await self._request(
            'GET',
            '/transaction/%s' % payment_id,
        )

        status = str(result.get('status', '')).upper()
        if status not in PLATEGA_SUCCESS_STATUSES:
            if status in PLATEGA_FAIL_STATUSES:
                logger.info('Platega invoice %s failed with %s', payment_id, status)
            return CheckResponse(False)

        payment_details = result.get('paymentDetails') or {}
        try:
            amount = int(Decimal(str(payment_details.get('amount', '0'))))
        except (InvalidOperation, TypeError, ValueError):
            amount = 0

        return CheckResponse(True, amount)


class CryptoPay(BasePayment):
    API_URL = 'https://pay.crypt.bot/api'

    def __init__(
        self,
        token: str,
        fiat: str = 'RUB',
        accepted_assets: str = 'USDT,TON,BTC,ETH,LTC,BNB,TRX,USDC',
        expires_in: int = 3600,
    ) -> None:
        self.token = token
        self.fiat = fiat
        self.accepted_assets = accepted_assets
        self.expires_in = expires_in

    async def _request(
        self,
        method: str,
        data: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        async with aiohttp.ClientSession(
            headers={'Crypto-Pay-API-Token': self.token},
        ) as session:
            async with session.post(
                f'{self.API_URL}/{method}',
                data=data or {},
            ) as response:
                payload = await response.json(content_type=None)

        if response.status >= 400:
            raise RuntimeError(
                'Crypto Pay HTTP error %s: %s' % (
                    response.status,
                    payload,
                )
            )

        if not payload.get('ok'):
            raise RuntimeError(
                'Crypto Pay API error: %s' % payload.get('error', 'unknown')
            )

        return payload['result']

    async def create_payment(
        self,
        amount: int,
        *,
        description: str = 'Оплата в анонимном чате',
        payload: str = '',
    ) -> BaseBill:
        data = {
            'currency_type': 'fiat',
            'fiat': self.fiat,
            'accepted_assets': self.accepted_assets,
            'amount': str(amount),
            'description': description,
            'expires_in': str(self.expires_in),
            'allow_comments': 'false',
            'allow_anonymous': 'false',
        }
        if payload:
            data['payload'] = payload

        result = await self._request(
            'createInvoice',
            data,
        )
        return BaseBill(
            id=str(result['invoice_id']),
            url=result['bot_invoice_url'],
            provider='crypto',
        )

    async def check_payment(self, payment_id: str) -> CheckResponse:
        try:
            result = await self._request(
                'getInvoices',
                {'invoice_ids': str(payment_id)},
            )
        except Exception as exc:
            logger.error('Crypto Pay check failed: %s', exc)
            return CheckResponse(False)

        items = result.get('items', [])
        if not items:
            return CheckResponse(False)

        invoice = items[0]
        if invoice.get('status') != 'paid':
            return CheckResponse(False)

        try:
            amount = int(Decimal(str(invoice.get('amount', '0'))))
        except (InvalidOperation, ValueError):
            amount = 0

        return CheckResponse(True, amount)


class PayOK(BasePayment):
    def __init__(
        self, api_id: int, api_key: str, project_id: int, project_secret: str,
    ) -> None:
        self.api = payok.PayOK(api_id, api_key, project_id, project_secret)

    async def create_payment(
        self,
        amount: int,
        *,
        description: str = 'Оплата в анонимном чате',
        payload: str = '',
    ) -> BaseBill:
        pay_id = self._get_id()
        url = await self.api.create_bill(
            pay_id=pay_id,
            amount=amount,
        )
        return BaseBill(
            id=str(pay_id),
            url=url,
        )

    async def check_payment(self, payment_id: str) -> CheckResponse:
        try:
            bills = await self.api.get_transactions(payment_id=int(payment_id))
        except payok.PayOKError as exc:
            logger.error('PayOk: [%s] %s' % (exc.message, exc.code))
            return CheckResponse(False)

        if not bills:
            return CheckResponse(False)

        bill: payok.Transaction = bills[0]
        return CheckResponse(
            bill.is_paid,
            bill.amount_profit,
        )
