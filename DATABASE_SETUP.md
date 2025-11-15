# Model Picks Database Setup

## Overview

The model now stores ALL picks in Supabase at the time they're generated. This ensures:
- **Original odds/lines are preserved** (no live line contamination)
- **Picks are locked once games start** (prevents overwrites)
- **Historical tracking** of all predictions
- **Accurate best bets analysis** based on actual game-day data

## Database Schema

### Table: `model_picks`

Stores all model predictions with these key features:
- **Unique constraint**: One pick per game per bet type per day
- **Locking mechanism**: `is_locked` prevents updates after game starts
- **Best bets tracking**: `is_best_bet` and `best_bet_rank` fields
- **Results tracking**: `result`, `home_score`, `away_score` filled after completion

## Setup Instructions

### 1. Run the Schema

Connect to your Supabase project and run:

```bash
psql -h YOUR_SUPABASE_HOST -U postgres -d postgres -f model_picks_schema.sql
```

Or use the Supabase SQL Editor to run `model_picks_schema.sql`.

### 2. Verify Tables Created

Check that these were created:
- Table: `model_picks`
- Indexes: `idx_model_picks_*` (several)
- Views: `best_bets_performance`, `all_picks_performance`
- Function: `lock_started_games()`

### 3. Set Row Level Security (Optional)

If using RLS, add policies to allow your service key to read/write.

## How It Works

### 1. Running main.py

```bash
python3 main.py  # or python3 main.py -d 2025-11-15
```

When you run `main.py`:
1. ✅ Generates all picks for the day
2. 💾 Saves ALL picks to `model_picks` table
3. 🔒 Skips games that already started (locked)
4. 🏆 Marks top 5 as best bets (`is_best_bet=true`)

**Output:**
```
💾 Saving 90 picks to database...
   ✅ Saved: 85, Skipped (locked): 5, Errors: 0

💾 Marking 5 best bets...
   ✅ Marked 5 picks as best bets
```

### 2. Analyzing Results

```bash
# Analyze all picks
python3 analyze_db_picks.py -d 2025-11-15

# Analyze only best bets
python3 analyze_db_picks.py -d 2025-11-15 --best-bets

# Skip auto-updating results
python3 analyze_db_picks.py -d 2025-11-15 --no-update
```

The script will:
1. 🔒 Lock any games that have started
2. 📥 Fetch final scores from API
3. ✅ Calculate win/loss for each bet
4. 📊 Display performance summary

## Key Features

### Locking Mechanism

Once a game starts, picks are **locked** and cannot be overwritten:

```sql
-- Automatically locks picks when game_start_time <= NOW()
SELECT lock_started_games();
```

This prevents accidentally saving picks with live odds lines.

### Best Bets Tracking

The top 5 picks are marked with:
- `is_best_bet = true`
- `best_bet_rank = 1-5`

You can query just best bets:
```sql
SELECT * FROM model_picks 
WHERE date = '2025-11-15' 
  AND is_best_bet = true 
ORDER BY best_bet_rank;
```

### Deduplication

If you run `main.py` multiple times:
- **Before game starts**: Pick is updated with latest odds/confidence
- **After game starts**: Pick is skipped (locked)

This lets you update picks throughout the day without losing historical data.

### Performance Views

Pre-built views for quick analysis:

```sql
-- Best bets performance by date
SELECT * FROM best_bets_performance;

-- All picks performance by date and type
SELECT * FROM all_picks_performance;
```

## Workflow

### Daily Usage

1. **Morning**: Run `main.py` to generate initial picks
   ```bash
   python3 main.py
   ```

2. **Afternoon**: Re-run if you want updated odds/lines
   ```bash
   python3 main.py  # Updates unlocked picks only
   ```

3. **Evening**: Games start, picks get locked automatically

4. **Next Day**: Analyze results
   ```bash
   python3 analyze_db_picks.py -d 2025-11-15 --best-bets
   ```

### Multi-Day Analysis

Get cumulative performance:

```python
from model_picks_db import ModelPicksDB

picks_db = ModelPicksDB(supabase_url, supabase_key)
stats = picks_db.get_performance_summary('2025-11-10', '2025-11-15')

print(f"Win Rate: {stats['win_rate']:.1%}")
print(f"ROI: {stats['roi']:.1f}%")
print(f"Best Bets: {stats['best_bets']['win_rate']:.1%}")
```

## Advantages Over Old System

### ❌ Old System (JSON files)
- Only saved best bets (not all picks)
- Manual file management
- Odds could change between runs
- No lock mechanism
- Harder to query historical data

### ✅ New System (Supabase)
- Saves ALL picks automatically
- Database-backed with indexes
- Locks picks when games start
- Prevents live line contamination
- Easy historical queries
- Views for instant analysis

## Troubleshooting

### Picks not saving?

Check:
1. `SUPABASE_URL` and `SUPABASE_SERVICE_KEY` in `.env`
2. Database table exists: `SELECT * FROM model_picks LIMIT 1;`
3. Permissions: Service key can insert into `model_picks`

### Results not updating?

The script auto-fetches results. If it fails:
1. Check `API_KEY` is set in `.env`
2. Verify games are marked as 'final' in API
3. Run with `--no-update` and check manually

### Duplicate key error?

This means a pick already exists for that game/date/type.
- If game hasn't started: Pick will be updated
- If game has started: Pick will be skipped (this is expected)

## Migration from JSON System

If you have old JSON files in `best_bets_history/`:

1. They're preserved for reference
2. New picks go to database
3. Use `analyze_db_picks.py` going forward
4. Old `analyze_saved_best_bets.py` still works with JSON files

