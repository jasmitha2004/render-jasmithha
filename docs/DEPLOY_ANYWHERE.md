# Deploying on other sites

## Static parts (no server): landing page and demo app
Upload the **contents** of `landing/` or `demo/` to any static host.
- **Netlify / Vercel / Cloudflare Pages:** drag the folder into the dashboard. No build command; publish directory is the folder itself.
- **GitHub Pages:** put the folder in a repo, then Settings → Pages → deploy from branch.
- **Render Static Site:** build command empty, publish directory `landing` (or `demo`).
For `landing/`, edit `landing/config.js` and set `appUrl` to your deployed app URL.

## Backend + Streamlit app (need a Python host)
Works on Render, Railway, Fly.io or any VPS.
1. Backend start command:
   `cd backend && python manage.py migrate --noinput && gunicorn contextbridge.wsgi:application --bind 0.0.0.0:$PORT`
   Build: `pip install -r requirements.txt && cd backend && python manage.py collectstatic --noinput`
   Env vars: `DJANGO_SECRET_KEY`, `DJANGO_DEBUG=False`, `DATABASE_URL`, `DJANGO_ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`, optional `ANTHROPIC_API_KEY`.
2. Streamlit start command:
   `streamlit run frontend/app.py --server.port $PORT --server.address 0.0.0.0`
   Env vars: `CONTEXTBRIDGE_API=https://<backend-host>/api`, `CONTEXTBRIDGE_SITE_URL=<landing url>`.
3. Add the Streamlit URL to the backend's `CSRF_TRUSTED_ORIGINS`.

Never commit `.env` or API keys.
