"""Exact business values: no floats, implicit currency conversion or negative credit notes."""

from datetime import date
from decimal import Decimal, InvalidOperation, localcontext
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from veya.domain.models import DomainError


def decimal(value):
    if type(value) is not str or len(value) > 40:
        raise ValueError('Use a decimal string')
    try:
        number = Decimal(value)
    except InvalidOperation:
        raise ValueError('Invalid decimal') from None
    if (
        not number.is_finite()
        or not 0 <= number <= Decimal('1e18')
        or int(str(number.as_tuple().exponent)) < -6
    ):
        raise ValueError('Decimal is outside the supported nonnegative range')
    return number


class Value(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True, frozen=True)


class Money(Value):
    amount: str
    currency: str = Field(pattern=r'^[A-Z]{3}$')

    @field_validator('amount')
    @classmethod
    def amount_valid(cls, value):
        decimal(value)
        return value

    def add(self, other):
        if self.currency != other.currency:
            raise DomainError(
                'currency_mismatch', 'Currency conversion requires an explicit policy'
            )
        with localcontext() as context:
            context.prec = 60
            return Money(
                amount=format(decimal(self.amount) + decimal(other.amount), 'f'),
                currency=self.currency,
            )


class Line(Value):
    item: str = Field(min_length=1, max_length=100)
    quantity: str
    unit_price: Money
    tax: Money

    @field_validator('quantity')
    @classmethod
    def positive(cls, value):
        if decimal(value) <= 0:
            raise ValueError('Quantity must be positive')
        return value

    @model_validator(mode='after')
    def same_currency(self):
        if self.unit_price.currency != self.tax.currency:
            raise ValueError('Line currencies differ')
        return self

    def total(self):
        with localcontext() as context:
            context.prec = 60
            return Money(
                amount=format(
                    decimal(self.quantity) * decimal(self.unit_price.amount)
                    + decimal(self.tax.amount),
                    'f',
                ),
                currency=self.unit_price.currency,
            )


class Invoice(Value):
    vendor: str = Field(min_length=1, max_length=100)
    number: str = Field(min_length=1, max_length=100)
    issued: str
    lines: tuple[Line, ...] = Field(min_length=1, max_length=200)
    total: Money

    @field_validator('issued')
    @classmethod
    def day(cls, value):
        if date.fromisoformat(value).isoformat() != value:
            raise ValueError('Use ISO date')
        return value

    @model_validator(mode='after')
    def totals(self):
        if not self.vendor.strip() or not self.number.strip():
            raise ValueError('Business identity is required')
        value = Money(amount='0', currency=self.total.currency)
        for line in self.lines:
            value = value.add(line.total())
        if decimal(value.amount) != decimal(self.total.amount):
            raise ValueError('Invoice total does not match its lines and tax')
        return self


class Order(Value):
    vendor: str = Field(min_length=1, max_length=100)
    number: str = Field(min_length=1, max_length=100)
    lines: tuple[Line, ...] = Field(min_length=1, max_length=200)


class Receipt(Value):
    vendor: str = Field(min_length=1, max_length=100)
    order_number: str = Field(min_length=1, max_length=100)
    item: str = Field(min_length=1, max_length=100)
    quantity: str
    state: Literal['received', 'returned']

    @field_validator('quantity')
    @classmethod
    def quantity_valid(cls, value):
        if decimal(value) <= 0:
            raise ValueError('Receipt quantity must be positive; use returned state')
        return value
