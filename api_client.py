"""
API Client for College Basketball Data API (CBBD)
Uses the official CBBD Python library: https://github.com/CFBD/cbbd-python
"""

import cbbd
from cbbd.rest import ApiException
import os
from typing import Dict, List, Optional
from datetime import datetime, timedelta


class CollegeBasketballAPI:
    """Client for interacting with the College Basketball Data API"""
    
    def __init__(self, api_key: Optional[str] = None, cache=None):
        """
        Initialize the API client
        
        Args:
            api_key: API key for authentication. If not provided, will look for API_KEY env variable
            cache: SupabaseCache instance for caching API responses (optional)
        """
        self.api_key = api_key or os.getenv('API_KEY')
        self.cache = cache  # Supabase cache instance
        
        # Configure API client
        configuration = cbbd.Configuration()
        configuration.access_token = self.api_key
        
        # Create API client
        self.api_client = cbbd.ApiClient(configuration)
        
        # Initialize API instances
        self.games_api = cbbd.GamesApi(self.api_client)
        self.lines_api = cbbd.LinesApi(self.api_client)
        self.stats_api = cbbd.StatsApi(self.api_client)
        self.teams_api = cbbd.TeamsApi(self.api_client)
        self.ratings_api = cbbd.RatingsApi(self.api_client)
        
        # Cache team name to ID mapping
        self._team_cache = {}
        
        # Track API calls for debugging
        self.api_calls = 0
    
    def _get_current_season(self) -> int:
        """
        Get the current college basketball season year.
        
        Season naming: The 2024-2025 season is referred to as "2025"
        - Starts in November 2024
        - Ends in April 2025
        
        Returns:
            Season year (e.g., 2025 for the 2024-2025 season)
        """
        now = datetime.now()
        # College basketball season spans two calendar years
        # Season starts in November, so if we're before July, use current year
        # Otherwise use next year
        if now.month < 7:
            return now.year
        else:
            return now.year + 1
    
    def _get_team_name_by_id(self, team_id: int) -> str:
        """Get team name from team ID"""
        if team_id in self._team_cache:
            return self._team_cache[team_id]
        
        try:
            teams = self.teams_api.get_teams()
            for team in teams:
                if hasattr(team, 'id') and team.id == team_id:
                    name = team.school if hasattr(team, 'school') else ''
                    self._team_cache[team_id] = name
                    return name
        except Exception:
            pass
        
        return ''
    
    def get_todays_games(self, date: Optional[str] = None, d1_only: bool = True, upcoming_only: bool = True) -> List[Dict]:
        """
        Get all games for today (or specified date)
        
        Args:
            date: Date in YYYY-MM-DD format (EST timezone). If None, uses today in EST
            d1_only: If True, only return games between D1 conference teams (excludes exhibitions)
            upcoming_only: If True, only return games that haven't been played yet (excludes FINAL games)
            
        Returns:
            List of game dictionaries
        """
        if date is None:
            # Get current date in EST (UTC-5)
            from datetime import timezone, timedelta
            now_utc = datetime.now(timezone.utc)
            now_est = now_utc - timedelta(hours=5)
            date = now_est.strftime('%Y-%m-%d')
        
        try:
            season = self._get_current_season()
            
            # Parse date in EST timezone (all game times are displayed in EST)
            # Create range for the full day in EST
            from datetime import timezone, timedelta
            local_date = datetime.strptime(date, '%Y-%m-%d')
            
            # Start of day EST (00:00:00 EST)
            start_est = local_date.replace(hour=0, minute=0, second=0, microsecond=0)
            # End of day EST (23:59:59 EST)
            end_est = local_date.replace(hour=23, minute=59, second=59, microsecond=999999)
            
            # Convert EST to UTC for API query (API uses UTC timestamps)
            # EST is UTC-5 (or EDT is UTC-4, but we'll use EST year-round for simplicity)
            # To convert EST to UTC, add 5 hours
            est_offset = timedelta(hours=5)
            start_utc = start_est + est_offset
            end_utc = end_est + est_offset
            
            # Try cache first (for same-day queries)
            if self.cache and not upcoming_only:  # Only cache completed games
                cached_games = self.cache.get_games_by_date(date, season)
                if cached_games:
                    # Still apply D1 filter if requested
                    if d1_only:
                        cached_games = [g for g in cached_games 
                                       if g.get('home_conference') and g.get('away_conference')]
                    return cached_games
            
            # Cache miss or upcoming games - fetch from API
            self.api_calls += 1
            
            # Get games for the UTC date range
            games = self.games_api.get_games(
                season=season,
                start_date_range=start_utc,
                end_date_range=end_utc
            )
            
            games_list = []
            for game in games:
                # Skip completed games if upcoming_only
                if upcoming_only:
                    status = str(game.status) if hasattr(game, 'status') else ''
                    if 'FINAL' in status or 'COMPLETED' in status:
                        continue
                
                game_dict = self._game_to_dict(game)
                
                # Filter for D1 games only if requested
                if d1_only:
                    # Only include if both teams have a conference affiliation
                    # This filters out exhibition games against non-D1 schools
                    home_conf = game.home_conference if hasattr(game, 'home_conference') else None
                    away_conf = game.away_conference if hasattr(game, 'away_conference') else None
                    
                    # Skip if either team doesn't have a conference (non-D1 exhibition)
                    if not home_conf or not away_conf:
                        continue
                    
                    # Also skip if marked as non-conference game against clearly non-D1 opponent
                    # (Some small schools might have conference listed but are exhibition)
                    game_dict['home_conference'] = home_conf
                    game_dict['away_conference'] = away_conf
                
                games_list.append(game_dict)
            
            # Cache the results (all games, not filtered)
            if self.cache and games_list:
                self.cache.cache_games(games_list, season)
            
            return games_list
        except ApiException as e:
            print(f"API Exception getting games: {e}")
            return []
        except Exception as e:
            print(f"Error getting games: {e}")
            return []
    
    def get_team_stats(self, team_id: int, season: Optional[int] = None) -> Dict:
        """
        Get team statistics (with caching)
        
        Args:
            team_id: Team ID
            season: Season year. If None, uses current season
            
        Returns:
            Team statistics dictionary
        """
        if season is None:
            season = self._get_current_season()
        
        # Try cache first
        if self.cache:
            cached_stats = self.cache.get_team_stats(team_id, season, max_age_hours=12)
            if cached_stats:
                return cached_stats
        
        # Cache miss - fetch from API
        self.api_calls += 1
        
        # Get team name from ID
        team_name = self._get_team_name_by_id(team_id)
        if not team_name:
            return {}
        
        try:
            # Get team stats by name
            stats_list = self.stats_api.get_team_season_stats(
                season=season,
                team=team_name
            )
            
            if stats_list and len(stats_list) > 0:
                stats_dict = self._team_stats_to_dict(stats_list[0])
                
                # Cache the result (including team info for the teams table)
                if self.cache and stats_dict:
                    # Extract conference from API response
                    conference = stats_list[0].conference if hasattr(stats_list[0], 'conference') else None
                    self.cache.cache_team_stats(team_id, season, stats_dict, team_name=team_name, conference=conference)
                
                return stats_dict
            
            return {}
        except ApiException as e:
            print(f"API Exception getting team stats: {e}")
            return {}
        except Exception as e:
            print(f"Error getting team stats: {e}")
            return {}
    
    def get_team_info(self, team_id: int) -> Dict:
        """
        Get team information (with caching)
        
        Args:
            team_id: Team ID
            
        Returns:
            Team information dictionary
        """
        # Try cache first
        if self.cache:
            cached_info = self.cache.get_team_info(team_id)
            if cached_info:
                return cached_info
        
        # Cache miss - fetch from API
        self.api_calls += 1
        
        try:
            teams = self.teams_api.get_teams()
            for team in teams:
                if hasattr(team, 'id') and team.id == team_id:
                    team_info = {
                        'id': team.id,
                        'name': team.school if hasattr(team, 'school') else 'Unknown',
                        'conference': team.conference if hasattr(team, 'conference') else '',
                        'abbreviation': team.abbreviation if hasattr(team, 'abbreviation') else ''
                    }
                    
                    # Cache the result
                    if self.cache:
                        self.cache.cache_team_info(team_info)
                    
                    return team_info
            return {}
        except Exception as e:
            print(f"Error getting team info: {e}")
            return {}
    
    def get_odds(self, game_id: int) -> Dict:
        """
        Get betting odds for a game
        
        Args:
            game_id: Game ID
            
        Returns:
            Odds dictionary with spread, total, moneyline
        """
        # Note: The CBBD API doesn't support querying lines by game_id directly
        # This is a limitation of the API
        # We'll return empty dict and let the caller handle default odds
        return {}
    
    def get_odds_for_team_date(self, team_name: str, date: str) -> Dict:
        """
        Get betting odds for a team on a specific date
        
        Args:
            team_name: Team name
            date: Date string in YYYY-MM-DD format
            
        Returns:
            Odds dictionary
        """
        try:
            season = self._get_current_season()
            target_date = datetime.strptime(date, '%Y-%m-%d')
            start_date = target_date.replace(hour=0, minute=0, second=0)
            end_date = target_date.replace(hour=23, minute=59, second=59)
            
            lines = self.lines_api.get_lines(
                season=season,
                team=team_name,
                start_date_range=start_date,
                end_date_range=end_date
            )
            
            if lines and len(lines) > 0:
                return self._line_to_dict(lines[0], team_name)
            
            return {}
        except ApiException:
            return {}
        except Exception:
            return {}
    
    def get_recent_games(self, team_id: int, limit: int = 10) -> List[Dict]:
        """
        Get recent games for a team (with caching)
        
        Args:
            team_id: Team ID
            limit: Number of recent games to retrieve
            
        Returns:
            List of recent game dictionaries
        """
        season = self._get_current_season()
        
        # Try cache first
        if self.cache:
            cached_games = self.cache.get_recent_games(team_id, season, limit, max_age_hours=6)
            if cached_games:
                return cached_games
        
        # Cache miss - fetch from API
        self.api_calls += 1
        
        team_name = self._get_team_name_by_id(team_id)
        if not team_name:
            return []
        
        try:
            # Get games for the team
            games = self.games_api.get_games(
                season=season,
                team=team_name
            )
            
            # Convert to dict and filter completed games
            games_list = []
            for g in games:
                game_dict = self._game_to_dict(g)
                # Only include completed games with valid scores (not 0-0 or None)
                home_score = game_dict.get('home_score')
                away_score = game_dict.get('away_score')
                if (home_score is not None and away_score is not None and 
                    (home_score > 0 or away_score > 0)):  # At least one team scored
                    games_list.append(game_dict)
            
            # Sort by date (most recent first)
            games_list.sort(key=lambda x: x.get('start_date', ''), reverse=True)
            
            recent_games = games_list[:limit]
            
            # Cache the result
            if self.cache and recent_games:
                self.cache.cache_games(recent_games, season)
            
            return recent_games
        except Exception as e:
            print(f"Error getting recent games: {e}")
            return []
    
    def get_team_roster(self, team_id: int) -> List[Dict]:
        """
        Get team roster
        
        Args:
            team_id: Team ID
            
        Returns:
            List of player dictionaries
        """
        team_name = self._get_team_name_by_id(team_id)
        if not team_name:
            return []
        
        try:
            season = self._get_current_season()
            roster = self.teams_api.get_team_roster(team=team_name, year=season)
            return [self._player_to_dict(p) for p in roster]
        except Exception as e:
            print(f"Error getting roster: {e}")
            return []
    
    def _game_to_dict(self, game) -> Dict:
        """Convert game object to dictionary"""
        # Handle start_date - might be datetime object or string
        start_date = game.start_date if hasattr(game, 'start_date') else None
        if start_date and hasattr(start_date, 'isoformat'):
            start_date = start_date.isoformat()
        
        return {
            'id': game.id if hasattr(game, 'id') else None,
            'season': game.season if hasattr(game, 'season') else None,
            'start_date': start_date,
            'home_team': game.home_team if hasattr(game, 'home_team') else 'Home',
            'away_team': game.away_team if hasattr(game, 'away_team') else 'Away',
            'home_team_id': game.home_team_id if hasattr(game, 'home_team_id') else None,
            'away_team_id': game.away_team_id if hasattr(game, 'away_team_id') else None,
            'home_conference': game.home_conference if hasattr(game, 'home_conference') else None,
            'away_conference': game.away_conference if hasattr(game, 'away_conference') else None,
            'home_score': game.home_points if hasattr(game, 'home_points') else None,
            'away_score': game.away_points if hasattr(game, 'away_points') else None,
            'venue': game.venue if hasattr(game, 'venue') else None,
            'status': game.status if hasattr(game, 'status') else None,
            'tournament': game.tournament if hasattr(game, 'tournament') else None,
            'season_type': str(game.season_type) if hasattr(game, 'season_type') else None,
        }
    
    def _team_stats_to_dict(self, stats) -> Dict:
        """Convert team stats object to dictionary with advanced metrics"""
        games = stats.games if hasattr(stats, 'games') and stats.games else 1  # Avoid division by zero
        
        # Extract team stats
        team_stats = stats.team_stats if hasattr(stats, 'team_stats') else None
        opponent_stats = stats.opponent_stats if hasattr(stats, 'opponent_stats') else None
        
        # Calculate per-game stats (keep for compatibility)
        ppg = 0
        opp_ppg = 0
        fg_pct = 0
        three_pct = 0
        ft_pct = 0
        rpg = 0
        apg = 0
        topg = 0
        spg = 0
        bpg = 0
        
        # ADVANCED METRICS (NEW!)
        offensive_rating = 0
        defensive_rating = 0
        true_shooting_pct = 0
        pace = 0
        possessions = 0
        
        # Four Factors
        effective_fg_pct = 0
        turnover_ratio = 0
        offensive_rebound_pct = 0
        free_throw_rate = 0
        
        # Opponent Four Factors
        opp_effective_fg_pct = 0
        opp_turnover_ratio = 0
        opp_offensive_rebound_pct = 0
        opp_free_throw_rate = 0
        
        if team_stats:
            ppg = team_stats.points.total / games if hasattr(team_stats, 'points') and team_stats.points else 0
            fg_pct = team_stats.field_goals.pct / 100 if hasattr(team_stats, 'field_goals') and team_stats.field_goals else 0
            three_pct = team_stats.three_point_field_goals.pct / 100 if hasattr(team_stats, 'three_point_field_goals') and team_stats.three_point_field_goals else 0
            ft_pct = team_stats.free_throws.pct / 100 if hasattr(team_stats, 'free_throws') and team_stats.free_throws else 0
            rpg = team_stats.rebounds.total / games if hasattr(team_stats, 'rebounds') and team_stats.rebounds else 0
            apg = team_stats.assists / games if hasattr(team_stats, 'assists') else 0
            topg = team_stats.turnovers.total / games if hasattr(team_stats, 'turnovers') and team_stats.turnovers else 0
            spg = team_stats.steals / games if hasattr(team_stats, 'steals') else 0
            bpg = team_stats.blocks / games if hasattr(team_stats, 'blocks') else 0
            
            # Extract advanced metrics from API
            offensive_rating = team_stats.rating if hasattr(team_stats, 'rating') else 0
            true_shooting_pct = team_stats.true_shooting / 100 if hasattr(team_stats, 'true_shooting') else 0
            possessions = team_stats.possessions / games if hasattr(team_stats, 'possessions') else 0
            
            # Extract Four Factors
            if hasattr(team_stats, 'four_factors') and team_stats.four_factors:
                ff = team_stats.four_factors
                effective_fg_pct = ff.effective_field_goal_pct / 100 if hasattr(ff, 'effective_field_goal_pct') else 0
                turnover_ratio = ff.turnover_ratio / 100 if hasattr(ff, 'turnover_ratio') else 0
                offensive_rebound_pct = ff.offensive_rebound_pct / 100 if hasattr(ff, 'offensive_rebound_pct') else 0
                free_throw_rate = ff.free_throw_rate / 100 if hasattr(ff, 'free_throw_rate') else 0
        
        if opponent_stats:
            opp_ppg = opponent_stats.points.total / games if hasattr(opponent_stats, 'points') and opponent_stats.points else 0
            defensive_rating = opponent_stats.rating if hasattr(opponent_stats, 'rating') else 0
            
            # Extract opponent Four Factors (for defensive analysis)
            if hasattr(opponent_stats, 'four_factors') and opponent_stats.four_factors:
                opp_ff = opponent_stats.four_factors
                opp_effective_fg_pct = opp_ff.effective_field_goal_pct / 100 if hasattr(opp_ff, 'effective_field_goal_pct') else 0
                opp_turnover_ratio = opp_ff.turnover_ratio / 100 if hasattr(opp_ff, 'turnover_ratio') else 0
                opp_offensive_rebound_pct = opp_ff.offensive_rebound_pct / 100 if hasattr(opp_ff, 'offensive_rebound_pct') else 0
                opp_free_throw_rate = opp_ff.free_throw_rate / 100 if hasattr(opp_ff, 'free_throw_rate') else 0
        
        # Extract pace (possessions per game)
        pace = stats.pace if hasattr(stats, 'pace') else possessions
        
        return {
            'team_id': stats.team_id if hasattr(stats, 'team_id') else None,
            'team': stats.team if hasattr(stats, 'team') else None,
            'games': games,
            # Basic stats (for compatibility)
            'points_per_game': ppg,
            'opponent_points_per_game': opp_ppg,
            'field_goal_percentage': fg_pct,
            'three_point_percentage': three_pct,
            'free_throw_percentage': ft_pct,
            'rebounds_per_game': rpg,
            'assists_per_game': apg,
            'turnovers_per_game': topg,
            'steals_per_game': spg,
            'blocks_per_game': bpg,
            # ADVANCED METRICS
            'offensive_rating': offensive_rating,  # Points per 100 possessions
            'defensive_rating': defensive_rating,  # Points allowed per 100 possessions
            'true_shooting_pct': true_shooting_pct,
            'pace': pace,  # Possessions per game
            'possessions': possessions,
            # Four Factors (Offensive)
            'effective_fg_pct': effective_fg_pct,
            'turnover_ratio': turnover_ratio,
            'offensive_rebound_pct': offensive_rebound_pct,
            'free_throw_rate': free_throw_rate,
            # Four Factors (Defensive - what opponents do)
            'opp_effective_fg_pct': opp_effective_fg_pct,
            'opp_turnover_ratio': opp_turnover_ratio,
            'opp_offensive_rebound_pct': opp_offensive_rebound_pct,
            'opp_free_throw_rate': opp_free_throw_rate,
        }
    
    def _line_to_dict(self, line, team_name: str) -> Dict:
        """Convert line object to dictionary"""
        odds_dict = {
            'spread': {},
            'total': {},
            'moneyline': {}
        }
        
        # Determine if team is home or away
        is_home = (hasattr(line, 'home_team') and line.home_team == team_name)
        
        if hasattr(line, 'lines') and line.lines:
            for l in line.lines:
                # Extract spread
                if hasattr(l, 'spread') and l.spread is not None:
                    spread_value = float(l.spread) if is_home else -float(l.spread)
                    odds_dict['spread'] = {
                        'home_spread': float(l.spread) if hasattr(l, 'spread') else 0,
                        'away_spread': -float(l.spread) if hasattr(l, 'spread') else 0,
                        'home_odds': -110,  # Default odds
                        'away_odds': -110,
                    }
                
                # Extract total
                if hasattr(l, 'over_under') and l.over_under is not None:
                    odds_dict['total'] = {
                        'line': float(l.over_under),
                        'over_odds': -110,
                        'under_odds': -110,
                    }
                
                # Extract moneyline
                if hasattr(l, 'home_moneyline') and hasattr(l, 'away_moneyline'):
                    odds_dict['moneyline'] = {
                        'home_odds': int(l.home_moneyline) if l.home_moneyline else -110,
                        'away_odds': int(l.away_moneyline) if l.away_moneyline else -110,
                    }
        
        return odds_dict
    
    def _player_to_dict(self, player) -> Dict:
        """Convert player object to dictionary"""
        return {
            'id': player.id if hasattr(player, 'id') else None,
            'name': player.name if hasattr(player, 'name') else '',
            'position': player.position if hasattr(player, 'position') else '',
            'height': player.height if hasattr(player, 'height') else '',
            'weight': player.weight if hasattr(player, 'weight') else '',
            'year': player.year if hasattr(player, 'year') else '',
        }
