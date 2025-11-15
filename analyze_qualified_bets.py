#!/usr/bin/env python3
"""
Analyze ALL bets that qualify for best bets criteria (not just top 5)

This addresses the issue that odds lines change throughout the day,
so bet #6 at 2pm might become bet #3 at 6pm. We should track performance
of all bets that meet the best bets criteria.
"""

import os
import sys
from datetime import datetime
from dotenv import load_dotenv
from tabulate import tabulate
from typing import Dict, List
import argparse

from api_client import CollegeBasketballAPI
from model import BasketballPredictionModel
from best_bets import BestBetsSelector
import config


def analyze_qualified_bets(target_date: str):
    """
    Analyze all bets that meet best bets criteria for a given date
    
    Args:
        target_date: Date in YYYY-MM-DD format
    """
    load_dotenv()
    
    print("="*80)
    print(f"QUALIFIED BETS ANALYSIS - {target_date}")
    print("Analyzing ALL bets that meet best bets criteria")
    print("="*80)
    print()
    
    api_key = os.getenv('API_KEY')
    if not api_key:
        print("❌ Error: API_KEY not found in environment")
        return
    
    # Initialize
    api_client = CollegeBasketballAPI(api_key)
    model = BasketballPredictionModel(api_client)
    selector = BestBetsSelector()
    
    # Get completed games
    print(f"Fetching games for {target_date}...")
    completed_games = api_client.get_todays_games(date=target_date, d1_only=True, upcoming_only=False)
    completed_games = [g for g in completed_games if g.get('status') == 'final']
    print(f"Found {len(completed_games)} completed games\n")
    
    print("Generating predictions and filtering by best bets criteria...")
    
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
            print(f"Error processing {away_team} @ {home_team}: {e}")
            continue
    
    # Filter by best bets criteria
    min_confidence = config.MIN_CONFIDENCE_FOR_BEST_BETS
    qualified_bets = [
        bet for bet in all_bets
        if selector.meets_odds_criteria(bet['odds'])
        and bet['confidence'] >= min_confidence
    ]
    
    print(f"Found {len(qualified_bets)} bets that meet criteria:")
    print(f"  • Odds: -125 or better")
    print(f"  • Confidence: >= {min_confidence*100:.0f}%")
    print()
    
    # Calculate scores for each bet
    for bet in qualified_bets:
        bet['score'] = selector.calculate_bet_score(
            bet['predicted_prob'],
            bet['odds'],
            bet['confidence']
        )
    
    # Sort by score (highest first)
    qualified_bets.sort(key=lambda x: x['score'], reverse=True)
    
    # Check results
    wins = 0
    losses = 0
    
    for bet in qualified_bets:
        game = bet['game']
        home_score = game.get('home_score', 0)
        away_score = game.get('away_score', 0)
        
        if bet['bet_type'] == 'spread':
            # Parse the pick to get team and spread
            pick_parts = bet['pick'].split()
            pick_team = ' '.join(pick_parts[:-1])
            pick_spread = float(pick_parts[-1])
            
            home_team = game.get('home_team')
            away_team = game.get('away_team')
            
            # Determine result
            actual_margin = home_score - away_score
            
            if pick_team == home_team:
                # Betting on home team
                bet['result'] = actual_margin > -pick_spread
            else:
                # Betting on away team
                bet['result'] = actual_margin < -pick_spread
                
        else:  # total
            total = home_score + away_score
            # Extract line from pick (e.g., "Over 145.5" -> 145.5)
            pick_parts = bet['pick'].split()
            line = float(pick_parts[-1])
            
            if 'Over' in bet['pick']:
                bet['result'] = total > line
            else:
                bet['result'] = total < line
        
        if bet['result']:
            wins += 1
            bet['result_str'] = '✅ WON'
        else:
            losses += 1
            bet['result_str'] = '❌ LOST'
    
    # Display results
    print("="*80)
    print("QUALIFIED BETS RESULTS")
    print("="*80)
    print()
    
    table_data = []
    for i, bet in enumerate(qualified_bets, 1):
        game = bet['game']
        game_desc = f"{game['away_team']} @ {game['home_team']}"
        table_data.append([
            f"#{i}",
            game_desc[:30],
            bet['bet_type'].title(),
            bet['pick'][:20],
            bet['odds'],
            f"{bet['predicted_prob']:.1%}",
            f"{bet['confidence']:.1%}",
            f"{bet['score']:.3f}",
            bet['result_str']
        ])
    
    print(tabulate(table_data,
                   headers=['Rank', 'Game', 'Type', 'Pick', 'Odds', 'Value', 'Conf', 'Score', 'Result'],
                   tablefmt='grid'))
    
    # Summary
    print()
    print("="*80)
    print("SUMMARY")
    print("="*80)
    print()
    
    total_bets = wins + losses
    win_rate = wins / total_bets if total_bets > 0 else 0
    
    print(f"📊 QUALIFIED BETS:")
    print(f"   Record: {wins}-{losses}")
    print(f"   Win Rate: {win_rate:.1%}")
    
    if win_rate > 0.524:
        print(f"   ✅ PROFITABLE (need >52.4%)")
    else:
        print(f"   ❌ NOT PROFITABLE (need >52.4%)")
    
    # Breakdown by type
    spread_bets = [b for b in qualified_bets if b['bet_type'] == 'spread']
    total_bets_list = [b for b in qualified_bets if b['bet_type'] == 'total']
    
    spread_wins = sum(1 for b in spread_bets if b['result'])
    total_wins = sum(1 for b in total_bets_list if b['result'])
    
    print()
    print(f"📊 SPREAD BETS:")
    print(f"   Record: {spread_wins}-{len(spread_bets)-spread_wins}")
    if len(spread_bets) > 0:
        print(f"   Win Rate: {spread_wins/len(spread_bets):.1%}")
    
    print()
    print(f"📊 TOTAL BETS:")
    print(f"   Record: {total_wins}-{len(total_bets_list)-total_wins}")
    if len(total_bets_list) > 0:
        print(f"   Win Rate: {total_wins/len(total_bets_list):.1%}")
    
    # ROI calculation
    if total_bets > 0:
        # Assuming -110 odds: win 0.909 units, lose 1 unit
        profit = (wins * 0.909) - losses
        roi = (profit / total_bets) * 100
        print()
        print(f"💰 ROI (at -110 odds):")
        print(f"   Units: {profit:+.2f}u")
        print(f"   ROI: {roi:+.1f}%")
    
    print()
    print("="*80)
    print("✅ Analysis Complete!")
    print("="*80)


def main():
    parser = argparse.ArgumentParser(description='Analyze all qualified bets for a date')
    parser.add_argument('-d', '--date', type=str,
                       help='Date to analyze (YYYY-MM-DD format)')
    
    args = parser.parse_args()
    
    if args.date:
        target_date = args.date
    else:
        # Default to yesterday (since we're analyzing completed games)
        from datetime import datetime, timedelta, timezone
        now_utc = datetime.now(timezone.utc)
        now_est = now_utc - timedelta(hours=5)
        yesterday = now_est - timedelta(days=1)
        target_date = yesterday.strftime('%Y-%m-%d')
    
    analyze_qualified_bets(target_date)


if __name__ == '__main__':
    main()

