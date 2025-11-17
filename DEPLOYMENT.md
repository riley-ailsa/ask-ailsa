# Deploying Ask Ailsa

## Quick Deploy to Streamlit Cloud (Free)

### Prerequisites
1. Push your code to GitHub
2. Create a Streamlit Cloud account at https://streamlit.io/cloud

### Steps

1. **Prepare your repository:**
   ```bash
   # Make sure your code is in a GitHub repo
   git add .
   git commit -m "Prepare for deployment"
   git push origin main
   ```

2. **Add a .streamlit/config.toml file:**
   Create `.streamlit/config.toml` with:
   ```toml
   [server]
   headless = true
   port = 8501

   [theme]
   primaryColor = "#6366f1"
   backgroundColor = "#0f172a"
   secondaryBackgroundColor = "#1e293b"
   textColor = "#f1f5f9"
   ```

3. **Deploy on Streamlit Cloud:**
   - Go to https://share.streamlit.io/
   - Click "New app"
   - Select your GitHub repo
   - Set main file path: `ui/app.py`
   - Click "Deploy"

4. **Configure environment variables:**
   In Streamlit Cloud settings, add:
   - `OPENAI_API_KEY` = your OpenAI API key
   - Any other environment variables from your `.env`

**Important:** Streamlit Cloud only hosts the frontend. You need to deploy the backend API separately.

---

## Option 2: Deploy Backend + Frontend (Full Solution)

### Backend Options

#### A. Railway.app (Recommended for FastAPI)

1. **Install Railway CLI:**
   ```bash
   npm install -g @railway/cli
   ```

2. **Login and initialize:**
   ```bash
   railway login
   railway init
   ```

3. **Create Procfile:**
   ```
   web: uvicorn src.api.server:app --host 0.0.0.0 --port $PORT
   ```

4. **Deploy:**
   ```bash
   railway up
   ```

5. **Set environment variables:**
   ```bash
   railway variables set OPENAI_API_KEY=your_key_here
   ```

6. **Get your backend URL:**
   ```bash
   railway domain
   ```
   Example: `https://ask-ailsa-api.up.railway.app`

#### B. Render.com (Alternative)

1. Create `render.yaml`:
   ```yaml
   services:
     - type: web
       name: ask-ailsa-api
       env: python
       buildCommand: pip install -r requirements.txt
       startCommand: uvicorn src.api.server:app --host 0.0.0.0 --port $PORT
       envVars:
         - key: OPENAI_API_KEY
           sync: false
   ```

2. Connect GitHub repo at https://render.com

### Frontend Configuration

Update `ui/app.py` to use the deployed backend URL:

```python
# In ui/app.py, change:
BACKEND_URL = "http://localhost:8000"

# To:
import os
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")
```

Then set `BACKEND_URL` in Streamlit Cloud environment variables.

---

## Option 3: ngrok (Quick Testing - Temporary Links)

For quick testing without deployment:

1. **Install ngrok:**
   ```bash
   brew install ngrok  # macOS
   # or download from https://ngrok.com/download
   ```

2. **Start your backend:**
   ```bash
   ./start_api.sh
   ```

3. **In a new terminal, expose the API:**
   ```bash
   ngrok http 8000
   ```
   Copy the https URL (e.g., `https://abc123.ngrok.io`)

4. **Start Streamlit with ngrok backend:**
   ```bash
   # Update BACKEND_URL in ui/app.py temporarily
   # Then run:
   streamlit run ui/app.py
   ```

5. **In another terminal, expose Streamlit:**
   ```bash
   ngrok http 8501
   ```
   Share this URL for testing!

**Note:** ngrok free tier URLs expire after 8 hours.

---

## Option 4: Docker + Cloud Run (Production)

### Create Dockerfiles

**Backend Dockerfile:**
```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "src.api.server:app", "--host", "0.0.0.0", "--port", "8000"]
```

**Frontend Dockerfile:**
```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY ui/ ./ui/

EXPOSE 8501

CMD ["streamlit", "run", "ui/app.py", "--server.port=8501", "--server.address=0.0.0.0"]
```

### Deploy to Google Cloud Run

```bash
# Backend
gcloud run deploy ask-ailsa-api \
  --source . \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated

# Frontend
gcloud run deploy ask-ailsa-ui \
  --source ./ui \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --set-env-vars BACKEND_URL=https://ask-ailsa-api-xxx.run.app
```

---

## Recommended Approach for Testing

**For quick testing (< 1 day):**
- Use **ngrok** (Option 3)
- Start backend, expose with ngrok
- Start frontend, expose with ngrok
- Share the frontend ngrok URL

**For sharing with stakeholders (demo/testing):**
- Deploy backend to **Railway** (Option 2A)
- Deploy frontend to **Streamlit Cloud** (Option 1)
- Configure BACKEND_URL in Streamlit Cloud
- Share the Streamlit Cloud URL

**For production:**
- Use **Docker + Cloud Run** (Option 4)
- Add authentication if needed
- Set up custom domain
- Configure monitoring and logging

---

## Database Considerations

**Important:** Your current setup uses a local SQLite database (`grants.db`). For cloud deployment, you need to:

1. **Option A: Include database in deployment**
   - Add `grants.db` to your repo (if small < 100MB)
   - Read-only for testing purposes

2. **Option B: Use cloud database**
   - Migrate to PostgreSQL (Railway provides free PostgreSQL)
   - Update database connection in your code

3. **Option C: Mount persistent storage**
   - Use Cloud Storage (GCS) or S3
   - Mount as volume in Docker

For testing, Option A is simplest if your database is small.

---

## Security Checklist

Before deploying publicly:

- [ ] Never commit `.env` or API keys to Git
- [ ] Use environment variables for all secrets
- [ ] Add `.env` to `.gitignore`
- [ ] Consider adding rate limiting to API
- [ ] Add authentication if needed
- [ ] Review CORS settings in FastAPI
- [ ] Monitor API usage costs (OpenAI)

---

## Quick Start Commands

**Fastest way to get a shareable link (using ngrok):**

```bash
# Terminal 1: Start backend
./start_api.sh

# Terminal 2: Expose backend
ngrok http 8000
# Copy the https URL

# Terminal 3: Update ui/app.py BACKEND_URL to ngrok URL, then:
streamlit run ui/app.py

# Terminal 4: Expose frontend
ngrok http 8501
# Share this URL!
```

**Note:** The database must be accessible to the backend. If deploying to cloud, ensure `grants.db` is included or use a cloud database.
