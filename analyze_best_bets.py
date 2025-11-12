#!/usr/bin/env python3
"""
Analyze performance of the TOP 5 BEST BETS specifically
(The actual bets you would make, not all games)
"""

import os
import sys
import argparse
from datetime import datetime
from dotenv import load_dotenv
from tabulate import tabulate

from api_client import CollegeBasketballAPI
from model import BasketballPredictionModel
from best_bets import BestBetsSelector
from database import SupabaseCache


def check_bet_result(bet: dict, game: dict) -> tuple:
    """
    Check if a bet won or lost
    
    Returns:
        (won: bool, actual_result: str, margin: float)
    """
    home_score = game.get('home_score', 0)
    away_score = game.get('away_score', 0)
    actual_spread = home_score - away_score
    actual_total = home_score + away_score
    
    bet_type = bet['bet_type']
    pick = bet['pick']
    
    if bet_type == 'Spread':
        # Parse the pick to get team and spread
        # Format: "Team Name +/-X.X"
        parts = pick.rsplit(' ', 1)
        if len(parts) != 2:
            return False, "Error parsing pick", 0
        
        team_name = parts[0]
        spread_value = float(parts[1])
        
        # Determine if this is home or away team
        home_team = game.get('home_team', '')
        away_team = game.get('away_team', '')
        
        if team_name == home_team:
            # Bet on home team
            won = actual_spread > spread_value
            result = f"{home_team} {home_score}, {away_team} {away_score} (Home by {actual_spread:+.0f})"
            margin = actual_spread - spread_value
        elif team_name == away_team:
            # Bet on away team
            won = actual_spread < spread_value
            result = f"{away_team} {away_score}, {home_team} {home_score} (Away by {-actual_spread:+.0f})"
            margin = spread_value - actual_spread
        else:
            return False, "Team name mismatch", 0
        
        return won, result, margin
    
    elif bet_type == 'Total':
        # Parse Over/Under
        if 'Over' in pick:
            line = float(pick.split('Over ')[1])
            won = actual_total > line
            margin = actual_total - line
        elif 'Under' in pick:
            line = float(pick.split('Under ')[1])
            won = actual_total < line
            margin = line - actual_total
        else:
            return False, "Error parsing total", 0
        
        result = f"Total: {actual_total} (Line: {line})"
        return won, result, margin
    
    return False, "Unknown bet type", 0


