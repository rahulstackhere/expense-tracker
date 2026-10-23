from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from database import (
    BACKEND_DIRECTORY,
    create_database_engine,
    initialize_database,
    resolve_database_url,
)
from main import create_app
from models import Base, Category, Expense


@pytest.fixture
def client():
    test_engine = create_database_engine("sqlite://")
    application = create_app(test_engine)
    with TestClient(application) as test_client:
        yield test_client
    test_engine.dispose()


def test_empty_database_returns_empty_lists_and_zero_summary(client: TestClient):
    assert client.get("/categories").json() == []
    assert client.get("/expenses").json() == []
    assert client.get("/summary").json() == {"total": 0.0, "count": 0, "average": 0.0}


def test_category_creation_duplicate_rejection_and_counts(client: TestClient):
    food = client.post("/categories", json={"name": "  Food  "})
    travel = client.post("/categories", json={"name": "Travel"})

    assert food.status_code == 201
    assert food.json()["name"] == "Food"
    assert travel.status_code == 201
    assert client.post("/categories", json={"name": "fOoD"}).status_code == 409

    categories = client.get("/categories").json()
    assert categories == [
        {"id": food.json()["id"], "name": "Food", "total_expenses": 0},
        {"id": travel.json()["id"], "name": "Travel", "total_expenses": 0},
    ]


def test_category_names_are_unique_using_unicode_casefold(client: TestClient):
    first = client.post("/categories", json={"name": "Straße"})
    duplicate = client.post("/categories", json={"name": "STRASSE"})

    assert first.status_code == 201
    assert duplicate.status_code == 409
    assert len(client.get("/categories").json()) == 1


def test_expenses_category_counts_and_summary(client: TestClient):
    food_id = client.post("/categories", json={"name": "Food"}).json()["id"]
    travel_id = client.post("/categories", json={"name": "Travel"}).json()["id"]

    lunch = client.post(
        "/expenses",
        json={"title": " Lunch ", "amount": 250.50, "category_id": food_id},
    )
    trip = client.post(
        "/expenses",
        json={"title": "Train", "amount": 40.00, "category_id": travel_id},
    )

    assert lunch.status_code == 201
    assert lunch.json()["title"] == "Lunch"
    assert lunch.json()["amount"] == 250.5
    assert lunch.json()["category_id"] == food_id
    assert lunch.json()["created_at"]
    assert trip.status_code == 201

    expenses = client.get("/expenses").json()
    assert len(expenses) == 2
    assert {expense["category"] for expense in expenses} == {"Food", "Travel"}
    assert all(expense["created_at"] for expense in expenses)

    assert [item["total_expenses"] for item in client.get("/categories").json()] == [1, 1]
    assert client.get("/summary").json() == {
        "total": 290.5,
        "count": 2,
        "average": 145.25,
    }


@pytest.mark.parametrize(
    "payload",
    [
        {"name": ""},
        {"name": "   "},
        {},
    ],
)
def test_invalid_category_payload_is_rejected(client: TestClient, payload: dict):
    assert client.post("/categories", json=payload).status_code == 422


@pytest.mark.parametrize("amount", [0, -1, "NaN", "Infinity", "0.001", "not-a-number"])
def test_invalid_amount_is_rejected(client: TestClient, amount):
    category_id = client.post("/categories", json={"name": "Food"}).json()["id"]
    response = client.post(
        "/expenses",
        json={"title": "Lunch", "amount": amount, "category_id": category_id},
    )
    assert response.status_code == 422
    assert client.get("/expenses").json() == []


def test_blank_title_and_unknown_category_are_rejected(client: TestClient):
    category_id = client.post("/categories", json={"name": "Food"}).json()["id"]

    blank_title = client.post(
        "/expenses",
        json={"title": "  ", "amount": 5, "category_id": category_id},
    )
    unknown_category = client.post(
        "/expenses",
        json={"title": "Lunch", "amount": 5, "category_id": 999},
    )

    assert blank_title.status_code == 422
    assert unknown_category.status_code == 404
    assert client.get("/expenses").json() == []


def test_database_enforces_amount_name_and_foreign_key_constraints():
    test_engine = create_database_engine("sqlite://")
    initialize_database(test_engine)
    with Session(test_engine) as db:
        category = Category(name="Food")
        db.add(category)
        db.commit()
        with pytest.raises(IntegrityError):
            db.execute(
                Expense.__table__.insert().values(
                    title="Invalid",
                    amount=Decimal("-1.00"),
                    category_id=category.id,
                )
            )
        db.rollback()

        with pytest.raises(IntegrityError):
            db.add(Category(name="food"))
            db.commit()
        db.rollback()

        with pytest.raises(IntegrityError):
            db.execute(
                Expense.__table__.insert().values(
                    title="Unknown category",
                    amount=Decimal("1.00"),
                    category_id=999,
                )
            )
        db.rollback()
    test_engine.dispose()


