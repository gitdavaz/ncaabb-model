-- NCAAB Predictions Database Schema
-- Run this in your Supabase SQL Editor to create the tables

-- ==================== TEAMS TABLE ====================
CREATE TABLE IF NOT EXISTS teams (
  id INT PRIMARY KEY,
  school VARCHAR(255) NOT NULL,
  mascot VARCHAR(255),
  abbreviation VARCHAR(10),
  conference VARCHAR(100),
  last_updated TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_teams_school ON teams(school);
CREATE INDEX IF NOT EXISTS idx_teams_conference ON teams(conference);

-- ==================== TEAM STATS TABLE ====================
CREATE TABLE IF NOT EXISTS team_stats (
  id BIGSERIAL PRIMARY KEY,
  team_id INT NOT NULL,
  season INT NOT NULL,
  last_updated TIMESTAMPTZ DEFAULT NOW(),
  
  -- Basic stats
  games INT DEFAULT 0,
  points_per_game DECIMAL(6,2) DEFAULT 0,
  opponent_points_per_game DECIMAL(6,2) DEFAULT 0,
  
  -- Advanced metrics (tempo-free)
  offensive_rating DECIMAL(6,2) DEFAULT 0,
  defensive_rating DECIMAL(6,2) DEFAULT 0,
  pace DECIMAL(6,2) DEFAULT 0,
  true_shooting_pct DECIMAL(6,4) DEFAULT 0,
  
  -- Four Factors (Offensive)
  effective_fg_pct DECIMAL(6,4) DEFAULT 0,
  turnover_ratio DECIMAL(6,4) DEFAULT 0,
  offensive_rebound_pct DECIMAL(6,4) DEFAULT 0,
  free_throw_rate DECIMAL(6,4) DEFAULT 0,
  
  -- Four Factors (Defensive - what opponents do)
  opp_effective_fg_pct DECIMAL(6,4) DEFAULT 0,
  opp_turnover_ratio DECIMAL(6,4) DEFAULT 0,
  opp_offensive_rebound_pct DECIMAL(6,4) DEFAULT 0,
  opp_free_throw_rate DECIMAL(6,4) DEFAULT 0,
  
  -- Full API response (for any additional fields)
  raw_data JSONB,
  
  UNIQUE(team_id, season)
);

CREATE INDEX IF NOT EXISTS idx_team_stats_lookup ON team_stats(team_id, season);
CREATE INDEX IF NOT EXISTS idx_team_stats_updated ON team_stats(last_updated);

-- ==================== GAMES TABLE ====================
CREATE TABLE IF NOT EXISTS games (
  id BIGINT PRIMARY KEY,
  season INT NOT NULL,
  start_date TIMESTAMPTZ,
  home_team_id INT,
  away_team_id INT,
  home_score INT,
  away_score INT,
  completed BOOLEAN DEFAULT FALSE,
  last_updated TIMESTAMPTZ DEFAULT NOW(),
  raw_data JSONB
);

CREATE INDEX IF NOT EXISTS idx_games_date ON games(start_date);
CREATE INDEX IF NOT EXISTS idx_games_teams ON games(home_team_id, away_team_id);
CREATE INDEX IF NOT EXISTS idx_games_season ON games(season);
CREATE INDEX IF NOT EXISTS idx_games_completed ON games(completed);
CREATE INDEX IF NOT EXISTS idx_games_team_lookup ON games(season, home_team_id, away_team_id, completed);

-- ==================== ODDS TABLE (Optional) ====================
CREATE TABLE IF NOT EXISTS odds (
  id BIGSERIAL PRIMARY KEY,
  game_id BIGINT,
  timestamp TIMESTAMPTZ DEFAULT NOW(),
  spread_home DECIMAL(5,1),
  spread_away DECIMAL(5,1),
  total_line DECIMAL(5,1),
  home_odds INT,
  away_odds INT,
  over_odds INT,
  under_odds INT,
  raw_data JSONB
);

CREATE INDEX IF NOT EXISTS idx_odds_game ON odds(game_id, timestamp DESC);

-- ==================== CACHE METADATA TABLE ====================
-- Track when different data types were last refreshed
CREATE TABLE IF NOT EXISTS cache_metadata (
  key VARCHAR(100) PRIMARY KEY,
  last_refresh TIMESTAMPTZ DEFAULT NOW(),
  notes TEXT
);

-- Insert initial metadata
INSERT INTO cache_metadata (key, notes) VALUES
  ('teams', 'Team information (school names, conferences)'),
  ('team_stats_2025', 'Team statistics for 2025 season'),
  ('games_schedule', 'Game schedules')
ON CONFLICT (key) DO NOTHING;

-- ==================== ENABLE ROW LEVEL SECURITY (for future public access) ====================
-- Uncomment these when ready to make data public

-- ALTER TABLE teams ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE team_stats ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE games ENABLE ROW LEVEL SECURITY;

-- Create policies for read-only public access
-- CREATE POLICY "Public teams read access" ON teams FOR SELECT USING (true);
-- CREATE POLICY "Public team_stats read access" ON team_stats FOR SELECT USING (true);
-- CREATE POLICY "Public games read access" ON games FOR SELECT USING (true);

-- ==================== HELPFUL VIEWS ====================

-- View for team stats with team names (all seasons)
-- Filter by season in your query: WHERE season = 2026
CREATE OR REPLACE VIEW current_season_team_stats AS
SELECT 
  ts.*,
  t.school,
  t.conference
FROM team_stats ts
JOIN teams t ON ts.team_id = t.id;

-- View for the most recent season's data
CREATE OR REPLACE VIEW latest_season_team_stats AS
SELECT 
  ts.*,
  t.school,
  t.conference
FROM team_stats ts
JOIN teams t ON ts.team_id = t.id
WHERE ts.season = (SELECT MAX(season) FROM team_stats);

-- View for recent games with team names
CREATE OR REPLACE VIEW recent_games_with_teams AS
SELECT 
  g.*,
  ht.school as home_team_name,
  at.school as away_team_name,
  ht.conference as home_conference,
  at.conference as away_conference
FROM games g
LEFT JOIN teams ht ON g.home_team_id = ht.id
LEFT JOIN teams at ON g.away_team_id = at.id
WHERE g.completed = true
ORDER BY g.start_date DESC;

-- ==================== UTILITY FUNCTIONS ====================

-- Function to clean up old cache entries
CREATE OR REPLACE FUNCTION cleanup_old_cache(days_to_keep INT DEFAULT 7)
RETURNS void AS $$
BEGIN
  -- Delete old team_stats
  DELETE FROM team_stats 
  WHERE last_updated < NOW() - (days_to_keep || ' days')::INTERVAL;
  
  -- Delete old uncompleted games
  DELETE FROM games 
  WHERE completed = false 
    AND last_updated < NOW() - (days_to_keep || ' days')::INTERVAL;
  
  -- Delete old odds
  DELETE FROM odds 
  WHERE timestamp < NOW() - (days_to_keep || ' days')::INTERVAL;
END;
$$ LANGUAGE plpgsql;

-- ==================== COMMENTS ====================
COMMENT ON TABLE teams IS 'NCAA basketball team information';
COMMENT ON TABLE team_stats IS 'Season statistics for teams including Four Factors';
COMMENT ON TABLE games IS 'Game schedule and results';
COMMENT ON TABLE odds IS 'Betting odds for games';
COMMENT ON TABLE cache_metadata IS 'Tracks when different data types were last refreshed';

