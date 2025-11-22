#!/usr/bin/env python3
"""
NCAAM Basketball Betting Model CLI
"""

import os
import sys
import argparse
from datetime import datetime, timezone, timedelta
from typing import List, Dict
from dotenv import load_dotenv
from tabulate import tabulate

from api_client import CollegeBasketballAPI
from model import BasketballPredictionModel
from best_bets import BestBetsSelector
from model_picks_db import ModelPicksDB
import config


def get_confidence_emoji(confidence: float) -> str:
    """Get emoji for confidence level"""
    if confidence >= 0.75:
        return "🔥"  # Very High
    elif confidence >= 0.65:
        return "✅"  # High
    elif confidence >= 0.55:
        return "⚠️"  # Moderate
    else:
        return "❌"  # Low


def get_confidence_label(confidence: float) -> str:
    """Get label for confidence level"""
    if confidence >= 0.75:
        return "Very High"
    elif confidence >= 0.65:
        return "High"
    elif confidence >= 0.55:
        return "Moderate"
    else:
        return "Low"


def parse_game_time_to_est(start_date_str: str) -> datetime:
    """Parse game start time and convert to EST"""
    try:
        if isinstance(start_date_str, str):
            # Remove timezone info if present for parsing
            start_str = start_date_str.replace('+00:00', '').replace('Z', '')
            # Parse as UTC
            game_time_utc = datetime.fromisoformat(start_str.split('.')[0])
            game_time_utc = game_time_utc.replace(tzinfo=timezone.utc)
            # Convert to EST (UTC-5)
            est_offset = timedelta(hours=-5)
            game_time_est = game_time_utc + est_offset
            return game_time_est
    except:
        pass
    
    # Return far future if can't parse (will sort to end)
    return datetime(2099, 12, 31)


def print_banner():
    """Print application banner"""
    banner = """
╔═══════════════════════════════════════════════════════════╗
║        NCAAM Basketball Betting Model                     ║
║        Daily Picks & Best Bets                            ║
╚═══════════════════════════════════════════════════════════╝
    """
    print(banner)


def format_odds(odds: int) -> str:
    """Format odds with + or - sign"""
    if odds > 0:
        return f"+{odds}"
    return str(odds)


def print_game_predictions(predictions: List[Dict]):
    """
    Print all game predictions in a table
    
    Args:
        predictions: List of prediction dictionaries
    """
    if not predictions:
        print("\nNo games found for today.")
        return
    
    # Parse the date for display
    try:
        display_date = datetime.strptime(predictions[0]['date'], '%Y-%m-%d').strftime('%A, %B %d, %Y')
    except:
        display_date = datetime.now().strftime('%A, %B %d, %Y')
    
    print(f"\n{'=' * 80}")
    print(f"ALL GAMES - {display_date}")
    print(f"{'=' * 80}\n")
    
    # Build table data
    table_data = []
    
    for pred in predictions:
        # Get game time
        game_time = pred.get('start_time', '')
        
        # Get conference info
        conf_info = ""
        if pred.get('home_conference') and pred.get('away_conference'):
            away_conf = pred['away_conference'][:8]  # Abbreviate long conference names
            home_conf = pred['home_conference'][:8]
            conf_info = f"{away_conf} vs {home_conf}"
        
        # Format confidence and value as simple percentage (no emojis for better alignment)
        spread_conf_str = f"{pred['spread_confidence']:.0%}"
        total_conf_str = f"{pred['total_confidence']:.0%}"
        spread_value_str = f"{pred.get('spread_value', 0):.0%}"
        total_value_str = f"{pred.get('total_value', 0):.0%}"
        
        # Ensure consistent pick lengths
        spread_pick = pred['spread_pick'][:25]  # Limit length
        total_pick = pred['total_pick'][:15]  # Limit length
        
        # Format projected score (away @ home format)
        home_proj = pred.get('home_projected', 0)
        away_proj = pred.get('away_projected', 0)
        projected_score = f"{away_proj:.0f}-{home_proj:.0f}"
        
        table_data.append([
            game_time,
            pred['game_description'][:35],  # Truncate long names
            projected_score,
            conf_info,
            spread_pick,
            spread_value_str,
            spread_conf_str,
            total_pick,
            total_value_str,
            total_conf_str
        ])
    
    # Print table
    headers = ['Time (EST)', 'Game', 'Proj Score', 'Matchup', 'Spread Pick', 'S Val', 'S Conf', 'Total Pick', 'T Val', 'T Conf']
    print(tabulate(table_data, headers=headers, tablefmt='grid'))
    
    # Print legend
    print(f"\n{'─' * 80}")
    print("CONFIDENCE LEVELS:")
    print("  75%+     = 🔥 Very High")
    print("  65-75%   = ✅ High")
    print("  55-65%   = ⚠️  Moderate")
    print("  Below 55% = ❌ Low")
    print(f"{'─' * 80}")