@pytest.mark.parametrize(
    ("table", "values"),
    [
        ("categories", {"name": "   "}),
        ("categories", {"name": "\u00a0 \u2003"}),
        ("categories", {"name": "x" * 101}),
        ("expenses", {"title": "   ", "amount": Decimal("1.00")}),
        ("expenses", {"title": "x" * 201, "amount": Decimal("1.00")}),
        ("expenses", {"title": "Valid", "amount": Decimal("1.001")}),
        ("expenses", {"title": "Valid", "amount": Decimal("10000000000.00")}),
    ],
)
def test_database_constraints_reject_invalid_text_and_amounts(table: str, values: dict):
    test_engine = create_database_engine("sqlite://")
    initialize_database(test_engine)
    with Session(test_engine) as db:
        category = Category(name="Valid category")
        db.add(category)
        db.commit()

        insert_values = dict(values)
        if table == "expenses":
            insert_values["category_id"] = category.id
        with pytest.raises(IntegrityError):
            db.execute(Base.metadata.tables[table].insert().values(**insert_values))
        db.rollback()
        assert db.query(Category).count() == 1
        assert db.query(Expense).count() == 0
    test_engine.dispose()


def test_relative_database_url_resolves_from_backend_directory():
    resolved = resolve_database_url("sqlite:///./expense_tracker.db")

    assert make_url(resolved).database == str(
        (BACKEND_DIRECTORY / "expense_tracker.db").resolve()
    )


def test_database_initialization_preserves_existing_records(tmp_path):
    database_path = tmp_path / "existing.sqlite"
    legacy_engine = create_database_engine(f"sqlite:///{database_path}")
    with legacy_engine.begin() as connection:
        connection.exec_driver_sql(
            "CREATE TABLE categories (id INTEGER PRIMARY KEY, name VARCHAR(100) NOT NULL)"
        )
        connection.exec_driver_sql(
            """
            CREATE TABLE expenses (
                id INTEGER PRIMARY KEY,
                title VARCHAR(200) NOT NULL,
                amount NUMERIC(12, 2) NOT NULL CHECK (amount > 0),
                category_id INTEGER NOT NULL REFERENCES categories(id),
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        connection.exec_driver_sql(
            "CREATE UNIQUE INDEX uq_categories_name_lower ON categories(lower(name))"
        )
        connection.exec_driver_sql("INSERT INTO categories (id, name) VALUES (1, 'Existing')")
        connection.exec_driver_sql(
            "INSERT INTO expenses (id, title, amount, category_id) "
            "VALUES (1, 'Saved', 14.25, 1)"
        )

    initialize_database(legacy_engine)
    with legacy_engine.connect() as connection:
        assert connection.exec_driver_sql(
            "SELECT name FROM categories WHERE id = 1"
        ).scalar_one() == "Existing"
        assert connection.exec_driver_sql(
            "SELECT title, amount, category_id FROM expenses WHERE id = 1"
        ).one() == ("Saved", 14.25, 1)
        index_names = {
            row[1] for row in connection.exec_driver_sql("PRAGMA index_list('categories')")
        }
        assert "uq_categories_name_casefold" in index_names
        assert connection.exec_driver_sql("SELECT count(*) FROM sqlite_master WHERE type='trigger'").scalar_one() == 4
    legacy_engine.dispose()


def test_database_read_errors_return_generic_server_errors():
    test_engine = create_database_engine("sqlite://")
    app = create_app(test_engine)
    with TestClient(app) as client:
        Expense.__table__.drop(test_engine)

        for path in ("/categories", "/expenses", "/summary"):
            response = client.get(path)
            assert response.status_code == 500
            assert "Traceback" not in response.text
    test_engine.dispose()


def test_category_query_database_errors_return_generic_server_error():
    test_engine = create_database_engine("sqlite://")
    app = create_app(test_engine)
    with TestClient(app) as client:
        Category.__table__.drop(test_engine)
        response = client.post("/categories", json={"name": "Food"})

        assert response.status_code == 500
        assert "Traceback" not in response.text
    test_engine.dispose()


def test_frontend_development_origin_is_allowed(client: TestClient):
    response = client.get(
        "/categories",
        headers={"Origin": "http://localhost:3000"},
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"
