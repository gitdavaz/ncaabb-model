#!/usr/bin/env python3
"""
Database module for storing and retrieving model picks

This module handles:
- Saving all picks to Supabase
- Locking picks once games start
- Retrieving picks for analysis
- Updating results after games complete
"""

import os
from datetime import datetime, timezone
from typing import List, Dict, Optional
from supabase import create_client, Client


class ModelPicksDB:
    """Database interface for model picks"""
    
    def __init__(self, supabase_url: str, supabase_key: str):
        """
        Initialize database connection
        
        Args:
            supabase_url: Supabase project URL
            supabase_key: Supabase service key
        """
        self.client: Client = create_client(supabase_url, supabase_key)
    
    def save_pick(self, pick: Dict) -> bool:
        """
        Save or update a pick in the database
        
        Only saves if:
        1. Pick doesn't exist yet, OR
        2. Pick exists but game hasn't started (not locked)
        
        Args:
            pick: Dictionary with pick details
            
        Returns:
            True if saved/updated, False if locked
        """
        # Check if pick is already locked
        existing = self.client.table('model_picks').select('id, is_locked').eq(
            'date', pick['date']
        ).eq(
            'game_id', pick['game_id']
        ).eq(
            'bet_type', pick['bet_type']
        ).execute()
        
        if existing.data and len(existing.data) > 0:
            if existing.data[0]['is_locked']:
                # Game has started, don't overwrite
                return False
            else:
                # Update existing unlocked pick
                self.client.table('model_picks').update(pick).eq(
                    'id', existing.data[0]['id']
                ).execute()
                return True
        else:
            # Insert new pick
            self.client.table('model_picks').insert(pick).execute()
            return True
    
    def save_picks_batch(self, picks: List[Dict]) -> Dict:
        """
        Save multiple picks at once
        
        Args:
            picks: List of pick dictionaries
            
        Returns:
            Dictionary with counts: {'saved': N, 'skipped': M, 'errors': K}
        """
        saved = 0
        skipped = 0
        errors = 0
        
        for pick in picks:
            try:
                if self.save_pick(pick):
                    saved += 1
                else:
                    skipped += 1
            except Exception as e:
                print(f"Error saving pick: {e}")
                errors += 1
        
        return {'saved': saved, 'skipped': skipped, 'errors': errors}
    
    def mark_best_bets(self, date: str, best_bets: List[Dict]) -> int:
        """
        Mark picks as best bets
        
        Args:
            date: Date in YYYY-MM-DD format
            best_bets: List of best bet dictionaries
            
        Returns:
            Number of picks updated
        """
        # First, clear all best bet flags for this date
        self.client.table('model_picks').update({
            'is_best_bet': False,
            'best_bet_rank': None
        }).eq('date', date).execute()
        
        # Then mark the best bets
        updated = 0
        for i, bet in enumerate(best_bets, 1):
            result = self.client.table('model_picks').update({
                'is_best_bet': True,
                'best_bet_rank': i
            }).eq('date', date).eq(
                'game_id', bet['game_id']
            ).eq(
                'bet_type', bet['bet_type'].lower()
            ).execute()
            
            if result.data:
                updated += len(result.data)
        
        return updated
    
    def lock_started_games(self, date: Optional[str] = None) -> int:
        """
        Lock all picks for games that have started
        
        Args:
            date: Optional date filter (YYYY-MM-DD)
            
        Returns:
            Number of picks locked
        """
        # Call the database function
        result = self.client.rpc('lock_started_games').execute()
        return result.data if result.data else 0
    
    def get_picks(self, date: str, best_bets_only: bool = False) -> List[Dict]:
        """
        Get picks for a date
        
        Args:
            date: Date in YYYY-MM-DD format
            best_bets_only: If True, only return best bets
            
        Returns:
            List of pick dictionaries
        """
        query = self.client.table('model_picks').select('*').eq('date', date)
        
        if best_bets_only:
            query = query.eq('is_best_bet', True).order('best_bet_rank')
        else:
            query = query.order('score', desc=True)
        
        result = query.execute()
        return result.data if result.data else []
    
    def update_results(self, date: str, results: Dict[str, Dict]) -> int:
        """
        Update results for completed games
        
        Args:
            date: Date in YYYY-MM-DD format
            results: Dictionary mapping game_id to {'home_score': X, 'away_score': Y}
            
        Returns:
            Number of picks updated
        """
        updated = 0
        
        for game_id, scores in results.items():
            home_score = scores['home_score']
            away_score = scores['away_score']
            
            # Get all picks for this game
            picks = self.client.table('model_picks').select('*').eq(
                'date', date
            ).eq(
                'game_id', game_id
            ).execute()
            
            if not picks.data:
                continue
            
            for pick in picks.data:
                # Calculate result based on bet type
                if pick['bet_type'] == 'spread':
                    result = self._calculate_spread_result(
                        pick, home_score, away_score
                    )
                else:  # total
                    result = self._calculate_total_result(
                        pick, home_score, away_score
                    )
                
                # Update the pick
                self.client.table('model_picks').update({
                    'home_score': home_score,
                    'away_score': away_score,
                    'result': result
                }).eq('id', pick['id']).execute()
                
                updated += 1
        
        return updated
    
    def _calculate_spread_result(self, pick: Dict, home_score: int, away_score: int) -> bool:
        """Calculate if a spread bet won"""
        # Parse the pick (e.g., "Duke -5.5" or "UNC +3.5")
        pick_parts = pick['pick'].split()
        pick_team = ' '.join(pick_parts[:-1])
        pick_spread = float(pick_parts[-1])
        
        actual_margin = home_score - away_score
        
        if pick_team == pick['home_team']:
            # Betting on home team
            return actual_margin > -pick_spread
        else:
            # Betting on away team
            return actual_margin < pick_spread
    
    def _calculate_total_result(self, pick: Dict, home_score: int, away_score: int) -> bool:
        """Calculate if a total bet won"""
        total = home_score + away_score
        
        # Extract line from pick
        pick_parts = pick['pick'].split()
        line = float(pick_parts[-1])
        
        if 'Over' in pick['pick']:
            return total > line
        else:
            return total < line
    
    def get_performance_summary(self, start_date: str, end_date: Optional[str] = None) -> Dict:
        """
        Get performance summary for a date range
        
        Args:
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD), defaults to start_date
            
        Returns:
            Dictionary with performance metrics
        """
        if not end_date:
            end_date = start_date
        
        # Query picks
        picks = self.client.table('model_picks').select('*').gte(
            'date', start_date
        ).lte(
            'date', end_date
        ).not_.is_('result', 'null').execute()
        
        if not picks.data:
            return {
                'total': 0,
                'wins': 0,
                'losses': 0,
                'win_rate': 0,
                'roi': 0
            }
        
        all_picks = picks.data
        wins = sum(1 for p in all_picks if p['result'])
        losses = len(all_picks) - wins
        
        # Calculate ROI (assuming -110 odds)
        profit = (wins * 0.909) - losses
        roi = (profit / len(all_picks)) * 100 if len(all_picks) > 0 else 0
        
        # Best bets stats
        best_bets = [p for p in all_picks if p['is_best_bet']]
        best_bets_wins = sum(1 for p in best_bets if p['result'])
        
        # By type
        spread_picks = [p for p in all_picks if p['bet_type'] == 'spread']
        total_picks = [p for p in all_picks if p['bet_type'] == 'total']
        
        return {
            'total': len(all_picks),
            'wins': wins,
            'losses': losses,
            'win_rate': wins / len(all_picks) if len(all_picks) > 0 else 0,
            'roi': roi,
            'profit_units': profit,
            'best_bets': {
                'total': len(best_bets),
                'wins': best_bets_wins,
                'losses': len(best_bets) - best_bets_wins,
                'win_rate': best_bets_wins / len(best_bets) if len(best_bets) > 0 else 0
            },
            'by_type': {
                'spread': {
                    'total': len(spread_picks),
                    'wins': sum(1 for p in spread_picks if p['result']),
                    'win_rate': sum(1 for p in spread_picks if p['result']) / len(spread_picks) if len(spread_picks) > 0 else 0
                },
                'total': {
                    'total': len(total_picks),
                    'wins': sum(1 for p in total_picks if p['result']),
                    'win_rate': sum(1 for p in total_picks if p['result']) / len(total_picks) if len(total_picks) > 0 else 0
                }
            }
        }

