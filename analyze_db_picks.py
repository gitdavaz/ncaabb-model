#!/usr/bin/env python3
"""
Analyze model picks from Supabase database

This uses the actual picks stored at game time,
not re-generated predictions with different odds.
"""

import os
import sys
import argparse
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
from tabulate import tabulate
from typing import Dict, List

from model_picks_db import ModelPicksDB
from api_client import CollegeBasketballAPI


def update_results_from_api(picks_db: ModelPicksDB, api_client: CollegeBasketballAPI, date: str):
    """Update results for picks that don't have results yet"""
    # Get picks without results
    picks = picks_db.get_picks(date)
    picks_without_results = [p for p in picks if p['result'] is None]
    
    if not picks_without_results:
        return 0
    
    print(f"⏳ Fetching results for {len(picks_without_results)} pending picks...")
    
    # Get completed games
    games = api_client.get_todays_games(date=date, d1_only=True, upcoming_only=False)
    completed_games = [g for g in games if g.get('status') == 'final']
    
    # Build results dict
    results = {}
    for game in completed_games:
        game_id = game.get('id', '')
        if game_id:
            results[game_id] = {
                'home_score': game.get('home_score', 0),
                'away_score': game.get('away_score', 0)
            }
    
    # Update in database
    updated = picks_db.update_results(date, results)
    print(f"   ✅ Updated {updated} picks with results")
    
    return updated


