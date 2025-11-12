#!/usr/bin/env python3
"""
Demo script for NCAAM Basketball Betting Model
Runs without requiring an API key to demonstrate the model's capabilities
"""

from tabulate import tabulate
import random
from datetime import datetime


def generate_demo_team_stats():
    """Generate realistic demo team statistics"""
    return {
        'points_per_game': random.uniform(65, 85),
        'opponent_points_per_game': random.uniform(60, 80),
        'field_goal_percentage': random.uniform(0.40, 0.50),
        'three_point_percentage': random.uniform(0.30, 0.40),
        'free_throw_percentage': random.uniform(0.70, 0.80),
        'rebounds_per_game': random.uniform(30, 40),
        'assists_per_game': random.uniform(12, 18),
        'turnovers_per_game': random.uniform(10, 15),
        'steals_per_game': random.uniform(5, 10),
        'blocks_per_game': random.uniform(3, 6),
    }


def calculate_demo_metrics(stats):
    """Calculate metrics from stats (simplified version)"""
    ppg = stats['points_per_game']
    opp_ppg = stats['opponent_points_per_game']
    net_rating = ppg - opp_ppg
    return {
        'offensive_rating': ppg,
        'defensive_rating': opp_ppg,
        'net_rating': net_rating,
        'efficiency': stats['field_goal_percentage'] * 100
    }


def run_demo():
    """Run a demonstration of the model"""
    print("""
╔═══════════════════════════════════════════════════════════╗
║     NCAAM Basketball Betting Model - DEMO MODE            ║
║     Showing model capabilities with sample data           ║
╚═══════════════════════════════════════════════════════════╝
    """)
    
    print("This demo shows how the model works using simulated data.")
    print("For real predictions, set up your API key and run main.py\n")
    
    # Create sample games
    games = [
        {"home": "Duke", "away": "North Carolina"},
        {"home": "Kansas", "away": "Kentucky"},
        {"home": "Gonzaga", "away": "UCLA"},
        {"home": "Villanova", "away": "Georgetown"},
        {"home": "Michigan State", "away": "Ohio State"},
    ]
    
    print(f"{'=' * 80}")
    print(f"SAMPLE GAME ANALYSIS - {datetime.now().strftime('%A, %B %d, %Y')}")
    print(f"{'=' * 80}\n")
    
    all_predictions = []
    
    for game in games:
        home = game['home']
        away = game['away']
        
        # Generate stats
        home_stats = generate_demo_team_stats()
        away_stats = generate_demo_team_stats()
        
        # Calculate metrics
        home_metrics = calculate_demo_metrics(home_stats)
        away_metrics = calculate_demo_metrics(away_stats)
        
        # Simple prediction
        net_diff = home_metrics['net_rating'] - away_metrics['net_rating']
        home_advantage = 3.5
        predicted_spread = net_diff + home_advantage
        
        # Determine pick
        if predicted_spread > 5.5:
            spread_pick = f"{home} -5.5"
        elif predicted_spread < -5.5:
            spread_pick = f"{away} -5.5"
        else:
            spread_pick = f"{home} {predicted_spread:+.1f}"
        
        # Total prediction
        predicted_total = home_metrics['offensive_rating'] + away_metrics['offensive_rating']
        total_line = round(predicted_total / 0.5) * 0.5  # Round to nearest 0.5
        
        if predicted_total > total_line:
            total_pick = f"Over {total_line:.1f}"
        else:
            total_pick = f"Under {total_line:.1f}"
        
        confidence = random.uniform(0.70, 0.90)
        
        print(f"\n{away} @ {home}")
        print(f"{'-' * 80}")
        
        # Team metrics comparison
        metrics_table = [
            ["Offensive Rating", f"{home_metrics['offensive_rating']:.1f}", 
             f"{away_metrics['offensive_rating']:.1f}"],
            ["Defensive Rating", f"{home_metrics['defensive_rating']:.1f}",
             f"{away_metrics['defensive_rating']:.1f}"],
            ["Net Rating", f"{home_metrics['net_rating']:+.1f}",
             f"{away_metrics['net_rating']:+.1f}"],
            ["FG%", f"{home_stats['field_goal_percentage']:.1%}",
             f"{away_stats['field_goal_percentage']:.1%}"],
        ]
        
        print(tabulate(metrics_table,
                      headers=['Metric', home, away],
                      tablefmt='simple'))
        
        print(f"\n{'Predictions:'}")
        pred_table = [
            ["SPREAD", spread_pick, "-110", f"{confidence:.1%}"],
            ["TOTAL", total_pick, "-110", f"{confidence:.1%}"],
        ]
        
        print(tabulate(pred_table,
                      headers=['Bet Type', 'Pick', 'Odds', 'Confidence'],
                      tablefmt='simple'))
        
        all_predictions.append({
            'game': f"{away} @ {home}",
            'pick': spread_pick,
            'confidence': confidence,
            'win_prob': 0.5 + (confidence - 0.5) * 0.5
        })
    
    # Show Best Bets
    print(f"\n\n{'=' * 80}")
    print("TOP 5 BEST BETS (Based on Confidence)")
    print(f"{'=' * 80}\n")
    
    sorted_predictions = sorted(all_predictions, key=lambda x: x['confidence'], reverse=True)
    
    best_bets_table = []
    for i, pred in enumerate(sorted_predictions[:5], 1):
        best_bets_table.append([
            f"#{i}",
            pred['game'],
            "Spread",
            pred['pick'],
            "-110",
            f"{pred['win_prob']:.1%}",
            f"{pred['confidence']:.1%}"
        ])
    
    print(tabulate(best_bets_table,
                  headers=['Rank', 'Game', 'Type', 'Pick', 'Odds', 'Win Prob', 'Confidence'],
                  tablefmt='grid'))
    
    print(f"\n{'=' * 80}")
    print("Key Model Features Demonstrated:")
    print(f"{'=' * 80}")
    print("""
✓ Statistical Analysis - Compares offensive/defensive ratings
✓ Advanced Metrics - FG%, efficiency, net ratings
✓ Home Court Advantage - Factors in 3.5 point advantage
✓ Confidence Scoring - Model certainty for each prediction
✓ Best Bets Selection - Ranks by statistical likelihood
✓ Multiple Bet Types - Spread and total predictions

To use with real data:
1. Get API key from https://collegefootballdata.com/
2. Add to .env file: API_KEY=your_key_here
3. Run: python main.py
    """)
    
    print(f"{'=' * 80}\n")


if __name__ == "__main__":
    try:
        run_demo()
    except KeyboardInterrupt:
        print("\n\nDemo interrupted. Exiting...")
    except Exception as e:
        print(f"\nError running demo: {e}")

