import unittest
from datetime import datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app import models, schemas
from app.database import Base
from app.main import (
    DEFAULT_VEHICLE_PRICES,
    create_booking,
    pricing,
    update_vehicle_category,
)
from app.migrations import add_booking_price_snapshots
from app.pricing import DOORSTEP_CHARGE_PAISE


class BookingPricingTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        self.user = models.User(
            name="Test Customer",
            phone="+919876543210",
            password_hash="not-used",
        )
        self.service = models.Service(
            name="Steam Wash",
            description="Test wash",
            price_paise=0,
            duration_minutes=45,
            active=True,
        )
        self.db.add_all([self.user, self.service])
        self.db.flush()
        self.db.add_all([
            models.VehiclePrice(vehicle_type=vehicle_type, price_paise=price)
            for vehicle_type, price in DEFAULT_VEHICLE_PRICES.items()
        ])
        self.db.commit()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def test_all_categories_and_booking_modes_calculate_server_side(self):
        for vehicle_type, price_paise in DEFAULT_VEHICLE_PRICES.items():
            for service_mode in ("shop", "doorstep"):
                with self.subTest(vehicle_type=vehicle_type, service_mode=service_mode):
                    vehicle = models.Vehicle(
                        user_id=self.user.id,
                        vehicle_type=vehicle_type,
                        make_model="Test model",
                        registration_number=f"TEST{len(self.db.new)}",
                    )
                    self.db.add(vehicle)
                    self.db.flush()
                    payload = schemas.BookingIn(
                        vehicle_id=vehicle.id,
                        service_id=self.service.id,
                        service_mode=service_mode,
                        location_text="Test address" if service_mode == "doorstep" else "",
                        scheduled_at=datetime.utcnow() + timedelta(days=1),
                        service_price_paise=1,
                        total_price_paise=1,
                    )

                    booking = create_booking(payload, self.user, self.db)

                    doorstep_charge = (
                        DOORSTEP_CHARGE_PAISE if service_mode == "doorstep" else 0
                    )
                    self.assertEqual(booking.service_price_paise, price_paise)
                    self.assertEqual(booking.doorstep_charge_paise, doorstep_charge)
                    self.assertEqual(
                        booking.total_price_paise,
                        price_paise + doorstep_charge,
                    )

                    current_price = self.db.scalar(select(models.VehiclePrice).where(
                        models.VehiclePrice.vehicle_type == vehicle_type
                    ))
                    current_price.price_paise += 10000
                    self.db.commit()
                    self.db.refresh(booking)
                    self.assertEqual(booking.service_price_paise, price_paise)
                    self.assertEqual(
                        booking.total_price_paise,
                        price_paise + doorstep_charge,
                    )
                    current_price.price_paise = price_paise
                    self.db.commit()

    def test_legacy_vehicle_category_requires_customer_correction(self):
        vehicle = models.Vehicle(
            user_id=self.user.id,
            vehicle_type="Car",
            make_model="Legacy car",
            registration_number="OLD123",
        )
        self.db.add(vehicle)
        self.db.commit()

        with self.assertRaises(HTTPException) as context:
            create_booking(
                schemas.BookingIn(
                    vehicle_id=vehicle.id,
                    service_id=self.service.id,
                    service_mode="shop",
                    scheduled_at=datetime.utcnow() + timedelta(days=1),
                ),
                self.user,
                self.db,
            )

        self.assertEqual(context.exception.status_code, 422)
        self.assertIn("pricing categories", context.exception.detail)

        updated_vehicle = update_vehicle_category(
            vehicle.id,
            schemas.VehicleCategoryUpdate(vehicle_type="Sedan"),
            self.user,
            self.db,
        )
        self.assertEqual(updated_vehicle.vehicle_type, "Sedan")
        booking = create_booking(
            schemas.BookingIn(
                vehicle_id=vehicle.id,
                service_id=self.service.id,
                service_mode="shop",
                scheduled_at=datetime.utcnow() + timedelta(days=1),
            ),
            self.user,
            self.db,
        )
        self.assertEqual(booking.total_price_paise, DEFAULT_VEHICLE_PRICES["Sedan"])

    def test_public_pricing_includes_all_categories_and_doorstep_charge(self):
        response = pricing(self.db)
        published_prices = {
            item["vehicle_type"]: item["price_paise"]
            for item in response["vehicle_prices"]
        }

        self.assertEqual(published_prices, DEFAULT_VEHICLE_PRICES)
        self.assertEqual(
            response["doorstep_charge_paise"],
            DOORSTEP_CHARGE_PAISE,
        )


class BookingPriceMigrationTests(unittest.TestCase):
    def test_adds_snapshot_columns_without_removing_existing_rows(self):
        engine = create_engine("sqlite://")
        with engine.begin() as connection:
            connection.exec_driver_sql(
                "CREATE TABLE bookings (id INTEGER PRIMARY KEY, status VARCHAR(20))"
            )
            connection.exec_driver_sql(
                "INSERT INTO bookings (id, status) VALUES (7, 'pending')"
            )

        add_booking_price_snapshots(engine)

        with engine.connect() as connection:
            row = connection.exec_driver_sql(
                "SELECT id, status, service_price_paise, doorstep_charge_paise, "
                "total_price_paise FROM bookings WHERE id = 7"
            ).one()
        self.assertEqual(tuple(row), (7, "pending", 0, 0, 0))
        engine.dispose()


if __name__ == "__main__":
    unittest.main()
