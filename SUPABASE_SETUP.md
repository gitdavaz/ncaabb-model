# Supabase Setup Instructions

## Step 1: Create Supabase Project

1. Go to https://supabase.com/dashboard
2. Click **"New Project"**
3. Fill in:
   - **Name**: `ncaab-picks` (or your preference)
   - **Database Password**: Create a strong password (save it!)
   - **Region**: Choose closest to you
   - **Pricing Plan**: Free tier
4. Click **"Create new project"** (takes ~2 minutes)

## Step 2: Get Credentials

Once the project is created:

1. Go to **Project Settings** (gear icon in sidebar)
2. Go to **API** section
3. Copy these two values:
   - **Project URL**: `https://xxxxx.supabase.co`
   - **service_role** key (the secret one - NOT the anon key)

## Step 3: Add to .env File

Add these lines to your `.env` file:

```bash
# Supabase Configuration
SUPABASE_URL=https://xxxxx.supabase.co
SUPABASE_SERVICE_KEY=your_service_role_key_here
USE_CACHE=true
```

## Step 4: Create Database Tables

1. In Supabase dashboard, go to **SQL Editor** (in sidebar)
2. Click **"New Query"**
3. Copy the entire contents of `supabase_schema.sql`
4. Paste into the SQL editor
5. Click **"Run"** or press Cmd/Ctrl+Enter

You should see: "Success. No rows returned"

## Step 5: Verify Tables Created

1. Go to **Table Editor** (in sidebar)
2. You should see these tables:
   - `teams`
   - `team_stats`
   - `games`
   - `odds`
   - `cache_metadata`

## Step 6: Test the Connection

Run this command to test:

```bash
python3 -c "from database import SupabaseCache; import os; from dotenv import load_dotenv; load_dotenv(); cache = SupabaseCache(os.getenv('SUPABASE_URL'), os.getenv('SUPABASE_SERVICE_KEY')); print('✅ Connection successful!')"
```

## Expected Results

Once set up, you should see:
- **First run**: ~200 API calls (fetching fresh data)
- **Subsequent runs**: ~10-70 calls (using cached data)
- **API call reduction**: 70-95%

## Cache Refresh Schedule

- **Team Stats**: Refreshed every 12 hours
- **Recent Games**: Refreshed every 6 hours
- **Game Schedule**: Refreshed every 24 hours
- **Teams Info**: Cached permanently (rarely changes)

## Troubleshooting

### "Connection refused" error
- Check that SUPABASE_URL is correct (should include https://)
- Check that SUPABASE_SERVICE_KEY is the service_role key (not anon key)

### "Table does not exist" error
- Make sure you ran the SQL schema (Step 4)
- Check SQL Editor for any error messages

### "Permission denied" error
- Make sure you're using the service_role key (has full access)
- The anon key won't work for writes

## Future: Making Data Public

To enable public read access (for your public API):

1. In SQL Editor, run:
```sql
ALTER TABLE teams ENABLE ROW LEVEL SECURITY;
ALTER TABLE team_stats ENABLE ROW LEVEL SECURITY;
ALTER TABLE games ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Public read access" ON teams FOR SELECT USING (true);
CREATE POLICY "Public read access" ON team_stats FOR SELECT USING (true);
CREATE POLICY "Public read access" ON games FOR SELECT USING (true);
```

2. Then you can share the anon key for read-only public access

