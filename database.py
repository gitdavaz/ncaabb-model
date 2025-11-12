"""
Supabase caching layer for NCAAB predictions
Reduces API calls by caching team stats, games, and other data
"""

from typing import Dict, List, Optional
from datetime import datetime, timedelta
from supabase import create_client, Client
import json


class SupabaseCache:
    """
    Manages caching of CBBD API data in Supabase
    """
    
    def __init__(self, supabase_url: str, supabase_key: str):
        """
        Initialize Supabase cache
        
        Args:
            supabase_url: Supabase project URL
            supabase_key: Supabase service role key
        """
        self.client: Client = create_client(supabase_url, supabase_key)
        self.enabled = True
    
    # ==================== TEAM STATS ====================
    
    def get_team_stats(self, team_id: int, season: int, max_age_hours: int = 12) -> Optional[Dict]:
        """
        Get team stats from cache
        
        Args:
            team_id: Team ID
            season: Season year
            max_age_hours: Maximum age of cached data in hours
            
        Returns:
            Cached team stats or None if cache miss
        """
        if not self.enabled:
            return None
        
        try:
            cutoff_time = (datetime.now() - timedelta(hours=max_age_hours)).isoformat()
            
            response = self.client.table('team_stats')\
                .select('*')\
                .eq('team_id', team_id)\
                .eq('season', season)\
                .gte('last_updated', cutoff_time)\
                .execute()
            
            if response.data and len(response.data) > 0:
                cached = response.data[0]
                # Convert back to expected format
                return self._db_to_team_stats_dict(cached)
            
            return None
        except Exception as e:
            print(f"Cache read error (team_stats): {e}")
            return None
    
    def cache_team_stats(self, team_id: int, season: int, stats_data: Dict, team_name: str = None, conference: str = None) -> bool:
        """
        Store team stats in cache
        
        Args:
            team_id: Team ID
            season: Season year
            stats_data: Stats dictionary from API
            team_name: Team name (optional, will cache in teams table if provided)
            conference: Conference name (optional)
            
        Returns:
            True if successful, False otherwise
        """
        if not self.enabled:
            return False
        
        try:
            db_record = {
                'team_id': team_id,
                'season': season,
                'last_updated': datetime.now().isoformat(),
                'games': stats_data.get('games', 0),
                'points_per_game': stats_data.get('points_per_game', 0),
                'opponent_points_per_game': stats_data.get('opponent_points_per_game', 0),
                'offensive_rating': stats_data.get('offensive_rating', 0),
                'defensive_rating': stats_data.get('defensive_rating', 0),
                'pace': stats_data.get('pace', 0),
                'true_shooting_pct': stats_data.get('true_shooting_pct', 0),
                'effective_fg_pct': stats_data.get('effective_fg_pct', 0),
                'turnover_ratio': stats_data.get('turnover_ratio', 0),
                'offensive_rebound_pct': stats_data.get('offensive_rebound_pct', 0),
                'free_throw_rate': stats_data.get('free_throw_rate', 0),
                'opp_effective_fg_pct': stats_data.get('opp_effective_fg_pct', 0),
                'opp_turnover_ratio': stats_data.get('opp_turnover_ratio', 0),
                'opp_offensive_rebound_pct': stats_data.get('opp_offensive_rebound_pct', 0),
                'opp_free_throw_rate': stats_data.get('opp_free_throw_rate', 0),
                'raw_data': json.dumps(stats_data)  # Store full response
            }
            
            # Use upsert with on_conflict parameter to handle duplicates
            self.client.table('team_stats').upsert(db_record, on_conflict='team_id,season').execute()
            
            # Also cache team info if provided
            if team_name:
                team_info = {
                    'id': team_id,
                    'school': team_name,
                    'conference': conference or stats_data.get('conference', ''),
                    'last_updated': datetime.now().isoformat()
                }
                self.cache_team_info(team_info)
            
            return True
        except Exception as e:
            print(f"Cache write error (team_stats): {e}")
            return False
    
    def _db_to_team_stats_dict(self, db_record: Dict) -> Dict:
        """Convert database record back to API format"""
        # Try to use raw_data if available
        if db_record.get('raw_data'):
            try:
                return json.loads(db_record['raw_data'])
            except:
                pass
        
        # Otherwise reconstruct from individual fields
        return {
            'team_id': db_record.get('team_id'),
            'games': db_record.get('games', 0),
            'points_per_game': db_record.get('points_per_game', 0),
            'opponent_points_per_game': db_record.get('opponent_points_per_game', 0),
            'offensive_rating': db_record.get('offensive_rating', 0),
            'defensive_rating': db_record.get('defensive_rating', 0),
            'pace': db_record.get('pace', 0),
            'true_shooting_pct': db_record.get('true_shooting_pct', 0),
            'effective_fg_pct': db_record.get('effective_fg_pct', 0),
            'turnover_ratio': db_record.get('turnover_ratio', 0),
            'offensive_rebound_pct': db_record.get('offensive_rebound_pct', 0),
            'free_throw_rate': db_record.get('free_throw_rate', 0),
            'opp_effective_fg_pct': db_record.get('opp_effective_fg_pct', 0),
            'opp_turnover_ratio': db_record.get('opp_turnover_ratio', 0),
            'opp_offensive_rebound_pct': db_record.get('opp_offensive_rebound_pct', 0),
            'opp_free_throw_rate': db_record.get('opp_free_throw_rate', 0),
        }
    
    # ==================== TEAMS ====================
    
    def get_team_info(self, team_id: int) -> Optional[Dict]:
        """
        Get team information from cache
        
        Args:
            team_id: Team ID
            
        Returns:
            Cached team info or None
        """
        if not self.enabled:
            return None
        
        try:
            response = self.client.table('teams')\
                .select('*')\
                .eq('id', team_id)\
                .execute()
            
            if response.data and len(response.data) > 0:
                return response.data[0]
            
            return None
        except Exception as e:
            print(f"Cache read error (teams): {e}")
            return None
    
    def cache_team_info(self, team_data: Dict) -> bool:
        """
        Store team information in cache
        
        Args:
            team_data: Team information dictionary
            
        Returns:
            True if successful
        """
        if not self.enabled:
            return False
        
        try:
            db_record = {
                'id': team_data.get('id'),
                'school': team_data.get('name', team_data.get('school', '')),
                'mascot': team_data.get('mascot', ''),
                'abbreviation': team_data.get('abbreviation', ''),
                'conference': team_data.get('conference', ''),
                'last_updated': datetime.now().isoformat()
            }
            
            # Use upsert with on_conflict parameter to handle duplicates
            self.client.table('teams').upsert(db_record, on_conflict='id').execute()
            return True
        except Exception as e:
            print(f"Cache write error (teams): {e}")
            return False
    
    # ==================== GAMES ====================
    
    def get_games_by_date(self, date: str, season: int) -> Optional[List[Dict]]:
        """
        Get games for a specific date from cache
        
        Args:
            date: Date in YYYY-MM-DD format
            season: Season year
            
        Returns:
            List of cached games or None
        """
        if not self.enabled:
            return None
        
        try:
            # Get games for this date (with some buffer for timezone issues)
            start_date = f"{date}T00:00:00"
            end_date = f"{date}T23:59:59"
            
            response = self.client.table('games')\
                .select('*')\
                .eq('season', season)\
                .gte('start_date', start_date)\
                .lte('start_date', end_date)\
                .execute()
            
            if response.data:
                return [self._db_to_game_dict(g) for g in response.data]
            
            return None
        except Exception as e:
            print(f"Cache read error (games): {e}")
            return None
    
    def cache_games(self, games: List[Dict], season: int) -> bool:
        """
        Store multiple games in cache
        
        Args:
            games: List of game dictionaries
            season: Season year
            
        Returns:
            True if successful
        """
        if not self.enabled or not games:
            return False
        
        try:
            db_records = []
            for game in games:
                db_record = {
                    'id': game.get('id'),
                    'season': season,
                    'start_date': game.get('start_date'),
                    'home_team_id': game.get('home_team_id'),
                    'away_team_id': game.get('away_team_id'),
                    'home_score': game.get('home_score'),
                    'away_score': game.get('away_score'),
                    'completed': bool(game.get('home_score') and game.get('away_score')),
                    'last_updated': datetime.now().isoformat(),
                    'raw_data': json.dumps(game)
                }
                db_records.append(db_record)
            
            if db_records:
                # Use upsert with on_conflict parameter to handle duplicates
                self.client.table('games').upsert(db_records, on_conflict='id').execute()
            return True
        except Exception as e:
            print(f"Cache write error (games): {e}")
            return False
    
    def _db_to_game_dict(self, db_record: Dict) -> Dict:
        """Convert database game record back to API format"""
        if db_record.get('raw_data'):
            try:
                return json.loads(db_record['raw_data'])
            except:
                pass
        
        return {
            'id': db_record.get('id'),
            'season': db_record.get('season'),
            'start_date': db_record.get('start_date'),
            'home_team_id': db_record.get('home_team_id'),
            'away_team_id': db_record.get('away_team_id'),
            'home_score': db_record.get('home_score'),
            'away_score': db_record.get('away_score'),
        }
    
    # ==================== RECENT GAMES ====================
    
    def get_recent_games(self, team_id: int, season: int, limit: int = 10, 
                        max_age_hours: int = 6) -> Optional[List[Dict]]:
        """
        Get recent games for a team from cache
        
        Args:
            team_id: Team ID
            season: Season year
            limit: Number of recent games
            max_age_hours: Maximum age of cached data
            
        Returns:
            List of recent games or None
        """
        if not self.enabled:
            return None
        
        try:
            cutoff_time = (datetime.now() - timedelta(hours=max_age_hours)).isoformat()
            
            # Get games where team is home
            home_games = self.client.table('games')\
                .select('*')\
                .eq('season', season)\
                .eq('home_team_id', team_id)\
                .eq('completed', True)\
                .gte('last_updated', cutoff_time)\
                .execute()
            
            # Get games where team is away
            away_games = self.client.table('games')\
                .select('*')\
                .eq('season', season)\
                .eq('away_team_id', team_id)\
                .eq('completed', True)\
                .gte('last_updated', cutoff_time)\
                .execute()
            
            # Combine and sort by date
            all_games = []
            if home_games.data:
                all_games.extend(home_games.data)
            if away_games.data:
                all_games.extend(away_games.data)
            
            if all_games:
                # Sort by start_date descending and limit
                all_games.sort(key=lambda x: x.get('start_date', ''), reverse=True)
                recent = all_games[:limit]
                return [self._db_to_game_dict(g) for g in recent]
            
            return None
        except Exception as e:
            print(f"Cache read error (recent_games): {e}")
            return None
    
    # ==================== UTILITY ====================
    
    def clear_old_cache(self, days: int = 7) -> None:
        """
        Clear cache entries older than specified days
        
        Args:
            days: Number of days to keep
        """
        if not self.enabled:
            return
        
        try:
            cutoff = (datetime.now() - timedelta(days=days)).isoformat()
            
            # Clear old team stats
            self.client.table('team_stats')\
                .delete()\
                .lt('last_updated', cutoff)\
                .execute()
            
            # Clear old games (keep completed games though)
            self.client.table('games')\
                .delete()\
                .eq('completed', False)\
                .lt('last_updated', cutoff)\
                .execute()
            
            print(f"Cleared cache entries older than {days} days")
        except Exception as e:
            print(f"Error clearing cache: {e}")

