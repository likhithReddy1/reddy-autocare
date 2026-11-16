from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict

class RegisterIn(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    phone: str = Field(pattern=r"^\+?[1-9]\d{9,14}$")
    password: str = Field(min_length=10, max_length=128)

class LoginIn(BaseModel):
    phone: str = Field(pattern=r"^\+?[1-9]\d{9,14}$")
    password: str = Field(min_length=1, max_length=128)

class UserOut(BaseModel):
    id: int
    name: str
    phone: str
    model_config = ConfigDict(from_attributes=True)

class VehicleIn(BaseModel):
    vehicle_type: str = Field(min_length=2, max_length=30)
    make_model: str = Field(min_length=2, max_length=100)
    registration_number: str = Field(min_length=4, max_length=20)

class VehicleOut(VehicleIn):
    id: int
    model_config = ConfigDict(from_attributes=True)

class BookingIn(BaseModel):
    vehicle_id: int
    service_id: int
    service_mode: str
    location_text: str = Field(default="", max_length=300)
    scheduled_at: datetime
    notes: str = Field(default="", max_length=500)

class BookingOut(BaseModel):
    id: int
    vehicle_id: int
    service_id: int
    service_mode: str
    location_text: str
    scheduled_at: datetime
    status: str
    notes: str
    model_config = ConfigDict(from_attributes=True)