def main():
    """Main analysis function"""
    parser = argparse.ArgumentParser(
        description='Analyze Best Bets Performance',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                      # Analyze today's best bets
  %(prog)s -d 2025-11-11        # Analyze best bets from Nov 11, 2025
        """
    )
    parser.add_argument(
        '-d', '--date',
        type=str,
        help='Date to analyze in YYYY-MM-DD format (default: today)'
    )
    parser.add_argument(
        '--max-odds',
        type=int,
        default=-125,
        help='Maximum odds for best bets (default: -125)'
    )
    
    args = parser.parse_args()
    
    load_dotenv()
    
    api_key = os.getenv('API_KEY')
    if not api_key:
        print("Error: API_KEY not found in environment variables")
        return
    
    # Validate and set date
    if args.date:
        try:
            datetime.strptime(args.date, '%Y-%m-%d')
            target_date = args.date
        except ValueError:
            print(f"❌ Error: Invalid date format '{args.date}'")
            print("   Please use YYYY-MM-DD format (e.g., 2025-11-08)")
            sys.exit(1)
    else:
        target_date = datetime.now().strftime('%Y-%m-%d')
    
    print("=" * 80)
    print(f"BEST BETS PERFORMANCE ANALYSIS - {target_date}")
    print("=" * 80)
    print()
    
    # Initialize caching (if enabled)
    cache = None
    use_cache = os.getenv('USE_CACHE', 'true').lower() == 'true'
    if use_cache:
        supabase_url = os.getenv('SUPABASE_URL')
        supabase_key = os.getenv('SUPABASE_SERVICE_KEY')
        
        if supabase_url and supabase_key:
            try:
                cache = SupabaseCache(supabase_url, supabase_key)
            except:
                pass
    
    # Initialize API and model
    api_client = CollegeBasketballAPI(api_key, cache=cache)
    model = BasketballPredictionModel(api_client)
    selector = BestBetsSelector(max_odds=args.max_odds)
    
    # Get completed games for target date
    print(f"Fetching games for {target_date}...")
    games = api_client.get_todays_games(date=target_date, d1_only=True, upcoming_only=False)
    
    # Filter for completed games with scores
    completed_games = [
        g for g in games 
        if g.get('home_score') is not None and g.get('away_score') is not None
        and g.get('home_score', 0) > 0
    ]
    
    if not completed_games:
        print(f"\n❌ No completed games found for {target_date}")
        return
    
    print(f"Found {len(completed_games)} completed games\n")
    print("Generating predictions and selecting best bets...\n")
    
    # Generate all predictions and bets (same logic as main.py)
    all_bets = []
    
    for game in completed_games:
        home_team_id = game.get('home_team_id', 0)
        away_team_id = game.get('away_team_id', 0)
        home_team = game.get('home_team', 'Home')
        away_team = game.get('away_team', 'Away')
        
        if not home_team_id or not away_team_id:
            continue
        
        try:
            # Get odds
            odds_data = api_client.get_odds_for_team_date(home_team, target_date)
            if not odds_data or 'spread' not in odds_data:
                # Create default odds
                odds_data = {
                    'spread': {'home_spread': -5.5, 'away_spread': 5.5, 'home_odds': -110, 'away_odds': -110},
                    'total': {'line': 145.5, 'over_odds': -110, 'under_odds': -110}
                }
            
            game['odds'] = odds_data
            
            # Get predictions
            predicted_spread, spread_confidence = model.predict_spread(home_team_id, away_team_id, game)
            predicted_total, total_confidence = model.predict_total(home_team_id, away_team_id, game)
            
            # Calculate projected scores
            home_projected = (predicted_total + predicted_spread) / 2
            away_projected = (predicted_total - predicted_spread) / 2
            
            # Create bets
            spread_bets = selector.create_bet_from_prediction(
                game, 'spread', predicted_spread, spread_confidence, odds_data
            )
            total_bets = selector.create_bet_from_prediction(
                game, 'total', predicted_total, total_confidence, odds_data
            )
            
            # Add projected scores to bets
            for bet in spread_bets + total_bets:
                bet['home_projected'] = home_projected
                bet['away_projected'] = away_projected
                bet['game'] = game  # Store game reference for result checking
            
            all_bets.extend(spread_bets)
            all_bets.extend(total_bets)
        
        except Exception as e:
            print(f"  ⚠️  Error analyzing {away_team} @ {home_team}: {e}")
            continue
    
    # Select best bets (same as main.py)
    best_bets = selector.select_best_bets(all_bets)
    
    if not best_bets:
        print("No best bets found that meet the criteria.")
        return
    
    print(f"Selected {len(best_bets)} best bets\n")
    
    # Analyze results for each best bet
    results = []
    for i, bet in enumerate(best_bets, 1):
        game = bet.get('game')
        if not game:
            continue
        
        won, result_str, margin = check_bet_result(bet, game)
        
        results.append({
            'rank': i,
            'game': bet['game_description'],
            'type': bet['bet_type'],
            'pick': bet['pick'],
            'odds': bet['odds'],
            'value_rating': bet['predicted_prob'],
            'confidence': bet['confidence'],
            'score': bet['score'],
            'won': won,
            'result': result_str,
            'margin': margin
        })
    
    # Display results
    print("=" * 80)
    print("BEST BETS RESULTS")
    print("=" * 80)
    print()
    
    table_data = []
    for r in results:
        status = "✅ WON" if r['won'] else "❌ LOST"
        table_data.append([
            f"#{r['rank']}",
            r['game'][:35],
            r['type'],
            r['pick'][:20],
            f"{r['odds']:+d}" if r['odds'] < 0 else f"+{r['odds']}",
            f"{r['value_rating']:.1%}",
            f"{r['confidence']:.1%}",
            status
        ])
    
    print(tabulate(table_data,
                   headers=['Rank', 'Game', 'Type', 'Pick', 'Odds', 'Value', 'Conf', 'Result'],
                   tablefmt='grid'))
    
    # Detailed results
    print(f"\n{'=' * 80}")
    print("DETAILED RESULTS")
    print(f"{'=' * 80}\n")
    
    for r in results:
        status = "✅ WON" if r['won'] else "❌ LOST"
        print(f"#{r['rank']} - {r['game']}")
        print(f"    Pick: {r['pick']} ({r['odds']:+d})")
        print(f"    Value Rating: {r['value_rating']:.1%} | Confidence: {r['confidence']:.1%} | Score: {r['score']:.3f}")
        print(f"    Result: {r['result']}")
        print(f"    Status: {status}")
        if r['won']:
            print(f"    Won by: {r['margin']:.1f} points")
        else:
            print(f"    Lost by: {abs(r['margin']):.1f} points")
        print()
    
    # Calculate statistics
    wins = sum(1 for r in results if r['won'])
    losses = len(results) - wins
    win_pct = wins / len(results) * 100 if results else 0
    
    # Separate by type
    spread_results = [r for r in results if r['type'] == 'Spread']
    total_results = [r for r in results if r['type'] == 'Total']
    
    spread_wins = sum(1 for r in spread_results if r['won'])
    spread_losses = len(spread_results) - spread_wins
    spread_pct = spread_wins / len(spread_results) * 100 if spread_results else 0
    
    total_wins = sum(1 for r in total_results if r['won'])
    total_losses = len(total_results) - total_wins
    total_pct = total_wins / len(total_results) * 100 if total_results else 0
    
    print(f"{'=' * 80}")
    print("SUMMARY")
    print(f"{'=' * 80}\n")
    
    print(f"📊 OVERALL BEST BETS:")
    print(f"   Record: {wins}-{losses}")
    print(f"   Win Rate: {win_pct:.1f}%")
    print(f"   {'✅ PROFITABLE' if win_pct > 52.4 else '❌ NOT PROFITABLE'} (need >52.4%)")
    print()
    
    if spread_results:
        print(f"📊 SPREAD BETS:")
        print(f"   Record: {spread_wins}-{spread_losses}")
        print(f"   Win Rate: {spread_pct:.1f}%")
        print()
    
    if total_results:
        print(f"📊 TOTAL BETS:")
        print(f"   Record: {total_wins}-{total_losses}")
        print(f"   Win Rate: {total_pct:.1f}%")
        print()
    
    # ROI calculation
    if wins + losses > 0:
        # Assuming -110 odds
        profit = wins * 0.909 - losses  # Win $0.909 for every $1 risked at -110
        roi = (profit / (wins + losses)) * 100
        
        print(f"💰 ROI (at -110 odds):")
        print(f"   Units: {profit:+.2f}u")
        print(f"   ROI: {roi:+.1f}%")
        print()
    
    print(f"{'=' * 80}")
    print("✅ Analysis Complete!")
    print(f"{'=' * 80}")


if __name__ == '__main__':
    main()

