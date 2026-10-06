# FreshCheck website + demo dashboard
- `public/` static site (index.html landing page, dashboard.html demo dashboard)
- `api/` + `backend/` FastAPI (same pattern as the Movie Library project), Neon Postgres
- Vercel env vars: `DATABASE_URI` (postgresql+psycopg://... Neon pooled string), `SECRET_KEY` (long random string), `ENV=production`
- Set `WEB3FORMS_KEY` in public/index.html (search for it). Contact email: search hello@freshcheck.tt
- Live readings: POST /api/readings with header X-API-Key (key shown in the dashboard); tables `demouser`, `dashstate`, `reading`
- Email alerts (optional): `RESEND_API_KEY` (+ `MAIL_FROM`), or `SMTP_HOST`, `SMTP_PORT` (587), `SMTP_USER`, `SMTP_PASSWORD`, `MAIL_FROM`
- Admin page /admin: set `ADMIN_EMAILS` (comma-separated emails of accounts allowed in)
- Real phone sensor: Sensor Logger (Android) > Data Streaming > HTTP Push. Push URL `https://YOUR-SITE/api/ingest/sensor-logger?sensor=My Phone`, Auth Header `Bearer <device key>` (shown in the Add sensor popup)
- Table `demouser` is created automatically on first request.
