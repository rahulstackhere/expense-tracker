import logging
import os
from contextlib import asynccontextmanager
from decimal import Decimal, ROUND_HALF_UP
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import Engine, func, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session, joinedload, sessionmaker

from database import SessionLocal, engine, get_db, initialize_database
from models import Category, Expense
from schemas import (
    CategoryCreate,
    CategoryResponse,
    CategoryWithCount,
    ExpenseCreate,
    ExpenseCreated,
    ExpenseSummary,
    ExpenseWithCategory,
)

logger = logging.getLogger(__name__)
CENT = Decimal("0.01")


def _is_category_name_conflict(error: IntegrityError) -> bool:
    message = str(error.orig)
    return any(
        index_name in message
        for index_name in ("uq_categories_name_casefold", "uq_categories_name_lower")
    )


def create_app(database_engine: Engine = engine) -> FastAPI:
    session_factory = (
        SessionLocal
        if database_engine is engine
        else sessionmaker(bind=database_engine, autoflush=False, expire_on_commit=False)
    )

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        initialize_database(database_engine)
        yield

    application = FastAPI(
        title="Expense Tracker API",
        description="Create categories and expenses, and retrieve spending activity and summaries.",
        version="1.0.0",
        lifespan=lifespan,
    )

    if database_engine is engine:
        db_dependency = get_db
    else:

        def db_dependency():
            with session_factory() as db:
                yield db

    application.add_middleware(
        CORSMiddleware,
        allow_origins=[
            origin.strip()
            for origin in os.getenv(
                "CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000"
            ).split(",")
            if origin.strip()
        ],
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )

    DbSession = Annotated[Session, Depends(db_dependency)]

    @application.post(
        "/categories",
        response_model=CategoryResponse,
        status_code=status.HTTP_201_CREATED,
        summary="Create a category",
        responses={409: {"description": "A category with this name already exists."}},
    )
    def create_category(payload: CategoryCreate, db: DbSession) -> Category:
        try:
            duplicate = db.scalar(
                select(Category.id).where(func.lower(Category.name) == payload.name.lower())
            )
            if duplicate is not None:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="A category with this name already exists.",
                )

            category = Category(name=payload.name)
            db.add(category)
            db.commit()
            db.refresh(category)
        except IntegrityError as error:
            db.rollback()
            if _is_category_name_conflict(error):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="A category with this name already exists.",
                ) from error
            logger.exception("Database integrity error while creating a category")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="The category could not be created because of a database integrity error.",
            ) from error
        except SQLAlchemyError as error:
            db.rollback()
            logger.exception("Database error while creating a category")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="The category could not be created.",
            ) from error
        return category

    @application.get(
        "/categories",
        response_model=list[CategoryWithCount],
        summary="List categories and expense counts",
    )
    def list_categories(db: DbSession) -> list[CategoryWithCount]:
        statement = (
            select(Category.id, Category.name, func.count(Expense.id).label("total_expenses"))
            .outerjoin(Expense, Expense.category_id == Category.id)
            .group_by(Category.id, Category.name)
            .order_by(Category.id)
        )
        try:
            rows = db.execute(statement).all()
            return [
                CategoryWithCount(id=row.id, name=row.name, total_expenses=row.total_expenses)
                for row in rows
            ]
        except SQLAlchemyError as error:
            db.rollback()
            logger.exception("Database error while listing categories")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Categories could not be retrieved.",
            ) from error

    @application.post(
        "/expenses",
        response_model=ExpenseCreated,
        status_code=status.HTTP_201_CREATED,
        summary="Create an expense",
        responses={404: {"description": "The selected category does not exist."}},
    )
    def create_expense(payload: ExpenseCreate, db: DbSession) -> Expense:
        try:
            category = db.get(Category, payload.category_id)
            if category is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="The selected category does not exist.",
                )

            expense = Expense(
                title=payload.title,
                amount=payload.amount.quantize(CENT, rounding=ROUND_HALF_UP),
                category_id=category.id,
            )
            db.add(expense)
            db.commit()
            db.refresh(expense)
        except IntegrityError as error:
            db.rollback()
            logger.exception("Database integrity error while creating an expense")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="The expense could not be created because of a database integrity error.",
            ) from error
        except SQLAlchemyError as error:
            db.rollback()
            logger.exception("Database error while creating an expense")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="The expense could not be created.",
            ) from error
        return expense

    @application.get(
        "/expenses",
        response_model=list[ExpenseWithCategory],
        summary="List expenses with category names",
    )
    def list_expenses(db: DbSession) -> list[Expense]:
        statement = (
            select(Expense)
            .options(joinedload(Expense.category))
            .order_by(Expense.created_at.desc(), Expense.id.desc())
        )
        try:
            return list(db.scalars(statement).all())
        except SQLAlchemyError as error:
            db.rollback()
            logger.exception("Database error while listing expenses")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Expenses could not be retrieved.",
            ) from error

    @application.get(
        "/summary",
        response_model=ExpenseSummary,
        summary="Get overall spending summary",
    )
    def get_summary(db: DbSession) -> ExpenseSummary:
        try:
            total, count = db.execute(
                select(
                    func.coalesce(func.sum(Expense.amount), 0),
                    func.count(Expense.id),
                )
            ).one()
            total_amount = Decimal(str(total)).quantize(CENT, rounding=ROUND_HALF_UP)
            average = (
                (total_amount / count).quantize(CENT, rounding=ROUND_HALF_UP)
                if count
                else Decimal("0.00")
            )
            return ExpenseSummary(total=float(total_amount), count=count, average=float(average))
        except SQLAlchemyError as error:
            db.rollback()
            logger.exception("Database error while calculating the expense summary")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="The expense summary could not be calculated.",
            ) from error

    return application


app = create_app()
