"""
Analyze model predictions vs actual game results
"""

import os
import sys
import argparse
from datetime import datetime
from dotenv import load_dotenv
from api_client import CollegeBasketballAPI
from model import BasketballPredictionModel
from typing import Dict, List, Tuple
from tabulate import tabulate


def analyze_game_result(game: Dict, predicted_spread: float, predicted_total: float, 
                        spread_conf: float, total_conf: float) -> Dict:
    """Analyze a single game's results vs predictions"""
    home_score = game.get('home_score', 0) or 0
    away_score = game.get('away_score', 0) or 0
    
    # Actual results
    actual_margin = home_score - away_score  # Positive = home won
    actual_total = home_score + away_score
    
    # Prediction errors
    spread_error = abs(predicted_spread - actual_margin)
    total_error = abs(predicted_total - actual_total)
    
    # Spread accuracy (within 5 points is good, within 10 is okay)
    spread_accuracy = "Excellent" if spread_error <= 5 else "Good" if spread_error <= 10 else "Poor"
    total_accuracy = "Excellent" if total_error <= 5 else "Good" if total_error <= 10 else "Poor"
    
    return {
        'game': f"{game.get('away_team')} @ {game.get('home_team')}",
        'home_team': game.get('home_team'),
        'away_team': game.get('away_team'),
        'actual_margin': actual_margin,
        'predicted_spread': predicted_spread,
        'spread_error': spread_error,
        'spread_accuracy': spread_accuracy,
        'spread_confidence': spread_conf,
        'actual_total': actual_total,
        'predicted_total': predicted_total,
        'total_error': total_error,
        'total_accuracy': total_accuracy,
        'total_confidence': total_conf,
        'home_score': home_score,
        'away_score': away_score,
    }


