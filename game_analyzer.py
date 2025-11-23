#!/usr/bin/env python3
"""
Interactive Game Analyzer - Deep dive into single game predictions
"""

import os
import sys
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv
from tabulate import tabulate
from typing import Dict, List, Optional

from api_client import CollegeBasketballAPI
from model import BasketballPredictionModel
from best_bets import BestBetsSelector


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
║        NCAAM Basketball Game Analyzer                     ║
║        Deep Dive Analysis & Model Breakdown               ║
╚═══════════════════════════════════════════════════════════╝
    """
    print(banner)


def get_date_input() -> str:
    """Get date input from user"""
    print("\n" + "=" * 60)
    print("STEP 1: Select Date")
    print("=" * 60)
    
    while True:
        date_input = input("\nEnter date (YYYY-MM-DD) or press Enter for today (EST): ").strip()
        
        if not date_input:
            # Get current date in EST (UTC-5)
            now_utc = datetime.now(timezone.utc)
            now_est = now_utc - timedelta(hours=5)
            return now_est.strftime('%Y-%m-%d')
        
        try:
            datetime.strptime(date_input, '%Y-%m-%d')
            return date_input
        except ValueError:
            print("❌ Invalid date format. Please use YYYY-MM-DD (e.g., 2025-11-08)")


def select_game(games: List[Dict]) -> Optional[Dict]:
    """Let user select a game from list"""
    if not games:
        print("\n❌ No games found for this date.")
        return None
    
    print("\n" + "=" * 60)
    print("STEP 2: Select Game")
    print("=" * 60)
    print(f"\nFound {len(games)} games:\n")
    
    # Display games with numbers
    for i, game in enumerate(games, 1):
        away = game.get('away_team', 'Away')
        home = game.get('home_team', 'Home')
        start = game.get('start_date', '')
        status = game.get('status', '')
        
        # Parse start time and convert to EST
        time_str = ""
        if start:
            try:
                game_time_est = parse_game_time_to_est(start)
                if game_time_est.year != 2099:  # Valid parse
                    time_str = game_time_est.strftime('%I:%M %p EST')
            except:
                pass
        
        status_str = f" [{status}]" if status else ""
        time_str = f" @ {time_str}" if time_str else ""
        
        print(f"  {i}. {away} @ {home}{time_str}{status_str}")
    
    print(f"\n  0. Exit")
    
    while True:
        try:
            choice = input(f"\nSelect game (1-{len(games)}) or 0 to exit: ").strip()
            choice_num = int(choice)
            
            if choice_num == 0:
                return None
            
            if 1 <= choice_num <= len(games):
                return games[choice_num - 1]
            
            print(f"❌ Please enter a number between 0 and {len(games)}")
        except ValueError:
            print("❌ Please enter a valid number")


def format_percentage(value: float) -> str:
    """Format a decimal as percentage"""
    return f"{value * 100:.1f}%"


def print_team_stats(team_name: str, stats: Dict, metrics: Dict, recent_form: Dict):
    """Print detailed team statistics"""
    print(f"\n{'─' * 60}")
    print(f"  {team_name}")
    print(f"{'─' * 60}")
    
    # Basic stats
    print("\n📊 Season Statistics:")
    stats_table = [
        ["Points Per Game", f"{stats.get('points_per_game', 0):.1f}"],
        ["Opp Points Per Game", f"{stats.get('opponent_points_per_game', 0):.1f}"],
        ["Field Goal %", format_percentage(stats.get('field_goal_percentage', 0))],
        ["3-Point %", format_percentage(stats.get('three_point_percentage', 0))],
        ["Free Throw %", format_percentage(stats.get('free_throw_percentage', 0))],
        ["Rebounds Per Game", f"{stats.get('rebounds_per_game', 0):.1f}"],
        ["Assists Per Game", f"{stats.get('assists_per_game', 0):.1f}"],
        ["Turnovers Per Game", f"{stats.get('turnovers_per_game', 0):.1f}"],
    ]
    print(tabulate(stats_table, tablefmt='simple'))
    
    # Advanced metrics
    print("\n📈 Advanced Metrics:")
    metrics_table = [
        ["Net Rating", f"{metrics.get('net_rating', 0):+.1f}"],
        ["Offensive Rating", f"{metrics.get('offensive_rating', 0):.1f}"],
        ["Defensive Rating", f"{metrics.get('defensive_rating', 0):.1f}"],
        ["Shooting Efficiency", format_percentage(metrics.get('shooting_efficiency', 0))],
        ["Assist/Turnover Ratio", f"{metrics.get('assist_to_turnover', 0):.2f}"],
        ["Defensive Intensity", f"{metrics.get('defensive_intensity', 0):.1f}"],
        ["Pace", f"{metrics.get('pace', 0):.1f}"],
    ]
    print(tabulate(metrics_table, tablefmt='simple'))
    
    # Recent form
    print("\n🔥 Recent Form:")
    form_table = [
        ["Win Rate", format_percentage(recent_form.get('win_rate', 0))],
        ["Avg Margin", f"{recent_form.get('avg_margin', 0):+.1f}"],
        ["Scoring Trend", f"{recent_form.get('scoring_trend', 0):.1f}"],
        ["Consistency", format_percentage(recent_form.get('consistency', 0))],
    ]
    print(tabulate(form_table, tablefmt='simple'))


def print_matchup_analysis(home_team: str, away_team: str, 
                           home_metrics: Dict, away_metrics: Dict):
    """Print head-to-head matchup comparison"""
    print("\n" + "=" * 60)
    print("MATCHUP COMPARISON")
    print("=" * 60)
    
    comparison = [
        ["Metric", away_team, home_team, "Advantage"],
        ["─" * 20, "─" * 15, "─" * 15, "─" * 15],
        ["Net Rating", 
         f"{away_metrics.get('net_rating', 0):+.1f}",
         f"{home_metrics.get('net_rating', 0):+.1f}",
         home_team if home_metrics.get('net_rating', 0) > away_metrics.get('net_rating', 0) else away_team],
        ["Offensive Rating",
         f"{away_metrics.get('offensive_rating', 0):.1f}",
         f"{home_metrics.get('offensive_rating', 0):.1f}",
         home_team if home_metrics.get('offensive_rating', 0) > away_metrics.get('offensive_rating', 0) else away_team],
        ["Defensive Rating",
         f"{away_metrics.get('defensive_rating', 0):.1f}",
         f"{home_metrics.get('defensive_rating', 0):.1f}",
         away_team if away_metrics.get('defensive_rating', 0) < home_metrics.get('defensive_rating', 0) else home_team],
        ["Pace",
         f"{away_metrics.get('pace', 0):.1f}",
         f"{home_metrics.get('pace', 0):.1f}",
         home_team if home_metrics.get('pace', 0) > away_metrics.get('pace', 0) else away_team],
        ["Shooting Efficiency",
         format_percentage(away_metrics.get('shooting_efficiency', 0)),
         format_percentage(home_metrics.get('shooting_efficiency', 0)),
         home_team if home_metrics.get('shooting_efficiency', 0) > away_metrics.get('shooting_efficiency', 0) else away_team],
    ]
    
    print(tabulate(comparison, headers='firstrow', tablefmt='grid'))


def print_prediction_breakdown(predicted_spread: float, spread_confidence: float,
                               predicted_total: float, total_confidence: float,
                               home_team: str, away_team: str):
    """Print model prediction breakdown"""
    print("\n" + "=" * 60)
    print("MODEL PREDICTIONS")
    print("=" * 60)
    
    # Calculate projected scores
    # predicted_spread = home_score - away_score
    # predicted_total = home_score + away_score
    # Therefore: home_score = (total + spread) / 2
    #           away_score = (total - spread) / 2
    home_projected = (predicted_total + predicted_spread) / 2
    away_projected = (predicted_total - predicted_spread) / 2
    
    # Spread prediction
    print("\n🎯 SPREAD PREDICTION:")
    print(f"   Projected Score: {home_team} {home_projected:.1f}, {away_team} {away_projected:.1f}")
    
    if predicted_spread > 0:
        print(f"   {home_team} by {predicted_spread:.1f} points")
    elif predicted_spread < 0:
        print(f"   {away_team} by {abs(predicted_spread):.1f} points")
    else:
        print(f"   Pick'em (Even game)")
    
    print(f"   Confidence: {format_percentage(spread_confidence)}")
    
    # Confidence breakdown
    if spread_confidence >= 0.75:
        confidence_level = "Very High"
        emoji = "🔥"
    elif spread_confidence >= 0.65:
        confidence_level = "High"
        emoji = "✅"
    elif spread_confidence >= 0.55:
        confidence_level = "Moderate"
        emoji = "⚠️"
    else:
        confidence_level = "Low"
        emoji = "❌"
    
    print(f"   Confidence Level: {emoji} {confidence_level}")
    
    # Total prediction
    print(f"\n📊 TOTAL PREDICTION:")
    print(f"   Predicted Total: {predicted_total:.1f} points")
    print(f"   Confidence: {format_percentage(total_confidence)}")
    
    if total_confidence >= 0.70:
        confidence_level = "High"
        emoji = "✅"
    elif total_confidence >= 0.55:
        confidence_level = "Moderate"
        emoji = "⚠️"
    else:
        confidence_level = "Low"
        emoji = "❌"
    
    print(f"   Confidence Level: {emoji} {confidence_level}")


def print_betting_analysis(game: Dict, predicted_spread: float, spread_confidence: float,
                           predicted_total: float, total_confidence: float,
                           odds_data: Dict, selector: BestBetsSelector):
    """Print betting lines and recommendations"""
    print("\n" + "=" * 60)
    print("BETTING ANALYSIS")
    print("=" * 60)
    
    home_team = game.get('home_team', 'Home')
    away_team = game.get('away_team', 'Away')
    
    # Market lines
    print("\n💰 Current Market Lines:")
    spread_data = odds_data.get('spread', {})
    total_data = odds_data.get('total', {})
    
    if spread_data:
        home_spread = spread_data.get('home_spread', 0)
        away_spread = spread_data.get('away_spread', 0)
        home_odds = spread_data.get('home_odds', -110)
        away_odds = spread_data.get('away_odds', -110)
        
        print(f"   Spread: {home_team} {home_spread:+.1f} ({home_odds:+d})")
        print(f"           {away_team} {away_spread:+.1f} ({away_odds:+d})")
    
    if total_data:
        total_line = total_data.get('line', 0)
        over_odds = total_data.get('over_odds', -110)
        under_odds = total_data.get('under_odds', -110)
        
        print(f"   Total:  Over {total_line:.1f} ({over_odds:+d})")
        print(f"           Under {total_line:.1f} ({under_odds:+d})")
    
    # Create bets for analysis
    spread_bets = selector.create_bet_from_prediction(
        game, 'spread', predicted_spread, spread_confidence, odds_data
    )
    total_bets = selector.create_bet_from_prediction(
        game, 'total', predicted_total, total_confidence, odds_data
    )
    
    # Best bet recommendation
    print("\n⭐ BEST BET RECOMMENDATIONS:")
    
    all_bets = spread_bets + total_bets
    if all_bets:
        # Sort by score
        sorted_bets = sorted(all_bets, key=lambda x: x.get('predicted_prob', 0) * x.get('confidence', 0), reverse=True)
        
        for i, bet in enumerate(sorted_bets[:3], 1):
            odds_str = f"{bet['odds']:+d}" if bet['odds'] < 0 else f"+{bet['odds']}"
            
            print(f"\n   #{i} - {bet['bet_type']}: {bet['pick']}")
            print(f"       Odds: {odds_str}")
            print(f"       Value Rating: {format_percentage(bet['predicted_prob'])}")
            print(f"       Model Confidence: {format_percentage(bet['confidence'])}")
            print(f"       Reasoning: {bet['reasoning']}")
            
            # Calculate edge
            if 'edge' in bet:
                print(f"       Edge: {bet.get('edge', 0):.1f} points")


def analyze_game(game: Dict, api_client: CollegeBasketballAPI, 
                model: BasketballPredictionModel, selector: BestBetsSelector):
    """Perform detailed analysis on a single game"""
    home_team = game.get('home_team', 'Home')
    away_team = game.get('away_team', 'Away')
    home_team_id = game.get('home_team_id', 0)
    away_team_id = game.get('away_team_id', 0)
    
    print("\n" + "=" * 60)
    print(f"ANALYZING: {away_team} @ {home_team}")
    print("=" * 60)
    
    # Get data
    print("\n⏳ Fetching team statistics...")
    home_stats = api_client.get_team_stats(home_team_id)
    away_stats = api_client.get_team_stats(away_team_id)
    
    print("⏳ Fetching recent games...")
    home_recent = api_client.get_recent_games(home_team_id, limit=10)
    away_recent = api_client.get_recent_games(away_team_id, limit=10)
    
    print("⏳ Calculating advanced metrics...")
    home_metrics = model.calculate_team_metrics(home_stats)
    away_metrics = model.calculate_team_metrics(away_stats)
    
    print("⏳ Analyzing recent form...")
    home_form = model.analyze_recent_form(home_recent, home_team_id)
    away_form = model.analyze_recent_form(away_recent, away_team_id)
    
    print("⏳ Generating predictions...")
    predicted_spread, spread_confidence = model.predict_spread(home_team_id, away_team_id, game)
    predicted_total, total_confidence = model.predict_total(home_team_id, away_team_id, game)
    
    print("⏳ Fetching odds data...")
    game_date = game.get('start_date', '')
    if isinstance(game_date, str):
        game_date = game_date.split('T')[0]
    else:
        game_date = datetime.now().strftime('%Y-%m-%d')
    
    odds_data = api_client.get_odds_for_team_date(home_team, game_date)
    # Treat 0 spreads as missing data (CFBD returns 0 when no lines available)
    if not odds_data or 'spread' not in odds_data or odds_data.get('spread', {}).get('home_spread') == 0:
        # Create default odds
        odds_data = {
            'spread': {
                'home_spread': -predicted_spread,
                'away_spread': predicted_spread,
                'home_odds': -110,
                'away_odds': -110,
            },
            'total': {
                'line': predicted_total,
                'over_odds': -110,
                'under_odds': -110,
            }
        }
    
    # Print analysis
    print("\n" + "=" * 60)
    print("TEAM STATISTICS & METRICS")
    print("=" * 60)
    
    print_team_stats(away_team, away_stats, away_metrics, away_form)
    print_team_stats(home_team, home_stats, home_metrics, home_form)
    
    print_matchup_analysis(home_team, away_team, home_metrics, away_metrics)
    
    print_prediction_breakdown(predicted_spread, spread_confidence,
                              predicted_total, total_confidence,
                              home_team, away_team)
    
    print_betting_analysis(game, predicted_spread, spread_confidence,
                          predicted_total, total_confidence,
                          odds_data, selector)
    
    print("\n" + "=" * 60)
    print("ANALYSIS COMPLETE")
    print("=" * 60)


def main():
    """Main interactive application"""
    load_dotenv()
    
    print_banner()
    
    # Get API key
    api_key = os.getenv('API_KEY')
    if not api_key:
        print("\n⚠️  Warning: API_KEY not found in environment variables.")
        print("   Create a .env file with your API key: API_KEY=your_key_here\n")
        return
    
    # Initialize caching (if enabled)
    cache = None
    use_cache = os.getenv('USE_CACHE', 'true').lower() == 'true'
    if use_cache:
        supabase_url = os.getenv('SUPABASE_URL')
        supabase_key = os.getenv('SUPABASE_SERVICE_KEY')
        
        if supabase_url and supabase_key:
            try:
                from database import SupabaseCache
                cache = SupabaseCache(supabase_url, supabase_key)
            except:
                pass  # Silently continue without cache
    
    # Initialize components
    print("\n⏳ Initializing model...")
    api_client = CollegeBasketballAPI(api_key, cache=cache)
    model = BasketballPredictionModel(api_client)
    selector = BestBetsSelector(max_odds=-125)
    
    while True:
        # Get date
        target_date = get_date_input()
        
        # Ask if user wants upcoming only or all games
        print("\n" + "=" * 60)
        print("Game Filter")
        print("=" * 60)
        print("\n1. Upcoming games only (not yet played)")
        print("2. All games (upcoming + completed)")
        
        filter_choice = input("\nSelect filter (1 or 2, default: 1): ").strip()
        upcoming_only = filter_choice != '2'
        
        # Get games for that date
        print(f"\n⏳ Fetching {'upcoming ' if upcoming_only else ''}games for {target_date}...")
        games = api_client.get_todays_games(date=target_date, d1_only=True, upcoming_only=upcoming_only)
        
        if not games:
            print(f"\n❌ No games found for {target_date}")
            
            retry = input("\nTry another date? (y/n): ").strip().lower()
            if retry != 'y':
                break
            continue
        
        # Let user select game
        selected_game = select_game(games)
        
        if not selected_game:
            print("\n👋 Exiting...")
            break
        
        # Analyze the selected game
        try:
            analyze_game(selected_game, api_client, model, selector)
        except Exception as e:
            print(f"\n❌ Error analyzing game: {e}")
            import traceback
            traceback.print_exc()
        
        # Ask to analyze another game
        print("\n")
        another = input("Analyze another game? (y/n): ").strip().lower()
        if another != 'y':
            print("\n👋 Thanks for using the Game Analyzer!")
            break


if __name__ == '__main__':
    main()