def analyze_picks(date: str, best_bets_only: bool = False, update_results: bool = True):
    """
    Analyze picks from database
    
    Args:
        date: Date in YYYY-MM-DD format
        best_bets_only: If True, only analyze best bets
        update_results: If True, fetch and update results from API
    """
    load_dotenv()
    
    bet_type_label = "BEST BETS" if best_bets_only else "ALL PICKS"
    
    print("="*80)
    print(f"{bet_type_label} ANALYSIS - {date}")
    print("Using picks saved to database at game time")
    print("="*80)
    print()
    
    # Initialize database
    supabase_url = os.getenv('SUPABASE_URL')
    supabase_key = os.getenv('SUPABASE_SERVICE_KEY')
    
    if not supabase_url or not supabase_key:
        print("❌ Error: SUPABASE_URL or SUPABASE_SERVICE_KEY not found in environment")
        return
    
    picks_db = ModelPicksDB(supabase_url, supabase_key)
    
    # Lock any games that have started
    locked = picks_db.lock_started_games(date)
    if locked > 0:
        print(f"🔒 Locked {locked} picks for games that have started")
        print()
    
    # Update results if requested
    if update_results:
        api_key = os.getenv('API_KEY')
        if api_key:
            api_client = CollegeBasketballAPI(api_key)
            update_results_from_api(picks_db, api_client, date)
            print()
    
    # Get picks
    picks = picks_db.get_picks(date, best_bets_only=best_bets_only)
    
    if not picks:
        print(f"❌ No picks found for {date}")
        print()
        if not best_bets_only:
            print("💡 TIP: Run main.py for this date to generate and save picks")
        else:
            print("💡 TIP: Picks exist but none were marked as best bets")
        return
    
    print(f"📁 Found {len(picks)} picks")
    print()
    
    # Display results table
    print("="*80)
    print(f"{bet_type_label} RESULTS")
    print("="*80)
    print()
    
    table_data = []
    for pick in picks:
        rank = f"#{pick['best_bet_rank']}" if pick.get('best_bet_rank') else "-"
        game_desc = f"{pick['away_team']} @ {pick['home_team']}"
        
        # Result status
        if pick['result'] is None:
            result_str = "⏳ Pending"
        elif pick['result']:
            result_str = "✅ WON"
        else:
            result_str = "❌ LOST"
        
        table_data.append([
            rank,
            game_desc[:30],
            pick['bet_type'].title(),
            pick['pick'][:20],
            pick['odds'],
            f"{pick['predicted_prob']:.1%}",
            f"{pick['confidence']:.1%}",
            f"{pick['score']:.3f}",
            result_str
        ])
    
    headers = ['Rank', 'Game', 'Type', 'Pick', 'Odds', 'Value', 'Conf', 'Score', 'Result']
    print(tabulate(table_data, headers=headers, tablefmt='grid'))
    
    # Detailed results
    print()
    print("="*80)
    print("DETAILED RESULTS")
    print("="*80)
    print()
    
    for pick in picks:
        rank = f"#{pick['best_bet_rank']}" if pick.get('best_bet_rank') else ""
        game_desc = f"{pick['away_team']} @ {pick['home_team']}"
        
        print(f"{rank} {game_desc}".strip())
        print(f"    Pick: {pick['pick']} ({pick['odds']})")
        print(f"    Value Rating: {pick['predicted_prob']:.1%} | Confidence: {pick['confidence']:.1%} | Score: {pick['score']:.3f}")
        
        if pick['home_score'] is not None and pick['away_score'] is not None:
            print(f"    Result: {pick['away_team']} {pick['away_score']}, {pick['home_team']} {pick['home_score']}")
        
        if pick['result'] is None:
            print(f"    Status: ⏳ Pending")
        elif pick['result']:
            print(f"    Status: ✅ WON")
        else:
            print(f"    Status: ❌ LOST")
        
        if pick.get('reasoning'):
            print(f"    Reasoning: {pick['reasoning']}")
        
        print()
    
    # Summary statistics
    print("="*80)
    print("SUMMARY")
    print("="*80)
    print()
    
    # Filter completed picks
    completed = [p for p in picks if p['result'] is not None]
    
    if not completed:
        print("⏳ No completed games yet")
        print()
        return
    
    wins = sum(1 for p in completed if p['result'])
    losses = len(completed) - wins
    win_rate = wins / len(completed) if len(completed) > 0 else 0
    
    print(f"📊 {bet_type_label}:")
    print(f"   Record: {wins}-{losses}")
    print(f"   Win Rate: {win_rate:.1%}")
    
    if win_rate > 0.524:
        print(f"   ✅ PROFITABLE (need >52.4%)")
    else:
        print(f"   ❌ NOT PROFITABLE (need >52.4%)")
    
    # Breakdown by type
    spread_picks = [p for p in completed if p['bet_type'] == 'spread']
    total_picks = [p for p in completed if p['bet_type'] == 'total']
    
    if spread_picks:
        spread_wins = sum(1 for p in spread_picks if p['result'])
        print()
        print(f"📊 SPREAD BETS:")
        print(f"   Record: {spread_wins}-{len(spread_picks)-spread_wins}")
        print(f"   Win Rate: {spread_wins/len(spread_picks):.1%}")
    
    if total_picks:
        total_wins = sum(1 for p in total_picks if p['result'])
        print()
        print(f"📊 TOTAL BETS:")
        print(f"   Record: {total_wins}-{len(total_picks)-total_wins}")
        print(f"   Win Rate: {total_wins/len(total_picks):.1%}")
    
    # ROI calculation
    if len(completed) > 0:
        # Assuming -110 odds: win 0.909 units, lose 1 unit
        profit = (wins * 0.909) - losses
        roi = (profit / len(completed)) * 100
        print()
        print(f"💰 ROI (at -110 odds):")
        print(f"   Units: {profit:+.2f}u")
        print(f"   ROI: {roi:+.1f}%")
    
    print()
    print("="*80)
    print("✅ Analysis Complete!")
    print("="*80)


def main():
    parser = argparse.ArgumentParser(description='Analyze model picks from database')
    parser.add_argument('-d', '--date', type=str,
                       help='Date to analyze (YYYY-MM-DD format)')
    parser.add_argument('--best-bets', action='store_true',
                       help='Analyze only best bets (default: all picks)')
    parser.add_argument('--no-update', action='store_true',
                       help='Skip updating results from API')
    
    args = parser.parse_args()
    
    if args.date:
        target_date = args.date
    else:
        # Default to today (EST)
        now_utc = datetime.now(timezone.utc)
        now_est = now_utc - timedelta(hours=5)
        target_date = now_est.strftime('%Y-%m-%d')
    
    analyze_picks(
        target_date,
        best_bets_only=args.best_bets,
        update_results=not args.no_update
    )


if __name__ == '__main__':
    main()

