import os
import re
from datetime import datetime, timezone
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from sqlalchemy import select
import jwt

from .database import Base, engine, get_db
from . import models, schemas
from .migrations import add_booking_price_snapshots
from .pricing import (
    DOORSTEP_CHARGE_PAISE,
    canonical_vehicle_category,
)
from .security import hash_password, verify_password, create_access_token, read_access_token

app = FastAPI(title="REDDY AUTOCARE API", version="1.0.0")

origins = [x.strip() for x in os.getenv(
    "CORS_ORIGINS", "http://127.0.0.1:5500,http://localhost:5500"
).split(",") if x.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

bearer = HTTPBearer(auto_error=False)

DEFAULT_SERVICES = [
    {"name": "Steam Exterior Wash", "description": "Steam-powered exterior wash.", "price_paise": 0, "duration_minutes": 45},
    {"name": "Interior Steam Cleaning", "description": "Steam cleaning for the vehicle interior.", "price_paise": 0, "duration_minutes": 60},
    {"name": "Complete Steam Wash", "description": "Combined interior and exterior steam wash.", "price_paise": 0, "duration_minutes": 90},
]

DEFAULT_VEHICLE_PRICES = {
    "Bike / Scooter": 14900,
    "Hatchback": 29900,
    "Sedan": 34900,
    "SUV / MUV": 44900,
    "Luxury / Large SUV": 59900,
}

@app.on_event("startup")
def startup():
    Base.metadata.create_all(bind=engine)
    add_booking_price_snapshots(engine)
    with next(get_db()) as db:
        for item in DEFAULT_SERVICES:
            exists = db.scalar(select(models.Service).where(models.Service.name == item["name"]))
            if not exists:
                db.add(models.Service(**item))
        for vehicle_type, price_paise in DEFAULT_VEHICLE_PRICES.items():
            exists = db.scalar(select(models.VehiclePrice).where(
                models.VehiclePrice.vehicle_type == vehicle_type
            ))
            if not exists:
                db.add(models.VehiclePrice(
                    vehicle_type=vehicle_type,
                    price_paise=price_paise,
                ))
        db.commit()

@app.get("/health")
def health():
    return {"status": "ok", "service": "REDDY AUTOCARE API"}

def current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer),
    db: Session = Depends(get_db),
):
    if not credentials:
        raise HTTPException(status_code=401, detail="Please log in.")
    try:
        user_id = read_access_token(credentials.credentials)
    except (jwt.InvalidTokenError, ValueError, KeyError):
        raise HTTPException(status_code=401, detail="Session is invalid or expired.")
    user = db.get(models.User, user_id)
    if not user:
        raise HTTPException(status_code=401, detail="Account not found.")
    return user

