-- Model Picks Table
-- Stores all model predictions at the time they're generated
-- Locked once game starts to prevent overwriting with live odds

CREATE TABLE IF NOT EXISTS model_picks (
    id BIGSERIAL PRIMARY KEY,
    
    -- Game Information
    date DATE NOT NULL,
    game_id TEXT NOT NULL,
    home_team TEXT NOT NULL,
    away_team TEXT NOT NULL,
    game_start_time TIMESTAMPTZ,
    
    -- Pick Details
    bet_type TEXT NOT NULL, -- 'spread' or 'total'
    pick TEXT NOT NULL, -- e.g., "Duke -5.5" or "Over 145.0"
    odds INTEGER NOT NULL, -- American odds (e.g., -110)
    
    -- Model Metrics (at time of pick)
    predicted_value DECIMAL(10, 4) NOT NULL, -- predicted spread or total
    predicted_prob DECIMAL(5, 4) NOT NULL, -- 0-1, model's predicted win probability
    confidence DECIMAL(5, 4) NOT NULL, -- 0-1, model's confidence in prediction
    score DECIMAL(6, 4) NOT NULL, -- combined score used for ranking
    
    -- Additional Context
    home_projected DECIMAL(6, 2), -- projected home score
    away_projected DECIMAL(6, 2), -- projected away score
    reasoning TEXT, -- why this pick was made
    
    -- Results (filled in after game completes)
    home_score INTEGER,
    away_score INTEGER,
    result BOOLEAN, -- true if bet won, false if lost, null if pending
    
    -- Metadata
    is_locked BOOLEAN DEFAULT FALSE, -- true once game starts, prevents updates
    is_best_bet BOOLEAN DEFAULT FALSE, -- was this in top 5 best bets?
    best_bet_rank INTEGER, -- rank in best bets (1-5), null if not best bet
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    
    -- Constraints
    UNIQUE(date, game_id, bet_type), -- one pick per game per bet type per day
    CHECK (bet_type IN ('spread', 'total')),
    CHECK (predicted_prob >= 0 AND predicted_prob <= 1),
    CHECK (confidence >= 0 AND confidence <= 1)
);

-- Indexes for fast queries
CREATE INDEX IF NOT EXISTS idx_model_picks_date ON model_picks(date);
CREATE INDEX IF NOT EXISTS idx_model_picks_game_id ON model_picks(game_id);
CREATE INDEX IF NOT EXISTS idx_model_picks_date_game ON model_picks(date, game_id);
CREATE INDEX IF NOT EXISTS idx_model_picks_best_bets ON model_picks(date, is_best_bet) WHERE is_best_bet = true;
CREATE INDEX IF NOT EXISTS idx_model_picks_locked ON model_picks(is_locked);
CREATE INDEX IF NOT EXISTS idx_model_picks_pending_results ON model_picks(date, result) WHERE result IS NULL;

-- Function to automatically update updated_at timestamp
CREATE OR REPLACE FUNCTION update_model_picks_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger to call the function
DROP TRIGGER IF EXISTS model_picks_updated_at_trigger ON model_picks;
CREATE TRIGGER model_picks_updated_at_trigger
    BEFORE UPDATE ON model_picks
    FOR EACH ROW
    EXECUTE FUNCTION update_model_picks_updated_at();

-- Function to lock picks once game starts
CREATE OR REPLACE FUNCTION lock_started_games()
RETURNS INTEGER AS $$
DECLARE
    rows_updated INTEGER;
BEGIN
    UPDATE model_picks
    SET is_locked = true
    WHERE is_locked = false
        AND game_start_time IS NOT NULL
        AND game_start_time <= NOW();
    
    GET DIAGNOSTICS rows_updated = ROW_COUNT;
    RETURN rows_updated;
END;
$$ LANGUAGE plpgsql;

-- View for analyzing best bets performance
CREATE OR REPLACE VIEW best_bets_performance AS
SELECT 
    date,
    COUNT(*) as total_bets,
    COUNT(*) FILTER (WHERE result = true) as wins,
    COUNT(*) FILTER (WHERE result = false) as losses,
    ROUND(COUNT(*) FILTER (WHERE result = true)::DECIMAL / NULLIF(COUNT(*), 0), 4) as win_rate,
    ROUND(AVG(predicted_prob), 4) as avg_predicted_prob,
    ROUND(AVG(confidence), 4) as avg_confidence,
    ROUND(AVG(score), 4) as avg_score
FROM model_picks
WHERE is_best_bet = true
    AND result IS NOT NULL
GROUP BY date
ORDER BY date DESC;

-- View for analyzing all picks performance
CREATE OR REPLACE VIEW all_picks_performance AS
SELECT 
    date,
    bet_type,
    COUNT(*) as total_bets,
    COUNT(*) FILTER (WHERE result = true) as wins,
    COUNT(*) FILTER (WHERE result = false) as losses,
    ROUND(COUNT(*) FILTER (WHERE result = true)::DECIMAL / NULLIF(COUNT(*), 0), 4) as win_rate
FROM model_picks
WHERE result IS NOT NULL
GROUP BY date, bet_type
ORDER BY date DESC, bet_type;

COMMENT ON TABLE model_picks IS 'Stores all model predictions at time of generation. Locked once game starts to preserve original odds/lines.';
COMMENT ON COLUMN model_picks.is_locked IS 'Set to true once game starts. Prevents overwriting with live odds.';
COMMENT ON COLUMN model_picks.predicted_value IS 'For spread: predicted spread (positive = home favored). For total: predicted total points.';
COMMENT ON COLUMN model_picks.predicted_prob IS 'Model predicted probability that this bet will win (0-1).';
COMMENT ON COLUMN model_picks.confidence IS 'Model confidence in this prediction based on data quality (0-1).';
COMMENT ON COLUMN model_picks.score IS 'Combined score used for ranking best bets (0-1).';