def print_best_bets(best_bets: List[Dict]):
    """
    Print best bets in a table
    
    Args:
        best_bets: List of best bet dictionaries
    """
    if not best_bets:
        print("\nNo best bets found that meet the criteria.")
        return
    
    print(f"\n{'=' * 80}")
    print(f"TOP 5 BEST BETS (Highest Statistical Likelihood)")
    print(f"{'=' * 80}\n")
    
    table_data = []
    for i, bet in enumerate(best_bets, 1):
        table_data.append([
            f"#{i}",
            bet.get('start_time', 'TBD'),
            bet['game_description'],
            bet['bet_type'],
            bet['pick'],
            format_odds(bet['odds']),
            f"{bet['predicted_prob']:.1%}",
            f"{bet['confidence']:.1%}",
            f"{bet['score']:.3f}"
        ])
    
    print(tabulate(table_data,
                  headers=['Rank', 'Time (EST)', 'Game', 'Type', 'Pick', 'Odds', 'Value', 'Confidence', 'Score'],
                  tablefmt='grid'))
    
    # Print detailed reasoning for each bet
    print(f"\n{'=' * 80}")
    print("DETAILED ANALYSIS")
    print(f"{'=' * 80}\n")
    
    for i, bet in enumerate(best_bets, 1):
        # Extract team names from game_description (format: "Away @ Home")
        game_parts = bet['game_description'].split(' @ ')
        away_team = game_parts[0] if len(game_parts) > 0 else "Away"
        home_team = game_parts[1] if len(game_parts) > 1 else "Home"
        
        # Get projected scores
        home_proj = bet.get('home_projected', 0)
        away_proj = bet.get('away_projected', 0)
        
        print(f"#{i} - {bet['game_description']} ({bet.get('start_time', 'TBD')} EST)")
        print(f"    Projected Score: {home_team} {home_proj:.1f}, {away_team} {away_proj:.1f}")
        print(f"    Pick: {bet['pick']} ({format_odds(bet['odds'])})")
        print(f"    Reasoning: {bet['reasoning']}")
        print(f"    Value Rating: {bet['predicted_prob']:.1%}")
        print(f"    Model Confidence: {bet['confidence']:.1%}\n")


