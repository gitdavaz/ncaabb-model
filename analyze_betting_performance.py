#!/usr/bin/env python3
"""
Analyze actual betting performance (wins vs losses), not prediction accuracy
"""

import os
from dotenv import load_dotenv
from api_client import CollegeBasketballAPI
from model import BasketballPredictionModel
from database import SupabaseCache

load_dotenv()

cache = SupabaseCache(os.getenv('SUPABASE_URL'), os.getenv('SUPABASE_SERVICE_KEY'))
api = CollegeBasketballAPI(os.getenv('API_KEY'), cache=cache)
model = BasketballPredictionModel(api)

print("="*70)
print("BETTING PERFORMANCE ANALYSIS")
print("Focus: Did the BET WIN against the market?")
print("="*70)

# Get all completed games
games = api.get_todays_games(date='2025-11-11', d1_only=True, upcoming_only=False)

spread_wins = 0
spread_losses = 0
total_wins = 0
total_losses = 0

losing_bets = []

for game in games:
    home_score = game.get('home_score', 0)
    away_score = game.get('away_score', 0)
    
    # Skip if not completed
    if home_score == 0 and away_score == 0:
        continue
        
    home_team = game.get('home_team', '')
    away_team = game.get('away_team', '')
    home_id = game.get('home_team_id')
    away_id = game.get('away_team_id')
    
    if not home_id or not away_id:
        continue
    
    # Get odds
    odds_data = api.get_odds_for_team_date(home_team, '2025-11-11')
    if not odds_data or 'spread' not in odds_data:
        continue
    
    game['odds'] = odds_data
    
    # Get model predictions
    try:
        predicted_spread, spread_conf = model.predict_spread(home_id, away_id, game)
        predicted_total, total_conf = model.predict_total(home_id, away_id, game)
    except:
        continue
    
    # Market lines
    market_spread_home = odds_data['spread']['home_spread']
    market_total = odds_data['total']['line']
    
    # Actual results
    actual_spread = home_score - away_score  # Positive = home won
    actual_total = home_score + away_score
    
    # SPREAD BET ANALYSIS
    # Determine which side model would bet based on model vs market
    # edge = predicted_spread + market_spread_home
    # Positive edge = model more bullish on home, negative = model more bullish on away
    edge = predicted_spread + market_spread_home
    
    if edge > 0:
        # Model likes home team more than market
        bet_result = actual_spread > market_spread_home  # Did home cover?
        bet_pick = f"{home_team} {market_spread_home:+.1f}"
    else:
        # Model likes away team more than market
        bet_result = actual_spread < market_spread_home  # Did away cover?
        away_spread = -market_spread_home
        bet_pick = f"{away_team} {away_spread:+.1f}"
    
    if bet_result:
        spread_wins += 1
    else:
        spread_losses += 1
        losing_bets.append({
            'game': f"{away_team} @ {home_team}",
            'type': 'Spread',
            'pick': bet_pick,
            'predicted': predicted_spread,
            'actual': actual_spread,
            'market': market_spread_home,
            'confidence': spread_conf
        })
    
    # TOTAL BET ANALYSIS
    if predicted_total > market_total:
        # Model says Over
        bet_result = actual_total > market_total
        bet_pick = f"Over {market_total}"
    else:
        # Model says Under
        bet_result = actual_total < market_total
        bet_pick = f"Under {market_total}"
    
    if bet_result:
        total_wins += 1
    else:
        total_losses += 1
        losing_bets.append({
            'game': f"{away_team} @ {home_team}",
            'type': 'Total',
            'pick': bet_pick,
            'predicted': predicted_total,
            'actual': actual_total,
            'market': market_total,
            'confidence': total_conf
        })

# Print results
print(f"\n{'='*70}")
print("BETTING RECORD:")
print(f"{'='*70}")
print(f"\nSPREAD BETS: {spread_wins}-{spread_losses} ({spread_wins/(spread_wins+spread_losses)*100:.1f}% win rate)")
print(f"TOTAL BETS: {total_wins}-{total_losses} ({total_wins/(total_wins+total_losses)*100:.1f}% win rate)")
print(f"\nOVERALL: {spread_wins+total_wins}-{spread_losses+total_losses} ({(spread_wins+total_wins)/(spread_wins+total_wins+spread_losses+total_losses)*100:.1f}% win rate)")

# Break even is 52.4% (accounting for -110 juice)
overall_pct = (spread_wins+total_wins)/(spread_wins+total_wins+spread_losses+total_losses)*100
if overall_pct > 52.4:
    print(f"✅ PROFITABLE (need 52.4% to break even with -110 odds)")
else:
    print(f"❌ NOT PROFITABLE (need 52.4% to break even with -110 odds)")

print(f"\n{'='*70}")
print(f"LOSING BETS (these need analysis):")
print(f"{'='*70}")

for bet in losing_bets:
    print(f"\n❌ {bet['game']}")
    print(f"   Type: {bet['type']}")
    print(f"   Model Pick: {bet['pick']}")
    if bet['type'] == 'Spread':
        print(f"   Market: Home {bet['market']:+.1f}")
        print(f"   Model predicted spread: {bet['predicted']:+.1f}")
        print(f"   Actual spread: {bet['actual']:+.1f}")
    else:
        print(f"   Market: {bet['market']}")
        print(f"   Model predicted total: {bet['predicted']:.1f}")
        print(f"   Actual total: {bet['actual']}")
    print(f"   Model Confidence: {bet['confidence']:.1%}")

