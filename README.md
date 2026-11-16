# REDDY AUTOCARE — Customer Portal

A full-stack starter for a premium steam car-wash business.

## Features
- Customer registration using name, mobile number and password
- Returning-customer login using mobile number and password
- Argon2 password hashing; passwords are never stored in plaintext
- JWT bearer authentication
- Customer profile, saved vehicles and wash bookings
- Doorstep and shop appointment service modes
- PostgreSQL database (Supabase-compatible) and SQLite local fallback
- Configurable wash packages; sample prices are deliberately marked as placeholders

> Phone + password login does not prove that a person owns a phone number. Add SMS OTP verification before treating a phone number as verified. Do not use this demo as a production payment or identity system without a security review.

## 1. Requirements
- Python 3.11+
- Git
- Optional: Docker + Docker Compose for local PostgreSQL

## 2. Start the backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

The default `.env` uses SQLite, so you can run locally without creating a cloud database:

```bash
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

API documentation: http://127.0.0.1:8000/docs

### Use PostgreSQL locally (optional)

From the project root:

```bash
docker compose up -d db
```

Set `DATABASE_URL` in `backend/.env` to:

```text
postgresql+psycopg://reddy:reddy_local_only@localhost:5432/reddy_autocare
```

Restart the backend.

### Use Supabase PostgreSQL (free tier subject to current limits)

Create a Supabase project, copy its PostgreSQL connection string, and set it as `DATABASE_URL`. Use the connection string format:

```text
postgresql+psycopg://USER:PASSWORD@HOST:5432/postgres?sslmode=require
```

Use the direct connection string or the session pooler for a persistent Python backend. Keep credentials only in `.env` / hosting environment variables. Never commit `.env`.

## 3. Start the frontend

Open a second terminal from the project root:

```bash
cd frontend
python3 -m http.server 5500
```

Open http://127.0.0.1:5500

The frontend calls the API at `http://127.0.0.1:8000`. If you change the backend address, edit `API_BASE` at the top of `frontend/app.js`.

## 4. First-time setup
1. Register with your name, mobile number and password.
2. Log out.
3. Log in again with the same mobile number and password.
4. Add a vehicle.
5. Create a booking and choose either Doorstep or At our shop.

## 5. Configure real business packages
The starter seeds clearly-labelled sample packages. Update `DEFAULT_SERVICES` in `backend/app/main.py` with your actual service names, descriptions, prices and durations before publishing. Do not advertise placeholder prices.

## 6. Security notes
- Passwords are hashed using Argon2.
- API endpoints validate input and use parameterized SQLAlchemy queries.
- JWT is returned to the browser and kept in `sessionStorage` (cleared when the tab session ends). Protect against XSS and use HTTPS in deployment.
- Configure a long random `JWT_SECRET`; never use the example value in production.
- Set `CORS_ORIGINS` to the exact deployed frontend origin(s).
- Add SMS OTP verification, rate limiting, password reset, backups and monitoring before production launch.
- The API does not collect card details or process payments.

## 7. Azure / Terraform
The `infra/` folder contains a starter Terraform definition for an Azure Static Web App (frontend hosting). It does not yet provision a backend runtime or PostgreSQL database. Deploying the API and database is a separate step; do not assume the whole application is hosted just because the frontend is live.


## REDDY AUTOCARE branded homepage
The frontend now uses the supplied brand artwork and cropped showroom, uniform and mobile-van visuals in `frontend/assets/`. The public landing page includes service cards, doorstep/shop booking calls to action, and a registration/login modal connected to the FastAPI API.