def main():
    """Main CLI application"""
    # Parse command-line arguments
    parser = argparse.ArgumentParser(
        description='NCAAM Basketball Betting Model - Daily Picks & Best Bets',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                      # Analyze today's games
  %(prog)s --date 2025-11-08    # Analyze games on Nov 8, 2025
  %(prog)s -d 2025-11-10        # Short form
  %(prog)s --all-games          # Include completed games (not just upcoming)
  %(prog)s -d 2025-11-07 --all  # Analyze all games from Nov 7
        """
    )
    parser.add_argument(
        '-d', '--date',
        type=str,
        help='Date to analyze in YYYY-MM-DD format (default: today)'
    )
    parser.add_argument(
        '-a', '--all-games',
        action='store_true',
        help='Include completed games (default: only upcoming games)'
    )
    parser.add_argument(
        '--max-odds',
        type=int,
        default=-125,
        help='Maximum odds for best bets (default: -125)'
    )
    
    args = parser.parse_args()
    
    # Load environment variables
    load_dotenv()
    
    # Print banner
    print_banner()
    
    # Validate and set date
    if args.date:
        try:
            # Validate date format
            datetime.strptime(args.date, '%Y-%m-%d')
            today = args.date
            print(f"📅 Analyzing games for: {args.date}")
        except ValueError:
            print(f"❌ Error: Invalid date format '{args.date}'")
            print("   Please use YYYY-MM-DD format (e.g., 2025-11-08)")
            sys.exit(1)
    else:
        today = datetime.now().strftime('%Y-%m-%d')
        print(f"📅 Analyzing games for today: {today}")
    
    # Get API key
    api_key = os.getenv('API_KEY')
    if not api_key:
        print("\n⚠️  Warning: API_KEY not found in environment variables.")
        print("   Some features may not work without authentication.")
        print("   Create a .env file with your API key: API_KEY=your_key_here\n")
    
    # Initialize caching and picks database (if enabled)
    cache = None
    picks_db = None
    use_cache = os.getenv('USE_CACHE', 'true').lower() == 'true'
    if use_cache:
        supabase_url = os.getenv('SUPABASE_URL')
        supabase_key = os.getenv('SUPABASE_SERVICE_KEY')
        
        if supabase_url and supabase_key:
            try:
                from database import SupabaseCache
                cache = SupabaseCache(supabase_url, supabase_key)
                picks_db = ModelPicksDB(supabase_url, supabase_key)
                print("✅ Cache enabled (Supabase)")
                print("✅ Picks database enabled (Supabase)")
            except Exception as e:
                print(f"⚠️  Cache initialization failed: {e}")
                print("   Continuing without cache...")
        else:
            print("⚠️  Cache disabled (missing SUPABASE_URL or SUPABASE_SERVICE_KEY)")
    
    # Initialize components
    print("Initializing model...")
    api_client = CollegeBasketballAPI(api_key, cache=cache)
    model = BasketballPredictionModel(api_client)
    selector = BestBetsSelector(max_odds=args.max_odds)
    
    # Determine which games to fetch
    upcoming_only = not args.all_games
    game_type = "all" if args.all_games else "upcoming"
    
    # Get games (D1 only)
    print(f"Fetching {game_type} D1 conference games for {today}...")
    today = today
    current_season = api_client._get_current_season()
    
    # Get games based on user preference
    games = api_client.get_todays_games(today, d1_only=True, upcoming_only=upcoming_only)
    
    if not games:
        print(f"\n❌ No {game_type} D1 games found for {today}")
        print("   Possible reasons:")
        if upcoming_only:
            print("   1. All games for this date have already been played")
            print("   2. No games scheduled on this date (off day)")
            print("   3. Games haven't started yet (check back closer to game time)")
            
            # Check if there are completed games on this date
            print(f"\n   Checking for completed games on {today}...")
            try:
                completed = api_client.get_todays_games(today, d1_only=True, upcoming_only=False)
                if completed:
                    print(f"   ✓ Found {len(completed)} completed games from {today}")
                    print(f"   💡 Tip: Run with --all-games flag to include completed games")
            except:
                pass
        else:
            print("   1. No games scheduled on this date")
            print("   2. The date might be outside the season")
        
        # Try to get upcoming games from next few days
        print(f"\n   Looking for upcoming games in next 7 days...")
        try:
            from datetime import timedelta
            now = datetime.now()
            for days_ahead in range(1, 8):
                check_date = (now + timedelta(days=days_ahead)).strftime('%Y-%m-%d')
                upcoming = api_client.get_todays_games(check_date, d1_only=True, upcoming_only=True)
                if upcoming:
                    date_str = (now + timedelta(days=days_ahead)).strftime('%A, %B %d')
                    print(f"   ✓ Found {len(upcoming)} games on {date_str}")
                    response = input(f"\n   Would you like to analyze games for {date_str}? (y/n): ")
                    if response.lower() == 'y':
                        games = upcoming
                        today = check_date
                    break
        except:
            pass
        
        if not games:
            print("\n   No upcoming games found in next 7 days.")
            print("   Creating sample predictions for demonstration...\n")
            games = create_sample_games()
    
    # Generate predictions for all games
    print(f"Analyzing {len(games)} D1 conference games (exhibition games filtered out)...\n")
    
    # Get current time in UTC for filtering
    from datetime import timezone
    current_time_utc = datetime.now(timezone.utc)
    
    all_predictions = []
    all_bets = []
    games_not_started = []
    games_with_times = []  # Store (game, start_time_est) tuples for sorting
    
    # First pass: get all games with their EST times for sorting
    for game in games:
        start_date_str = game.get('start_date', '')
        game_time_est = parse_game_time_to_est(start_date_str)
        games_with_times.append((game, game_time_est))
    
    # Sort by start time
    games_with_times.sort(key=lambda x: x[1])
    
    # Second pass: process in time order
    for game, game_time_est in games_with_times:
        try:
            game_id = game.get('id', '')
            home_team = game.get('home_team', 'Home Team')
            away_team = game.get('away_team', 'Away Team')
            home_team_id = game.get('home_team_id', 0)
            away_team_id = game.get('away_team_id', 0)
            
            print(f"  Analyzing: {away_team} @ {home_team}...")
            
            # Get odds using team name and date
            start_date_raw = game.get('start_date', today)
            if isinstance(start_date_raw, str):
                game_date = start_date_raw.split('T')[0]
            else:
                # It's already a datetime object
                game_date = start_date_raw.strftime('%Y-%m-%d') if hasattr(start_date_raw, 'strftime') else today
            odds_data = api_client.get_odds_for_team_date(home_team, game_date)
            
            # If no odds data, create defaults
            if not odds_data or 'spread' not in odds_data:
                odds_data = create_default_odds()
            
            # Add odds to game dictionary for market-informed predictions
            game['odds'] = odds_data
            
            # Predict spread
            predicted_spread, spread_confidence = model.predict_spread(home_team_id, away_team_id, game)
            
            # Predict total
            predicted_total, total_confidence = model.predict_total(home_team_id, away_team_id, game)
            
            # Calculate projected scores
            # predicted_spread = home_score - away_score
            # predicted_total = home_score + away_score
            # Therefore: home_score = (total + spread) / 2, away_score = (total - spread) / 2
            home_projected = (predicted_total + predicted_spread) / 2
            away_projected = (predicted_total - predicted_spread) / 2
            
            # Create prediction entry
            game_desc = f"{away_team} @ {home_team}"
            
            # Store date in prediction for display
            prediction_date = today
            
            # Determine spread pick using same logic as best_bets.py
            market_spread = odds_data.get('spread', {})
            home_spread = market_spread.get('home_spread', 0)
            away_spread = market_spread.get('away_spread', 0)
            home_odds = market_spread.get('home_odds', -110)
            away_odds = market_spread.get('away_odds', -110)
            
            # Determine which side to bet based on model vs market
            # Edge calculation: positive edge means model is more bullish on home than market
            # home_spread is negative when home is favored (e.g., -10 means home gives 10 points)
            # predicted_spread = home_score - away_score (positive means home wins)
            # 
            # To compare apples-to-apples, convert both to expected home margins:
            # - Model's expected home margin: predicted_spread
            # - Market's expected home margin: -home_spread (negative of the spread)
            # - edge = predicted_spread - (-home_spread) = predicted_spread + home_spread
            edge = predicted_spread + home_spread
            
            if edge > 0:
                # Model is more bullish on home team than market
                # Bet home side (model thinks home will do better than market expects)
                spread_pick = f"{home_team} {home_spread:+.1f}"
                spread_odds = home_odds
            else:
                # Model is more bullish on away team than market
                # Bet away side (model thinks away will do better than market expects)
                spread_pick = f"{away_team} {away_spread:+.1f}"
                spread_odds = away_odds
            
            # Determine total pick
            market_total = odds_data.get('total', {})
            total_line = market_total.get('line', predicted_total)
            
            if predicted_total > total_line:
                total_pick = f"Over {total_line}"
                total_odds = market_total.get('over_odds', -110)
            else:
                total_pick = f"Under {total_line}"
                total_odds = market_total.get('under_odds', -110)
            
            # Format game time
            time_str = game_time_est.strftime('%I:%M %p') if game_time_est.year != 2099 else "TBD"
            
            # Initialize value placeholders (will be calculated from bets later)
            spread_value = 0
            total_value = 0
            
            prediction = {
                'game_id': game_id,
                'game_description': game_desc,
                'date': today,
                'start_time': time_str,
                'start_time_sort': game_time_est,  # For sorting
                'home_team': home_team,
                'away_team': away_team,
                'home_conference': game.get('home_conference'),
                'away_conference': game.get('away_conference'),
                'home_projected': home_projected,
                'away_projected': away_projected,
                'predicted_spread': predicted_spread,
                'spread_pick': spread_pick,
                'spread_odds': spread_odds,
                'spread_value': spread_value,
                'spread_confidence': spread_confidence,
                'spread_reasoning': f"Model predicts {abs(predicted_spread):.1f} pt margin",
                'total_pick': total_pick,
                'total_odds': total_odds,
                'total_value': total_value,
                'total_confidence': total_confidence,
                'total_reasoning': f"Model predicts {predicted_total:.1f} total points"
            }
            
            all_predictions.append(prediction)
            
            # Check if game hasn't started yet for best bets
            game_start = game.get('start_date')
            game_has_started = False
            
            if game_start:
                # Parse start time (it's in UTC)
                try:
                    if isinstance(game_start, str):
                        # Remove timezone info if present for parsing
                        start_str = game_start.replace('+00:00', '').replace('Z', '')
                        game_start_time = datetime.fromisoformat(start_str.split('.')[0])
                        # Make it timezone-aware (UTC)
                        game_start_time = game_start_time.replace(tzinfo=timezone.utc)
                    else:
                        # It's already a datetime object
                        game_start_time = game_start if hasattr(game_start, 'tzinfo') else game_start.replace(tzinfo=timezone.utc)
                    
                    game_has_started = current_time_utc >= game_start_time
                except:
                    pass
            
            # Track games that haven't started
            if not game_has_started:
                games_not_started.append(game)
            
            # ALWAYS create bets for ALL games (for database tracking)
            spread_bets = selector.create_bet_from_prediction(
                game, 'spread', predicted_spread, spread_confidence, odds_data
            )
            total_bets = selector.create_bet_from_prediction(
                game, 'total', predicted_total, total_confidence, odds_data
            )
            
            # Extract value (predicted_prob) from bets for display in ALL GAMES table
            # Update the prediction dict with actual values now that bets are created
            prediction['spread_value'] = spread_bets[0]['predicted_prob'] if spread_bets else 0
            prediction['total_value'] = total_bets[0]['predicted_prob'] if total_bets else 0
            
            # Add projected scores and start time to bet dictionaries
            for bet in spread_bets + total_bets:
                bet['home_projected'] = home_projected
                bet['away_projected'] = away_projected
                bet['start_time'] = time_str  # Formatted string for display (EST)
                bet['start_time_sort'] = game_time_est  # For sorting (EST)
                bet['start_time_utc'] = game.get('start_date')  # Original UTC for database
                bet['game_has_started'] = game_has_started  # Track status
            
            # Apply early-season total bet filter (Option B: Only recommend high-scoring totals)
            # Spread bets have proven reliable (53.7% win rate), but total bets struggle (42.6%)
            # Best bets went 10-2, proving the scoring algorithm works - trust it!
            game_date = game_time_est.date() if hasattr(game_time_est, 'date') else game_time_est
            is_early_season = (
                game_date.month < config.EARLY_SEASON_END_DATE[0] or
                (game_date.month == config.EARLY_SEASON_END_DATE[0] and 
                 game_date.day <= config.EARLY_SEASON_END_DATE[1])
            )
            
            for bet in total_bets:
                # Mark total bets as not recommended if below threshold during early season
                if is_early_season and bet.get('score', 0) < config.EARLY_SEASON_TOTAL_MIN_SCORE:
                    bet['recommended'] = False
                    bet['skip_reason'] = 'Early season: Total bet score below threshold (0.50)'
                else:
                    bet['recommended'] = True
            
            # Mark spread bets as recommended unless they're large underdog spreads
            for bet in spread_bets:
                # Extract the spread value from the pick (e.g., "Team +20.5" -> 20.5)
                pick = bet.get('pick', '')
                if '+' in pick:
                    # Extract spread value for underdog bets
                    try:
                        spread_value = float(pick.split('+')[1])
                        # Filter out large underdog spreads (+20 or more)
                        if spread_value >= 20.0:
                            bet['recommended'] = False
                            bet['skip_reason'] = f'Large underdog spread (+{spread_value:.1f}): High variance/blowout risk'
                        else:
                            bet['recommended'] = True
                    except (ValueError, IndexError):
                        bet['recommended'] = True  # If parsing fails, keep it
                else:
                    bet['recommended'] = True  # Favorite bets are always recommended
            
            # Always add to all_bets for database saving
            all_bets.extend(spread_bets)
            all_bets.extend(total_bets)
            
        except Exception as e:
            print(f"  ⚠️  Error analyzing game: {e}")
            continue
    
    # Print all game predictions
    print_game_predictions(all_predictions)
    
    # Print bet filter summary
    not_recommended_totals = [bet for bet in all_bets if not bet.get('recommended', True) and bet['bet_type'] == 'total']
    not_recommended_spreads = [bet for bet in all_bets if not bet.get('recommended', True) and bet['bet_type'] == 'spread']
    
    if not_recommended_totals or not_recommended_spreads:
        print(f"\n⚠️  Smart Filters Active:")
        
        if not_recommended_spreads:
            print(f"   🚫 {len(not_recommended_spreads)} large underdog spread(s) filtered out (+20 or more)")
            print(f"      Reason: High variance/blowout risk (33% win rate on Nov 21)")
        
        if not_recommended_totals:
            print(f"   🚫 {len(not_recommended_totals)} early-season total bet(s) filtered out (score < 0.50)")
            print(f"      Reason: Total bets risky early season (42.6% win rate vs 53.7% for spreads)")
        
        print(f"   ℹ️  Filtered bets still saved to database for tracking")
    
    # Select and print best bets
    games_started = len(games) - len(games_not_started)
    
    # Filter bets for best bets selection based on --all-games flag
    # Also filter out non-recommended bets (early-season low-scoring totals)
    if args.all_games:
        # When using --all-games, include all games for best bets (but only recommended bets)
        bets_for_selection = [bet for bet in all_bets if bet.get('recommended', True)]
        print(f"\nSelecting top 5 best bets from {len(games)} game(s) (odds -125 or better)...")
        if games_started > 0:
            print(f"   ℹ️  Note: {games_started} game(s) have already completed")
    else:
        # Normal mode: only include bets for games that haven't started AND are recommended
        bets_for_selection = [bet for bet in all_bets 
                             if not bet.get('game_has_started', False) 
                             and bet.get('recommended', True)]
        if games_started > 0:
            print(f"\n⏰ Note: {games_started} game(s) have already started and excluded from best bets")
        print(f"\nSelecting top 5 best bets from {len(games_not_started)} games that haven't started (odds -125 or better)...")
    
    best_bets = selector.select_best_bets(bets_for_selection)
    print_best_bets(best_bets)
    
    # Save all picks to database (if enabled)
    # NOTE: We save ALL bets including non-recommended ones for complete tracking/analysis
    if picks_db and all_bets:
        recommended_count = len([b for b in all_bets if b.get('recommended', True)])
        print(f"\n💾 Saving {len(all_bets)} picks to database ({recommended_count} recommended)...")
        
        # Convert bets to database format
        db_picks = []
        for bet in all_bets:
            # Get game info from the bet
            game_desc = bet.get('game_description', '')
            parts = game_desc.split(' @ ')
            if len(parts) != 2:
                continue
            
            away_team = parts[0]
            home_team = parts[1]
            
            # Create database record
            # Use the original UTC time from the API (not the EST-converted display time)
            # This ensures the lock mechanism compares correctly with PostgreSQL's NOW()
            game_start = bet.get('start_time_utc')  # Original UTC timestamp
            if game_start:
                # Parse if it's a string
                if isinstance(game_start, str):
                    # Remove timezone suffix if present and parse
                    start_str = game_start.replace('+00:00', '').replace('Z', '')
                    game_start_dt = datetime.fromisoformat(start_str.split('.')[0])
                    # Make it timezone-aware (UTC)
                    game_start_dt = game_start_dt.replace(tzinfo=timezone.utc)
                    game_start = game_start_dt.isoformat()
                elif hasattr(game_start, 'isoformat'):
                    # Already a datetime, just convert to ISO
                    game_start = game_start.isoformat()
            
            db_pick = {
                'date': today,
                'game_id': bet.get('game_id', ''),
                'home_team': home_team,
                'away_team': away_team,
                'game_start_time': game_start,
                'bet_type': bet['bet_type'].lower(),
                'pick': bet['pick'],
                'odds': bet['odds'],
                'predicted_value': bet.get('predicted_value', 0),
                'predicted_prob': bet['predicted_prob'],
                'confidence': bet['confidence'],
                'score': bet.get('score', 0),
                'home_projected': bet.get('home_projected'),
                'away_projected': bet.get('away_projected'),
                'reasoning': bet.get('reasoning', ''),
                'is_locked': False
            }
            db_picks.append(db_pick)
        
        # Save to database
        result = picks_db.save_picks_batch(db_picks)
        print(f"   ✅ Saved: {result['saved']}, Skipped (locked): {result['skipped']}, Errors: {result['errors']}")
        
        # Lock any games that have already started
        print(f"\n🔒 Locking picks for games that have started...")
        locked = picks_db.lock_started_games()
        print(f"   ✅ Locked {locked} picks")
        
        # Mark best bets in database
        if best_bets:
            print(f"\n💾 Marking {len(best_bets)} best bets...")
            updated = picks_db.mark_best_bets(today, best_bets)
            print(f"   ✅ Marked {updated} picks as best bets")
    
    # Print API call statistics
    if cache:
        print(f"\n💾 Cache Statistics:")
        print(f"   API calls made: {api_client.api_calls}")
        print(f"   (Cached data used for remaining queries)")
    
    print(f"\n{'=' * 80}")
    print("Analysis complete!")
    print(f"{'=' * 80}\n")


def create_sample_games() -> List[Dict]:
    """Create sample games for demonstration"""
    return [
        {
            'id': 'sample_1',
            'home_team': 'Duke',
            'away_team': 'North Carolina',
            'home_team_id': 1,
            'away_team_id': 2,
            'scheduled': '2024-01-15T19:00:00Z'
        },
        {
            'id': 'sample_2',
            'home_team': 'Kansas',
            'away_team': 'Kentucky',
            'home_team_id': 3,
            'away_team_id': 4,
            'scheduled': '2024-01-15T20:00:00Z'
        },
        {
            'id': 'sample_3',
            'home_team': 'Gonzaga',
            'away_team': 'UCLA',
            'home_team_id': 5,
            'away_team_id': 6,
            'scheduled': '2024-01-15T21:00:00Z'
        }
    ]


def create_default_odds() -> Dict:
    """Create default odds structure"""
    return {
        'spread': {
            'home_spread': -5.5,
            'away_spread': 5.5,
            'home_odds': -110,
            'away_odds': -110
        },
        'total': {
            'line': 145.5,
            'over_odds': -110,
            'under_odds': -110
        },
        'moneyline': {
            'home_odds': -200,
            'away_odds': 170
        }
    }


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nExiting...")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1)

