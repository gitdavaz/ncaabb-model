#!/usr/bin/env python3
"""
Analyze saved best bets from JSON files

This uses the ACTUAL picks that were generated on game day,
not re-generated predictions with different odds.
"""

import os
import sys
import argparse
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
from tabulate import tabulate
from typing import Dict, List

from api_client import CollegeBasketballAPI
from save_best_bets import load_best_bets


def analyze_saved_bets(target_date: str):
    """
    Analyze saved best bets for a given date
    
    Args:
        target_date: Date in YYYY-MM-DD format
    """
    load_dotenv()
    
    print("="*80)
    print(f"SAVED BEST BETS ANALYSIS - {target_date}")
    print("Using actual picks from game day")
    print("="*80)
    print()
    
    # Load saved bets
    saved_data = load_best_bets(target_date)
    
    if not saved_data:
        print(f"❌ No saved best bets found for {target_date}")
        print(f"   Looking for: best_bets_history/{target_date}.json")
        print()
        print("💡 TIP: Run main.py for a date to save best bets automatically")
        return
    
    best_bets = saved_data['best_bets']
    saved_time = saved_data.get('timestamp', 'Unknown')
    
    print(f"📁 Loaded {len(best_bets)} bets")
    print(f"🕐 Saved at: {saved_time}")
    print()
    
    # Get API client to fetch actual results
    api_key = os.getenv('API_KEY')
    if not api_key:
        print("❌ Error: API_KEY not found in environment")
        return
    
    api_client = CollegeBasketballAPI(api_key)
    
    print("⏳ Fetching game results...")
    games = api_client.get_todays_games(date=target_date, d1_only=True, upcoming_only=False)
    completed_games = [g for g in games if g.get('status') == 'final']
    print(f"   Found {len(completed_games)} completed games")
    print()
    
    # Create game lookup by teams
    game_lookup = {}
    for game in completed_games:
        key = f"{game.get('away_team')}@{game.get('home_team')}"
        game_lookup[key] = game
    
    # Analyze each bet
    wins = 0
    losses = 0
    
    for bet in best_bets:
        game_desc = bet['game_description']
        parts = game_desc.split(' @ ')
        if len(parts) != 2:
            print(f"⚠️  Warning: Could not parse game: {game_desc}")
            continue
        
        away_team = parts[0]
        home_team = parts[1]
        key = f"{away_team}@{home_team}"
        
        game = game_lookup.get(key)
        if not game:
            print(f"⚠️  Warning: Game not found: {game_desc}")
            continue
        
        home_score = game.get('home_score', 0)
        away_score = game.get('away_score', 0)
        
        # Analyze result based on bet type
        if bet['bet_type'] == 'Spread':
            # Parse the pick (e.g., "Northwestern -5.0" or "Hampton +1.5")
            pick_parts = bet['pick'].split()
            pick_team = ' '.join(pick_parts[:-1])
            pick_spread = float(pick_parts[-1])
            
            actual_margin = home_score - away_score
            
            if pick_team == home_team:
                # Betting on home team with spread
                # Home team needs to win by more than abs(spread) if negative spread (favorite)
                # or lose by less than spread if positive spread (underdog)
                # Example: Home -5.0 means home must win by >5, so actual_margin > 5
                # Example: Home +5.0 means home can lose by <5, so actual_margin > -5
                bet['result'] = actual_margin > -pick_spread
            else:
                # Betting on away team with spread
                # Away team needs to win by more than abs(spread) if negative spread (favorite)  
                # or lose by less than spread if positive spread (underdog)
                # Example: Away -5.0 means away must win by >5, so actual_margin < -5
                # Example: Away +5.0 means away can lose by <5, so actual_margin < 5
                bet['result'] = actual_margin < pick_spread
                
        else:  # Total
            total = home_score + away_score
            # Extract line from pick (e.g., "Over 145.0" -> 145.0)
            pick_parts = bet['pick'].split()
            line = float(pick_parts[-1])
            
            if 'Over' in bet['pick']:
                bet['result'] = total > line
            else:
                bet['result'] = total < line
        
        # Update bet with game info
        bet['actual_score'] = f"{away_team} {away_score}, {home_team} {home_score}"
        
        if bet['result']:
            wins += 1
            bet['result_str'] = '✅ WON'
        else:
            losses += 1
            bet['result_str'] = '❌ LOST'
    
    # Display results
    print("="*80)
    print("BEST BETS RESULTS")
    print("="*80)
    print()
    
    table_data = []
    for i, bet in enumerate(best_bets, 1):
        table_data.append([
            f"#{i}",
            bet['game_description'][:30],
            bet['bet_type'],
            bet['pick'][:20],
            bet['odds'],
            f"{bet['predicted_prob']:.1%}",
            f"{bet['confidence']:.1%}",
            f"{bet['score']:.3f}",
            bet.get('result_str', 'N/A')
        ])
    
    print(tabulate(table_data,
                   headers=['Rank', 'Game', 'Type', 'Pick', 'Odds', 'Value', 'Conf', 'Score', 'Result'],
                   tablefmt='grid'))
    
    # Detailed results
    print()
    print("="*80)
    print("DETAILED RESULTS")
    print("="*80)
    print()
    
    for i, bet in enumerate(best_bets, 1):
        print(f"#{i} - {bet['game_description']}")
        print(f"    Pick: {bet['pick']} ({bet['odds']})")
        print(f"    Value Rating: {bet['predicted_prob']:.1%} | Confidence: {bet['confidence']:.1%} | Score: {bet['score']:.3f}")
        print(f"    Result: {bet.get('actual_score', 'N/A')}")
        print(f"    Status: {bet.get('result_str', 'N/A')}")
        if 'reasoning' in bet:
            print(f"    Reasoning: {bet['reasoning']}")
        print()
    
    # Summary
    print("="*80)
    print("SUMMARY")
    print("="*80)
    print()
    
    total_bets = wins + losses
    win_rate = wins / total_bets if total_bets > 0 else 0
    
    print(f"📊 BEST BETS:")
    print(f"   Record: {wins}-{losses}")
    print(f"   Win Rate: {win_rate:.1%}")
    
    if win_rate > 0.524:
        print(f"   ✅ PROFITABLE (need >52.4%)")
    else:
        print(f"   ❌ NOT PROFITABLE (need >52.4%)")
    
    # Breakdown by type
    spread_bets = [b for b in best_bets if b['bet_type'] == 'Spread']
    total_bets_list = [b for b in best_bets if b['bet_type'] == 'Total']
    
    spread_wins = sum(1 for b in spread_bets if b.get('result', False))
    total_wins = sum(1 for b in total_bets_list if b.get('result', False))
    
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
    parser = argparse.ArgumentParser(description='Analyze saved best bets for a date')
    parser.add_argument('-d', '--date', type=str,
                       help='Date to analyze (YYYY-MM-DD format)')
    
    args = parser.parse_args()
    
    if args.date:
        target_date = args.date
    else:
        # Default to yesterday
        now_utc = datetime.now(timezone.utc)
        now_est = now_utc - timedelta(hours=5)
        yesterday = now_est - timedelta(days=1)
        target_date = yesterday.strftime('%Y-%m-%d')
    
    analyze_saved_bets(target_date)


if __name__ == '__main__':
    main()

