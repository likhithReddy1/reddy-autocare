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
from .security import hash_password, verify_password, create_access_token, read_access_token

app = FastAPI(title="REDDY AUTOCARE API", version="1.0.0")

origins = [x.strip() for x in os.getenv(
    "CORS_ORIGINS", "http://127.0.0.1:5500,http://localhost:5500"
).split(",") if x.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

bearer = HTTPBearer(auto_error=False)

# Replace these sample entries with your actual services and approved prices.
DEFAULT_SERVICES = [
    {"name": "Steam Exterior Wash", "description": "Steam-based exterior cleaning. Confirm final scope and price with the business.", "price_paise": 0, "duration_minutes": 45},
    {"name": "Interior Steam Cleaning", "description": "Interior steam-cleaning service. Confirm final scope and price with the business.", "price_paise": 0, "duration_minutes": 60},
    {"name": "Complete Steam Wash", "description": "Combined interior and exterior steam wash. Confirm final scope and price with the business.", "price_paise": 0, "duration_minutes": 90},
]

@app.on_event("startup")
def startup():
    Base.metadata.create_all(bind=engine)
    with next(get_db()) as db:
        for item in DEFAULT_SERVICES:
            exists = db.scalar(select(models.Service).where(models.Service.name == item["name"]))
            if not exists:
                db.add(models.Service(**item))
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
    if payload.scheduled_at.replace(tzinfo=None) <= datetime.utcnow():
        raise HTTPException(status_code=422, detail="Choose a future appointment time.")
    if payload.service_mode == "doorstep" and not payload.location_text.strip():
        raise HTTPException(status_code=422, detail="Enter the doorstep service address.")
    booking = models.Booking(
        user_id=user.id,
        vehicle_id=vehicle.id,
        service_id=service.id,
        service_mode=payload.service_mode,
        location_text=payload.location_text.strip(),
        scheduled_at=payload.scheduled_at.replace(tzinfo=None),
        notes=payload.notes.strip(),
    )
    db.add(booking)
    db.commit()
    db.refresh(booking)
    return booking
