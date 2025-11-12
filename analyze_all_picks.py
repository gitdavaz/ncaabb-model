#!/usr/bin/env python3
"""
Analyze ALL model picks for a given date
Shows every game's prediction and actual result
"""

import os
import sys
import argparse
from datetime import datetime
from dotenv import load_dotenv
from tabulate import tabulate

from api_client import CollegeBasketballAPI
from model import BasketballPredictionModel
from database import SupabaseCache


def main():
    """Main analysis function"""
    parser = argparse.ArgumentParser(
        description='Analyze All Model Picks for a Date',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                      # Analyze today's picks
  %(prog)s -d 2025-11-11        # Analyze picks from Nov 11, 2025
  %(prog)s -d 2025-11-11 -v     # Verbose mode with more details
        """
    )
    parser.add_argument(
        '-d', '--date',
        type=str,
        help='Date to analyze in YYYY-MM-DD format (default: today)'
    )
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Show verbose output with more details'
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
    
    print("=" * 100)
    print(f"ALL MODEL PICKS ANALYSIS - {target_date}")
    print("=" * 100)
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
    print("Analyzing model picks vs actual results...\n")
    
    # Analyze each game
    results = []
    spread_wins = 0
    spread_losses = 0
    total_wins = 0
    total_losses = 0
    
    for game in completed_games:
        home_team = game.get('home_team', 'Home')
        away_team = game.get('away_team', 'Away')
        home_team_id = game.get('home_team_id', 0)
        away_team_id = game.get('away_team_id', 0)
        home_score = game.get('home_score', 0)
        away_score = game.get('away_score', 0)
        
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
            
            # Get model predictions
            predicted_spread, spread_confidence = model.predict_spread(home_team_id, away_team_id, game)
            predicted_total, total_confidence = model.predict_total(home_team_id, away_team_id, game)
            
            # Actual results
            actual_spread = home_score - away_score
            actual_total = home_score + away_score
            
            # Market lines
            home_spread = odds_data['spread']['home_spread']
            away_spread = odds_data['spread']['away_spread']
            total_line = odds_data['total']['line']
            
            # Determine spread pick
            edge = predicted_spread + home_spread
            if edge > 0:
                spread_pick = f"{home_team} {home_spread:+.1f}"
                spread_bet_home = True
            else:
                spread_pick = f"{away_team} {away_spread:+.1f}"
                spread_bet_home = False
            
            # Check if spread bet won
            spread_won = (actual_spread > home_spread) if spread_bet_home else (actual_spread < home_spread)
            
            # Determine total pick
            if predicted_total > total_line:
                total_pick = f"Over {total_line}"
                total_bet_over = True
            else:
                total_pick = f"Under {total_line}"
                total_bet_over = False
            
            # Check if total bet won
            total_won = (actual_total > total_line) if total_bet_over else (actual_total < total_line)
            
            # Track wins/losses
            if spread_won:
                spread_wins += 1
            else:
                spread_losses += 1
            
            if total_won:
                total_wins += 1
            else:
                total_losses += 1
            
            results.append({
                'game': f"{away_team} @ {home_team}",
                'away_team': away_team,
                'home_team': home_team,
                'score': f"{away_score}-{home_score}",
                'actual_spread': actual_spread,
                'actual_total': actual_total,
                # Spread
                'predicted_spread': predicted_spread,
                'spread_pick': spread_pick,
                'spread_confidence': spread_confidence,
                'spread_won': spread_won,
                'spread_margin': (actual_spread - home_spread) if spread_bet_home else (home_spread - actual_spread),
                # Total
                'predicted_total': predicted_total,
                'total_pick': total_pick,
                'total_confidence': total_confidence,
                'total_won': total_won,
                'total_line': total_line,
                'total_margin': (actual_total - total_line) if total_bet_over else (total_line - actual_total),
            })
        
        except Exception as e:
            print(f"  ⚠️  Error analyzing {away_team} @ {home_team}: {e}")
            continue
    
    if not results:
        print("Could not analyze any games.")
        return
    
    # Sort by game name for consistent ordering
    results.sort(key=lambda x: x['game'])
    
    # Display results
    print("=" * 100)
    print("SPREAD PICKS")
    print("=" * 100)
    print()
    
    spread_table = []
    for r in results:
        status = "✅" if r['spread_won'] else "❌"
        
        # Show who won
        if r['actual_spread'] > 0:
            winner = f"{r['home_team']} by {r['actual_spread']}"
        elif r['actual_spread'] < 0:
            winner = f"{r['away_team']} by {abs(r['actual_spread'])}"
        else:
            winner = "Tie"
        
        spread_table.append([
            r['game'][:40],
            r['score'],
            winner[:25],
            r['spread_pick'][:25],
            f"{r['spread_confidence']:.0%}",
            status,
            f"{r['spread_margin']:+.1f}"
        ])
    
    print(tabulate(spread_table,
                   headers=['Game', 'Score', 'Winner', 'Model Pick', 'Conf', 'Result', 'Margin'],
                   tablefmt='grid'))
    
    print(f"\n{'=' * 100}")
    print("TOTAL PICKS")
    print("=" * 100)
    print()
    
    total_table = []
    for r in results:
        status = "✅" if r['total_won'] else "❌"
        
        total_table.append([
            r['game'][:40],
            r['score'],
            r['actual_total'],
            f"{r['total_line']:.1f}",
            r['total_pick'][:15],
            f"{r['total_confidence']:.0%}",
            status,
            f"{r['total_margin']:+.1f}"
        ])
    
    print(tabulate(total_table,
                   headers=['Game', 'Score', 'Total', 'Line', 'Model Pick', 'Conf', 'Result', 'Margin'],
                   tablefmt='grid'))
    
    # Calculate overall statistics
    total_bets = len(results) * 2  # Spread + Total for each game
    total_wins_all = spread_wins + total_wins
    total_losses_all = spread_losses + total_losses
    overall_pct = total_wins_all / total_bets * 100 if total_bets > 0 else 0
    spread_pct = spread_wins / len(results) * 100 if results else 0
    total_pct = total_wins / len(results) * 100 if results else 0
    
    print(f"\n{'=' * 100}")
    print("SUMMARY")
    print("=" * 100)
    print()
    
    print(f"📊 OVERALL PERFORMANCE:")
    print(f"   Total Bets: {total_wins_all}-{total_losses_all}")
    print(f"   Win Rate: {overall_pct:.1f}%")
    print(f"   {'✅ PROFITABLE' if overall_pct > 52.4 else '❌ NOT PROFITABLE'} (need >52.4%)")
    print()
    
    print(f"📊 SPREAD BETS:")
    print(f"   Record: {spread_wins}-{spread_losses}")
    print(f"   Win Rate: {spread_pct:.1f}%")
    print(f"   {'✅ PROFITABLE' if spread_pct > 52.4 else '❌ NOT PROFITABLE'}")
    print()
    
    print(f"📊 TOTAL BETS:")
    print(f"   Record: {total_wins}-{total_losses}")
    print(f"   Win Rate: {total_pct:.1f}%")
    print(f"   {'✅ PROFITABLE' if total_pct > 52.4 else '❌ NOT PROFITABLE'}")
    print()
    
    # ROI calculation
    if total_bets > 0:
        # Assuming -110 odds
        profit = total_wins_all * 0.909 - total_losses_all
        roi = (profit / total_bets) * 100
        
        print(f"💰 ROI (at -110 odds):")
        print(f"   Units: {profit:+.2f}u")
        print(f"   ROI: {roi:+.1f}%")
        print()
    
    # Show best and worst picks if verbose
    if args.verbose:
        print(f"{'=' * 100}")
        print("BEST PICKS (Largest Wins)")
        print("=" * 100)
        print()
        
        # Best spread picks
        best_spreads = sorted([r for r in results if r['spread_won']], 
                             key=lambda x: x['spread_margin'], reverse=True)[:5]
        
        if best_spreads:
            print("🏆 TOP 5 SPREAD PICKS:")
            for i, r in enumerate(best_spreads, 1):
                print(f"{i}. {r['game']}")
                print(f"   Pick: {r['spread_pick']} | Won by: {r['spread_margin']:.1f} pts")
                print(f"   Score: {r['score']}")
                print()
        
        # Best total picks
        best_totals = sorted([r for r in results if r['total_won']], 
                            key=lambda x: x['total_margin'], reverse=True)[:5]
        
        if best_totals:
            print("🏆 TOP 5 TOTAL PICKS:")
            for i, r in enumerate(best_totals, 1):
                print(f"{i}. {r['game']}")
                print(f"   Pick: {r['total_pick']} | Won by: {r['total_margin']:.1f} pts")
                print(f"   Total: {r['actual_total']} (Line: {r['total_line']:.1f})")
                print()
        
        print(f"{'=' * 100}")
        print("WORST PICKS (Biggest Losses)")
        print("=" * 100)
        print()
        
        # Worst spread picks
        worst_spreads = sorted([r for r in results if not r['spread_won']], 
                              key=lambda x: x['spread_margin'])[:5]
        
        if worst_spreads:
            print("❌ TOP 5 SPREAD LOSSES:")
            for i, r in enumerate(worst_spreads, 1):
                print(f"{i}. {r['game']}")
                print(f"   Pick: {r['spread_pick']} | Lost by: {abs(r['spread_margin']):.1f} pts")
                print(f"   Score: {r['score']}")
                print()
        
        # Worst total picks
        worst_totals = sorted([r for r in results if not r['total_won']], 
                             key=lambda x: x['total_margin'])[:5]
        
        if worst_totals:
            print("❌ TOP 5 TOTAL LOSSES:")
            for i, r in enumerate(worst_totals, 1):
                print(f"{i}. {r['game']}")
                print(f"   Pick: {r['total_pick']} | Lost by: {abs(r['total_margin']):.1f} pts")
                print(f"   Total: {r['actual_total']} (Line: {r['total_line']:.1f})")
                print()
    
    print(f"{'=' * 100}")
    print("✅ Analysis Complete!")
    print(f"{'=' * 100}")


if __name__ == '__main__':
    main()

