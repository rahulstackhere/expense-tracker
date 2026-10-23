from datetime import datetime
from decimal import Decimal
from typing import Annotated

from pydantic import AliasPath, BaseModel, ConfigDict, Field, field_serializer, field_validator


class CategoryCreate(BaseModel):
    name: Annotated[str, Field(min_length=1, max_length=100)]

    @field_validator("name")
    @classmethod
    def trim_and_validate_name(cls, value: str) -> str:
        name = value.strip()
        if not name:
            raise ValueError("Category name must not be blank.")
        return name


class CategoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str


class CategoryWithCount(CategoryResponse):
    total_expenses: int


class ExpenseCreate(BaseModel):
    title: Annotated[str, Field(min_length=1, max_length=200)]
    amount: Annotated[Decimal, Field(gt=0, max_digits=12, decimal_places=2, allow_inf_nan=False)]
    category_id: Annotated[int, Field(gt=0)]

    @field_validator("title")
    @classmethod
    def trim_and_validate_title(cls, value: str) -> str:
        title = value.strip()
        if not title:
            raise ValueError("Expense title must not be blank.")
        return title


class ExpenseCreated(BaseModel):
    id: int
    title: str
    amount: Decimal
    category_id: int
    created_at: datetime

    @field_serializer("amount", when_used="json")
    def serialize_amount(self, value: Decimal) -> float:
        return float(value)


class ExpenseWithCategory(BaseModel):
    id: int
    title: str
    amount: Decimal
    category: Annotated[str, Field(validation_alias=AliasPath("category", "name"))]
    created_at: datetime

    @field_serializer("amount", when_used="json")
    def serialize_amount(self, value: Decimal) -> float:
        return float(value)


class ExpenseSummary(BaseModel):
    total: float
    count: int
    average: float