def main():
    """Main analysis function"""
    # Parse command-line arguments
    parser = argparse.ArgumentParser(
        description='Analyze NCAAM Basketball Model Performance',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                      # Analyze today's completed games
  %(prog)s --date 2025-11-07    # Analyze games from Nov 7, 2025
  %(prog)s -d 2025-11-06        # Short form
        """
    )
    parser.add_argument(
        '-d', '--date',
        type=str,
        help='Date to analyze in YYYY-MM-DD format (default: today)'
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
            # Validate date format
            datetime.strptime(args.date, '%Y-%m-%d')
            target_date = args.date
            print("=" * 80)
            print(f"MODEL PERFORMANCE ANALYSIS - {target_date}")
            print("=" * 80)
            print()
        except ValueError:
            print(f"❌ Error: Invalid date format '{args.date}'")
            print("   Please use YYYY-MM-DD format (e.g., 2025-11-08)")
            sys.exit(1)
    else:
        target_date = datetime.now().strftime('%Y-%m-%d')
        print("=" * 80)
        print("MODEL PERFORMANCE ANALYSIS - Today's Games")
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
                from database import SupabaseCache
                cache = SupabaseCache(supabase_url, supabase_key)
            except:
                pass  # Silently continue without cache
    
    # Initialize API and model
    api_client = CollegeBasketballAPI(api_key, cache=cache)
    model = BasketballPredictionModel(api_client)
    
    # Get completed games for target date
    print(f"Fetching completed games for {target_date}...\n")
    
    # Get ALL games (including completed ones)
    all_games = api_client.get_todays_games(date=target_date, d1_only=True, upcoming_only=False)
    
    # Filter for completed games with scores
    completed_games = [
        g for g in all_games 
        if g.get('home_score') is not None and g.get('away_score') is not None
        and g.get('home_score', 0) > 0  # Ensure game actually happened
    ]
    
    if not completed_games:
        print(f"No completed games found for {target_date}.")
        print("This might be because:")
        print("  - Games haven't finished yet")
        print("  - The date might be incorrect")
        print("  - There were no D1 games on this date")
        print(f"  - The date might be outside the season")
        return
    
    print(f"Found {len(completed_games)} completed D1 games.\n")
    print("Analyzing predictions vs actual results...\n")
    
    # Analyze each game
    results = []
    for game in completed_games:
        home_team_id = game.get('home_team_id', 0)
        away_team_id = game.get('away_team_id', 0)
        
        if not home_team_id or not away_team_id:
            continue
        
        try:
            # Get predictions
            predicted_spread, spread_conf = model.predict_spread(home_team_id, away_team_id, game)
            predicted_total, total_conf = model.predict_total(home_team_id, away_team_id, game)
            
            # Analyze
            result = analyze_game_result(game, predicted_spread, predicted_total, 
                                        spread_conf, total_conf)
            results.append(result)
        except Exception as e:
            print(f"  Error analyzing {game.get('away_team')} @ {game.get('home_team')}: {e}")
    
    if not results:
        print("Could not analyze any games.")
        return
    
    # Print detailed results
    print("=" * 80)
    print("SPREAD PREDICTIONS")
    print("=" * 80)
    print()
    
    spread_table = []
    for r in results:
        winner = r['home_team'] if r['actual_margin'] > 0 else r['away_team']
        margin_str = f"{abs(r['actual_margin']):.0f}"
        
        spread_table.append([
            r['game'][:40],
            f"{winner} by {margin_str}",
            f"{r['predicted_spread']:+.1f}",
            f"{r['actual_margin']:+.1f}",
            f"{r['spread_error']:.1f}",
            r['spread_accuracy'],
            f"{r['spread_confidence']:.1%}"
        ])
    
    print(tabulate(spread_table, 
                   headers=['Game', 'Actual Result', 'Predicted', 'Actual', 'Error', 'Grade', 'Confidence'],
                   tablefmt='simple'))
    
    print("\n" + "=" * 80)
    print("TOTAL PREDICTIONS")
    print("=" * 80)
    print()
    
    total_table = []
    for r in results:
        total_table.append([
            r['game'][:40],
            f"{r['home_score']}-{r['away_score']}",
            f"{r['actual_total']:.0f}",
            f"{r['predicted_total']:.1f}",
            f"{r['total_error']:.1f}",
            r['total_accuracy'],
            f"{r['total_confidence']:.1%}"
        ])
    
    print(tabulate(total_table,
                   headers=['Game', 'Score', 'Actual', 'Predicted', 'Error', 'Grade', 'Confidence'],
                   tablefmt='simple'))
    
    # Calculate overall statistics
    print("\n" + "=" * 80)
    print("OVERALL MODEL PERFORMANCE")
    print("=" * 80)
    print()
    
    avg_spread_error = sum(r['spread_error'] for r in results) / len(results)
    avg_total_error = sum(r['total_error'] for r in results) / len(results)
    
    spread_excellent = sum(1 for r in results if r['spread_accuracy'] == 'Excellent')
    spread_good = sum(1 for r in results if r['spread_accuracy'] == 'Good')
    spread_poor = sum(1 for r in results if r['spread_accuracy'] == 'Poor')
    
    total_excellent = sum(1 for r in results if r['total_accuracy'] == 'Excellent')
    total_good = sum(1 for r in results if r['total_accuracy'] == 'Good')
    total_poor = sum(1 for r in results if r['total_accuracy'] == 'Poor')
    
    avg_spread_conf = sum(r['spread_confidence'] for r in results) / len(results)
    avg_total_conf = sum(r['total_confidence'] for r in results) / len(results)
    
    print(f"Games Analyzed: {len(results)}")
    print()
    
    print("SPREAD PREDICTIONS:")
    print(f"  Average Error: {avg_spread_error:.1f} points")
    print(f"  Average Confidence: {avg_spread_conf:.1%}")
    print(f"  Excellent (≤5 pts): {spread_excellent} ({spread_excellent/len(results)*100:.1f}%)")
    print(f"  Good (6-10 pts): {spread_good} ({spread_good/len(results)*100:.1f}%)")
    print(f"  Poor (>10 pts): {spread_poor} ({spread_poor/len(results)*100:.1f}%)")
    print()
    
    print("TOTAL PREDICTIONS:")
    print(f"  Average Error: {avg_total_error:.1f} points")
    print(f"  Average Confidence: {avg_total_conf:.1%}")
    print(f"  Excellent (≤5 pts): {total_excellent} ({total_excellent/len(results)*100:.1f}%)")
    print(f"  Good (6-10 pts): {total_good} ({total_good/len(results)*100:.1f}%)")
    print(f"  Poor (>10 pts): {total_poor} ({total_poor/len(results)*100:.1f}%)")
    print()
    
    # Identify patterns
    print("=" * 80)
    print("INSIGHTS & PATTERNS")
    print("=" * 80)
    print()
    
    # High confidence games - were they accurate?
    high_conf_spread = [r for r in results if r['spread_confidence'] > 0.75]
    if high_conf_spread:
        high_conf_spread_avg_error = sum(r['spread_error'] for r in high_conf_spread) / len(high_conf_spread)
        print(f"High Confidence Spread Predictions (>75%):")
        print(f"  Count: {len(high_conf_spread)}")
        print(f"  Average Error: {high_conf_spread_avg_error:.1f} points")
        print()
    
    high_conf_total = [r for r in results if r['total_confidence'] > 0.75]
    if high_conf_total:
        high_conf_total_avg_error = sum(r['total_error'] for r in high_conf_total) / len(high_conf_total)
        print(f"High Confidence Total Predictions (>75%):")
        print(f"  Count: {len(high_conf_total)}")
        print(f"  Average Error: {high_conf_total_avg_error:.1f} points")
        print()
    
    # Low confidence games - were they less accurate?
    low_conf_spread = [r for r in results if r['spread_confidence'] < 0.60]
    if low_conf_spread:
        low_conf_spread_avg_error = sum(r['spread_error'] for r in low_conf_spread) / len(low_conf_spread)
        print(f"Low Confidence Spread Predictions (<60%):")
        print(f"  Count: {len(low_conf_spread)}")
        print(f"  Average Error: {low_conf_spread_avg_error:.1f} points")
        print()
    
    low_conf_total = [r for r in results if r['total_confidence'] < 0.60]
    if low_conf_total:
        low_conf_total_avg_error = sum(r['total_error'] for r in low_conf_total) / len(low_conf_total)
        print(f"Low Confidence Total Predictions (<60%):")
        print(f"  Count: {len(low_conf_total)}")
        print(f"  Average Error: {low_conf_total_avg_error:.1f} points")
        print()
    
    # Biggest misses
    biggest_spread_miss = max(results, key=lambda r: r['spread_error'])
    biggest_total_miss = max(results, key=lambda r: r['total_error'])
    
    print("Biggest Spread Miss:")
    print(f"  Game: {biggest_spread_miss['game']}")
    print(f"  Predicted: {biggest_spread_miss['predicted_spread']:+.1f}, Actual: {biggest_spread_miss['actual_margin']:+.1f}")
    print(f"  Error: {biggest_spread_miss['spread_error']:.1f} points")
    print(f"  Confidence: {biggest_spread_miss['spread_confidence']:.1%}")
    print()
    
    print("Biggest Total Miss:")
    print(f"  Game: {biggest_total_miss['game']}")
    print(f"  Predicted: {biggest_total_miss['predicted_total']:.1f}, Actual: {biggest_total_miss['actual_total']:.0f}")
    print(f"  Error: {biggest_total_miss['total_error']:.1f} points")
    print(f"  Confidence: {biggest_total_miss['total_confidence']:.1%}")
    print()
    
    # Best predictions
    best_spread = min(results, key=lambda r: r['spread_error'])
    best_total = min(results, key=lambda r: r['total_error'])
    
    print("Best Spread Prediction:")
    print(f"  Game: {best_spread['game']}")
    print(f"  Predicted: {best_spread['predicted_spread']:+.1f}, Actual: {best_spread['actual_margin']:+.1f}")
    print(f"  Error: {best_spread['spread_error']:.1f} points")
    print()
    
    print("Best Total Prediction:")
    print(f"  Game: {best_total['game']}")
    print(f"  Predicted: {best_total['predicted_total']:.1f}, Actual: {best_total['actual_total']:.0f}")
    print(f"  Error: {best_total['total_error']:.1f} points")
    print()
    
    print("=" * 80)
    print("Analysis Complete!")
    print("=" * 80)


if __name__ == '__main__':
    main()

