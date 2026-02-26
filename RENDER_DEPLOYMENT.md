# AI News Aggregator - Deployment Guide for Render

## Prerequisites
- GitHub repository with this code pushed
- Render account (render.com)
- Environment variables ready

## Environment Variables to Set on Render

1. **Database Variables** (Auto-configured via render.yaml)
   - `POSTGRES_USER` - PostgreSQL username
   - `POSTGRES_PASSWORD` - PostgreSQL password  
   - `POSTGRES_DB` - Database name

2. **API Keys & Credentials** (Set manually in Render dashboard)
   - `GEMINI_API_KEY` - Google Gemini API key
   - `APP_PASSWORD` - Gmail app-specific password
   - `MY_EMAIL` - Your Gmail address
   - `GROQ_API_KEY` - Groq API key (if using Groq LLM)

## Deployment Steps

### 1. Push Code to GitHub
```bash
git add .
git commit -m "Add Render deployment files"
git push origin main
```

### 2. Create Render Service
- Go to render.com and sign in
- Click "New +" → "Blueprint"
- Connect your GitHub repository
- Select the repository containing this code
- Render will automatically detect `render.yaml`

### 3. Configure Environment Variables
- In the Render dashboard, go to your service
- Add the following environment variables:
  - `MY_EMAIL` - Your Gmail address
  - `APP_PASSWORD` - Gmail app-specific password
  - `GEMINI_API_KEY` - Your API key
  - `GROQ_API_KEY` - Your API key (if used)

### 4. Deploy
- Click "Deploy Blueprint"
- Render will create:
  - PostgreSQL database (ai-news-db)
  - Background worker service (ai-news-worker)

## How It Works

**Option A: Background Worker (Current Setup)**
- Your app runs as a one-time job via the worker service
- Use Render's Cron feature to schedule it:
  - Go to your worker service settings
  - Add a Cron trigger to run daily/hourly
  - Set schedule: `0 0 * * *` (daily at midnight) or your preferred time

## Monitoring

- View logs in Render dashboard under "Logs"
- Check database status in the resource sidebar
- Monitor worker executions for errors/successes

## Database Connection

The `render.yaml` automatically:
1. Creates PostgreSQL database
2. Sets environment variables for database connection
3. Creates tables during build phase via `start.sh`

## Troubleshooting

If tables don't create automatically:
```bash
# Run manually in Render Shell:
python -c "from app.database.create_tables import *"
```

If API calls fail:
- Verify API keys are set correctly in Render dashboard
- Check rate limits on external APIs
- Review logs for specific error messages

## Cost Notes
- Free tier PostgreSQL: 256MB storage
- Free tier Worker: 750 hours/month (runs ~31 times daily)
- Adjust scheduling if approaching limits