@app.post("/api/auth/register", status_code=201)
def register(payload: schemas.RegisterIn, db: Session = Depends(get_db)):
    phone = payload.phone.strip()
    if db.scalar(select(models.User).where(models.User.phone == phone)):
        raise HTTPException(status_code=409, detail="This mobile number is already registered. Please log in.")
    user = models.User(
        name=payload.name.strip(),
        phone=phone,
        password_hash=hash_password(payload.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return {"message": "Account created. You can now log in.", "user_id": user.id}

@app.post("/api/auth/login")
def login(payload: schemas.LoginIn, db: Session = Depends(get_db)):
    user = db.scalar(select(models.User).where(models.User.phone == payload.phone.strip()))
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Incorrect mobile number or password.")
    return {
        "access_token": create_access_token(user.id),
        "token_type": "bearer",
        "user": {"id": user.id, "name": user.name, "phone": user.phone},
    }

@app.get("/api/me", response_model=schemas.UserOut)
def me(user: models.User = Depends(current_user)):
    return user

@app.get("/api/services")
def services(db: Session = Depends(get_db)):
    rows = db.scalars(select(models.Service).where(models.Service.active == True).order_by(models.Service.id)).all()
    return [{
        "id": x.id, "name": x.name, "description": x.description,
        "price_paise": x.price_paise, "duration_minutes": x.duration_minutes
    } for x in rows]

@app.get("/api/pricing")
def pricing(db: Session = Depends(get_db)):
    rows = db.scalars(
        select(models.VehiclePrice).order_by(models.VehiclePrice.id)
    ).all()
    return {
        "currency": "INR",
        "doorstep_charge_paise": DOORSTEP_CHARGE_PAISE,
        "vehicle_prices": [
            {"vehicle_type": row.vehicle_type, "price_paise": row.price_paise}
            for row in rows
        ],
    }

@app.get("/api/vehicles", response_model=list[schemas.VehicleOut])
def list_vehicles(user: models.User = Depends(current_user), db: Session = Depends(get_db)):
    return db.scalars(select(models.Vehicle).where(models.Vehicle.user_id == user.id).order_by(models.Vehicle.id.desc())).all()

@app.post("/api/vehicles", response_model=schemas.VehicleOut, status_code=201)
def add_vehicle(payload: schemas.VehicleIn, user: models.User = Depends(current_user), db: Session = Depends(get_db)):
    vehicle = models.Vehicle(
        user_id=user.id,
        vehicle_type=payload.vehicle_type.strip(),
        make_model=payload.make_model.strip(),
        registration_number=payload.registration_number.strip().upper(),
    )
    db.add(vehicle)
    db.commit()
    db.refresh(vehicle)
    return vehicle

@app.patch("/api/vehicles/{vehicle_id}", response_model=schemas.VehicleOut)
def update_vehicle_category(
    vehicle_id: int,
    payload: schemas.VehicleCategoryUpdate,
    user: models.User = Depends(current_user),
    db: Session = Depends(get_db),
):
    vehicle = db.scalar(select(models.Vehicle).where(
        models.Vehicle.id == vehicle_id,
        models.Vehicle.user_id == user.id,
    ))
    if not vehicle:
        raise HTTPException(status_code=404, detail="Vehicle not found in your account.")
    vehicle.vehicle_type = payload.vehicle_type.strip()
    db.commit()
    db.refresh(vehicle)
    return vehicle

@app.get("/api/bookings", response_model=list[schemas.BookingOut])
def list_bookings(user: models.User = Depends(current_user), db: Session = Depends(get_db)):
    return db.scalars(select(models.Booking).where(models.Booking.user_id == user.id).order_by(models.Booking.scheduled_at.desc())).all()

@app.post("/api/bookings", response_model=schemas.BookingOut, status_code=201)
def create_booking(payload: schemas.BookingIn, user: models.User = Depends(current_user), db: Session = Depends(get_db)):
    if payload.service_mode not in ("doorstep", "shop"):
        raise HTTPException(status_code=422, detail="Choose doorstep or shop service.")
    vehicle = db.scalar(select(models.Vehicle).where(
        models.Vehicle.id == payload.vehicle_id,
        models.Vehicle.user_id == user.id
    ))
    service = db.get(models.Service, payload.service_id)
    if not vehicle:
        raise HTTPException(status_code=404, detail="Vehicle not found in your account.")
    if not service or not service.active:
        raise HTTPException(status_code=404, detail="Selected service is unavailable.")
    category = canonical_vehicle_category(vehicle.vehicle_type)
    if not category:
        raise HTTPException(
            status_code=422,
            detail="Update this vehicle to one of the listed pricing categories before booking.",
        )
    vehicle_price = db.scalar(select(models.VehiclePrice).where(
        models.VehiclePrice.vehicle_type == category
    ))
    if not vehicle_price:
        raise HTTPException(status_code=503, detail="Pricing is temporarily unavailable.")
    if payload.scheduled_at.replace(tzinfo=None) <= datetime.utcnow():
        raise HTTPException(status_code=422, detail="Choose a future appointment time.")
    if payload.service_mode == "doorstep" and not payload.location_text.strip():
        raise HTTPException(status_code=422, detail="Enter the doorstep service address.")
    doorstep_charge_paise = (
        DOORSTEP_CHARGE_PAISE if payload.service_mode == "doorstep" else 0
    )
    booking = models.Booking(
        user_id=user.id,
        vehicle_id=vehicle.id,
        service_id=service.id,
        service_mode=payload.service_mode,
        service_price_paise=vehicle_price.price_paise,
        doorstep_charge_paise=doorstep_charge_paise,
        total_price_paise=vehicle_price.price_paise + doorstep_charge_paise,
        location_text=payload.location_text.strip(),
        scheduled_at=payload.scheduled_at.replace(tzinfo=None),
        notes=payload.notes.strip(),
    )
    db.add(booking)
    db.commit()
    db.refresh(booking)
    return booking
