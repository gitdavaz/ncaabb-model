"""
Configuration settings for the NCAAM Basketball Betting Model
"""

# API Settings
# Using the CBBD Python library: https://github.com/CFBD/cbbd-python
# Register for API key at: https://collegefootballdata.com/

# Model Settings
HOME_COURT_ADVANTAGE = 3.5  # Points advantage for home team
RECENT_GAMES_LIMIT = 10     # Number of recent games to analyze
D1_GAMES_ONLY = True        # Filter to only D1 conference games (excludes exhibitions vs non-D1)

# Best Bets Settings
MAX_ODDS = -125              # Maximum odds for best bets (e.g., -125 means -125 or better)
NUM_BEST_BETS = 5           # Number of best bets to display

# Prediction Weights (used in model calculations)
WEIGHTS = {
    'net_rating': 1.0,           # Weight for net rating differential
    'recent_form': 0.3,          # Weight for recent form adjustment
    'shooting_efficiency': 10.0, # Multiplier for shooting efficiency
    'defensive_rating': -0.5,    # Multiplier for defensive rating difference
}

# Confidence Thresholds
MIN_CONFIDENCE_FOR_BEST_BETS = 0.35  # Minimum confidence (0-1) to consider for best bets
# Note: Early season (Nov-Dec) typically 35-45% confidence due to limited data
#       Mid-season (Jan-Feb) typically 40-55% confidence with more data
#       35% filters out the bottom ~10% of predictions while keeping quality bets

# Display Settings
SHOW_DETAILED_ANALYSIS = True    # Show detailed reasoning for best bets
USE_COLORED_OUTPUT = False       # Use colored terminal output (requires termcolor)
TABLE_FORMAT = 'grid'            # Table format: 'grid', 'simple', 'fancy_grid', 'pipe'

# Advanced Settings
USE_CACHING = False              # Cache API responses (requires redis or file caching)
CACHE_EXPIRY_MINUTES = 30       # How long to cache API responses

# Risk Management
RECOMMENDED_UNIT_SIZE = 0.02    # Recommend betting 2% of bankroll per bet
MAX_BETS_PER_DAY = 5           # Maximum recommended bets per day

# Logging
LOG_LEVEL = 'INFO'              # Logging level: 'DEBUG', 'INFO', 'WARNING', 'ERROR'
LOG_TO_FILE = False             # Whether to log to file
LOG_FILE = 'betting_model.log' # Log file name

# Feature Flags
ENABLE_MONEYLINE_BETS = False   # Include moneyline bets in analysis
ENABLE_ALTERNATE_LINES = False  # Consider alternate spreads/totals
ENABLE_PLAYER_PROPS = False     # Include player prop bets
ENABLE_LIVE_BETTING = False     # Real-time updates for live games

# Stat Weights for Metrics Calculation
SHOOTING_WEIGHTS = {
    'field_goal': 0.5,
    'three_point': 0.3,
    'free_throw': 0.2
}

# Spread to Probability Conversion
SPREAD_POINT_VALUE = 0.035      # Each point of spread edge = ~3.5% win probability
TOTAL_POINT_VALUE = 0.025       # Each point of total edge = ~2.5% win probability

# Odds Filters for Different Bet Types
ODDS_FILTERS = {
    'conservative': -150,        # More conservative, higher favorites
    'balanced': -125,            # Default balanced approach
    'aggressive': -110,          # More aggressive, including underdogs
    'value': 100,               # Pure value plays, including all underdogs
}

# Minimum Sample Sizes
MIN_GAMES_FOR_PREDICTION = 5    # Minimum games played to make prediction
MIN_GAMES_FOR_CONFIDENCE = 10   # Minimum games for high confidence

# Alert Thresholds (for notification features)
HIGH_VALUE_BET_THRESHOLD = 0.85  # Alert when bet score exceeds this
LINE_MOVEMENT_THRESHOLD = 1.5    # Alert when line moves more than X points

# Backtesting Settings (for future feature)
BACKTEST_START_DATE = '2023-11-01'
BACKTEST_END_DATE = '2024-03-31'
BACKTEST_INITIAL_BANKROLL = 1000

# Team Ratings Adjustments (optional manual overrides)
TEAM_ADJUSTMENTS = {
    # Example: 'Duke': 2.0,  # Add 2 points to Duke's rating
}

# Conference Strength Multipliers (optional)
CONFERENCE_MULTIPLIERS = {
    'ACC': 1.0,
    'Big Ten': 1.0,
    'Big 12': 1.0,
    'SEC': 1.0,
    'Big East': 1.0,
    'Pac-12': 0.95,
    # Add more as needed
}

# Time-based Adjustments
TOURNAMENT_ADJUSTMENT = 1.2      # Multiply volatility during March Madness
RIVALRY_GAME_ADJUSTMENT = 0.8    # Reduce predictability for rivalry games
BACK_TO_BACK_PENALTY = -1.5     # Points penalty for back-to-back games


def get_odds_filter(strategy: str = 'balanced') -> int:
    """
    Get odds filter based on betting strategy
    
    Args:
        strategy: 'conservative', 'balanced', 'aggressive', or 'value'
        
    Returns:
        Maximum odds threshold
    """
    return ODDS_FILTERS.get(strategy, MAX_ODDS)


def get_config_summary() -> dict:
    """
    Get a summary of current configuration
    
    Returns:
        Dictionary of key configuration values
    """
    return {
        'home_court_advantage': HOME_COURT_ADVANTAGE,
        'recent_games_analyzed': RECENT_GAMES_LIMIT,
        'max_odds': MAX_ODDS,
        'num_best_bets': NUM_BEST_BETS,
        'recommended_unit_size': f"{RECOMMENDED_UNIT_SIZE * 100}%",
        'max_bets_per_day': MAX_BETS_PER_DAY,
    }

