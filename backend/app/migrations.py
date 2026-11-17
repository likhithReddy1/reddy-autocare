from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine


def add_booking_price_snapshots(engine: Engine) -> None:
    if "bookings" not in inspect(engine).get_table_names():
        return

    existing_columns = {
        column["name"] for column in inspect(engine).get_columns("bookings")
    }
    snapshot_columns = (
        "service_price_paise",
        "doorstep_charge_paise",
        "total_price_paise",
    )
    with engine.begin() as connection:
        for column in snapshot_columns:
            if column not in existing_columns:
                connection.execute(text(
                    f"ALTER TABLE bookings ADD COLUMN {column} INTEGER NOT NULL DEFAULT 0"
                ))
