"""
Prediction model for NCAAM basketball betting
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Optional
from api_client import CollegeBasketballAPI


class BasketballPredictionModel:
    """
    Statistical model for predicting basketball game outcomes
    """
    
    # Conference tiers for early-season adjustments
    CONFERENCE_TIERS = {
        # Tier 1: Elite Power 5
        'Big Ten': 1,
        'SEC': 1,
        'Big 12': 1,
        'ACC': 1,
        
        # Tier 2: Strong conferences
        'Big East': 2,
        'Pac-12': 2,
        
        # Tier 3: Mid-major elite
        'Mountain West': 3,
        'Atlantic 10': 3,
        'West Coast': 3,
        'American Athletic': 3,
        
        # Tier 4: Strong mid-major
        'Missouri Valley': 4,
        'Conference USA': 4,
        'Sun Belt': 4,
        'Mid-American': 4,
        'MAC': 4,
        
        # Tier 5: Lower mid-major
        'Horizon': 5,
        'WAC': 5,
        'Big West': 5,
        'Big Sky': 5,
        'Summit': 5,
        'Southern': 5,
        'Colonial': 5,
        'America East': 5,
        
        # Tier 6: Low-major
        'Southland': 6,
        'Ohio Valley': 6,
        'MAAC': 6,
        'Northeast': 6,
        'Patriot': 6,
        'Atlantic Sun': 6,
        'Big South': 6,
        'SWAC': 6,
        'MEAC': 6,
    }
    
    def __init__(self, api_client: CollegeBasketballAPI):
        """
        Initialize the prediction model
        
        Args:
            api_client: Instance of CollegeBasketballAPI
        """
        self.api = api_client
    
    def calculate_team_metrics(self, team_stats: Dict) -> Dict[str, float]:
        """
        Calculate advanced metrics from team stats
        
        Args:
            team_stats: Team statistics dictionary
            
        Returns:
            Dictionary of calculated metrics
        """
        metrics = {}
        
        # Extract basic stats (with safe defaults)
        ppg = team_stats.get('points_per_game', 0)
        opp_ppg = team_stats.get('opponent_points_per_game', 0)
        fg_pct = team_stats.get('field_goal_percentage', 0)
        three_pt_pct = team_stats.get('three_point_percentage', 0)
        ft_pct = team_stats.get('free_throw_percentage', 0)
        rebounds_pg = team_stats.get('rebounds_per_game', 0)
        assists_pg = team_stats.get('assists_per_game', 0)
        turnovers_pg = team_stats.get('turnovers_per_game', 0)
        steals_pg = team_stats.get('steals_per_game', 0)
        blocks_pg = team_stats.get('blocks_per_game', 0)
        
        # ADVANCED METRICS from API (tempo-free)
        # Use API efficiency ratings (points per 100 possessions) if available
        # Otherwise fall back to raw PPG
        metrics['offensive_rating'] = team_stats.get('offensive_rating', ppg)
        metrics['defensive_rating'] = team_stats.get('defensive_rating', opp_ppg)
        metrics['net_rating'] = metrics['offensive_rating'] - metrics['defensive_rating']
        
        # Use True Shooting % if available (better than weighted FG%)
        metrics['true_shooting_pct'] = team_stats.get('true_shooting_pct', 0)
        if metrics['true_shooting_pct'] == 0:
            # Fallback to old calculation
            metrics['shooting_efficiency'] = (fg_pct * 0.5 + three_pt_pct * 0.3 + ft_pct * 0.2) if fg_pct else 0
        else:
            metrics['shooting_efficiency'] = metrics['true_shooting_pct']
        
        # FOUR FACTORS (The 4 most important basketball metrics)
        metrics['effective_fg_pct'] = team_stats.get('effective_fg_pct', fg_pct)
        metrics['turnover_ratio'] = team_stats.get('turnover_ratio', 0)
        metrics['offensive_rebound_pct'] = team_stats.get('offensive_rebound_pct', 0)
        metrics['free_throw_rate'] = team_stats.get('free_throw_rate', 0)
        
        # Opponent Four Factors (defensive strength)
        metrics['opp_effective_fg_pct'] = team_stats.get('opp_effective_fg_pct', 0)
        metrics['opp_turnover_ratio'] = team_stats.get('opp_turnover_ratio', 0)
        metrics['opp_offensive_rebound_pct'] = team_stats.get('opp_offensive_rebound_pct', 0)
        metrics['opp_free_throw_rate'] = team_stats.get('opp_free_throw_rate', 0)
        
        # Legacy metrics (keep for backward compatibility)
        metrics['rebound_rate'] = rebounds_pg
        metrics['assist_to_turnover'] = assists_pg / turnovers_pg if turnovers_pg > 0 else 0
        metrics['defensive_intensity'] = steals_pg + blocks_pg
        
        # Actual pace (possessions per game) from API
        metrics['pace'] = team_stats.get('pace', ppg + opp_ppg)  # Fallback to estimate
        
        return metrics
    
    def get_adaptive_regression_weight(self, home_stats: Dict, away_stats: Dict, 
                                        home_recent: List, away_recent: List,
                                        game_info: Optional[Dict] = None) -> float:
        """
        Calculate regression weight that adapts to season progress and talent gaps
        
        Returns higher weight (more trust) when:
        - More games have been played
        - Larger talent gap between teams (obvious mismatches)
        - Market spread suggests mismatch (even if ratings don't show it yet)
        
        Args:
            home_stats: Home team statistics
            away_stats: Away team statistics
            home_recent: Home team recent games
            away_recent: Away team recent games
            game_info: Optional game information (can include market odds)
            
        Returns:
            float: Weight to apply to actual ratings (0.75-0.99)
        """
        # Get actual games played from team stats (more accurate than recent games list)
        home_games = home_stats.get('games', len(home_recent))
        away_games = away_stats.get('games', len(away_recent))
        avg_games = (home_games + away_games) / 2
        
        # Base regression curve (smooth progression, not hard breakpoints)
        # This creates a natural learning curve as season progresses
        if avg_games <= 5:
            base_weight = 0.75 + (avg_games / 5) * 0.10  # 75% -> 85%
        elif avg_games <= 10:
            base_weight = 0.85 + ((avg_games - 5) / 5) * 0.07  # 85% -> 92%
        elif avg_games <= 20:
            base_weight = 0.92 + ((avg_games - 10) / 10) * 0.05  # 92% -> 97%
        else:
            base_weight = 0.97 + min((avg_games - 20) / 20, 1.0) * 0.02  # 97% -> 99%
        
        # Talent gap adjustment: Trust ratings more for obvious mismatches
        home_metrics = self.calculate_team_metrics(home_stats)
        away_metrics = self.calculate_team_metrics(away_stats)
        
        # Check multiple gap indicators (use maximum to catch mismatches)
        net_rating_gap = abs(home_metrics['net_rating'] - away_metrics['net_rating'])
        off_rating_gap = abs(home_metrics['offensive_rating'] - away_metrics['offensive_rating'])
        def_rating_gap = abs(home_metrics['defensive_rating'] - away_metrics['defensive_rating'])
        
        # Use the maximum gap found across different metrics
        # Weight offensive/defensive gaps at 70% since they're more specific
        # This catches cases where one side shows the mismatch clearly
        max_gap = max(net_rating_gap, off_rating_gap * 0.7, def_rating_gap * 0.7)
        
        # Bigger gaps = less regression needed (even early season)
        if max_gap > 30:
            talent_boost = 0.10  # Huge gap (elite vs bottom tier)
        elif max_gap > 20:
            talent_boost = 0.07  # Big gap (Power 5 vs mid-major)
        elif max_gap > 15:
            talent_boost = 0.04  # Moderate gap
        else:
            talent_boost = 0.00  # Similar teams - use base regression
        
        # Early season safety: if net rating gap is small BUT teams have very different
        # win/loss records, add extra boost (catches cases where ratings haven't stabilized)
        home_wins = home_stats.get('wins', 0)
        away_wins = away_stats.get('wins', 0)
        home_losses = home_stats.get('losses', 0)
        away_losses = away_stats.get('losses', 0)
        
        # Only apply if we have enough games to judge
        if home_games >= 2 and away_games >= 2:
            home_win_pct = home_wins / max(1, home_games)
            away_win_pct = away_wins / max(1, away_games)
            win_pct_gap = abs(home_win_pct - away_win_pct)
            
            # If win % gap is large but net rating gap is small, add boost
            # This catches early season where one team is clearly dominant
            if win_pct_gap > 0.6 and net_rating_gap < 15:
                talent_boost = max(talent_boost, 0.06)  # At least 6% boost
        
        # Conference tier adjustment: Trust more for cross-conference mismatches
        # This is critical early season when ratings haven't stabilized
        conference_boost = 0.0
        if game_info and avg_games < 10:  # Only apply in first ~10 games
            home_conf = game_info.get('home_conference', '')
            away_conf = game_info.get('away_conference', '')
            
            home_tier = self.CONFERENCE_TIERS.get(home_conf, 7)  # Default to tier 7 (unknown)
            away_tier = self.CONFERENCE_TIERS.get(away_conf, 7)
            
            tier_gap = abs(home_tier - away_tier)
            
            # Apply boost based on conference tier mismatch
            # Larger tier gap = more trust in the better conference team
            if tier_gap >= 3:  # e.g., Big Ten (1) vs MAC (4) or worse
                conference_boost = 0.12  # Trust ratings 12% more
            elif tier_gap >= 2:  # e.g., Big Ten (1) vs Mountain West (3)
                conference_boost = 0.08  # Trust ratings 8% more
            elif tier_gap >= 1:  # e.g., Big Ten (1) vs Big East (2)
                conference_boost = 0.04  # Trust ratings 4% more
            
            # Scale down conference boost as season progresses (by game 10, no boost)
            conference_boost *= (10 - avg_games) / 10
            
            # Use max of talent boost and conference boost (don't double-count)
            talent_boost = max(talent_boost, conference_boost)
        
        # Final weight (capped at 99% to always maintain some regression)
        final_weight = min(0.99, base_weight + talent_boost)
        
        return final_weight
    
    def analyze_recent_form(self, recent_games: List[Dict], team_id: int) -> Dict[str, float]:
        """
        Analyze recent form/momentum
        
        Args:
            recent_games: List of recent game dictionaries
            team_id: Team ID to analyze
            
        Returns:
            Dictionary of form metrics
        """
        if not recent_games:
            return {
                'win_rate': 0.5,
                'avg_margin': 0,
                'scoring_trend': 0,
                'consistency': 0.3  # Low confidence with no data
            }
        
        results = []
        margins = []
        scores = []
        
        for game in recent_games:
            home_score = game.get('home_score', 0)
            away_score = game.get('away_score', 0)
            home_id = game.get('home_team_id')
            
            is_home = (home_id == team_id)
            team_score = home_score if is_home else away_score
            opp_score = away_score if is_home else home_score
            
            margin = team_score - opp_score
            won = margin > 0
            
            results.append(won)
            margins.append(margin)
            scores.append(team_score)
        
        # Calculate metrics
        win_rate = sum(results) / len(results) if results else 0.5
        avg_margin = np.mean(margins) if margins else 0
        
        # Scoring trend (weighted more recent)
        weights = np.linspace(0.5, 1.0, len(scores))
        scoring_trend = np.average(scores, weights=weights) if scores else 0
        
        # Consistency score based on:
        # 1. Sample size (more games = more confident) - BUT BE STRICTER
        # 2. Variance (lower variance = more consistent = more confident)
        # 3. Game quality (blowouts vs close games)
        
        num_games = len(margins)
        
        # Much stricter sample size requirements
        if num_games <= 2:
            sample_size_factor = 0.3  # Very low confidence with 2 or fewer games
        elif num_games <= 5:
            sample_size_factor = 0.4 + (num_games - 2) * 0.05  # Gradual increase: 40-55%
        elif num_games <= 10:
            sample_size_factor = 0.55 + (num_games - 5) * 0.04  # 55-75%
        else:
            sample_size_factor = min(0.75 + (num_games - 10) * 0.02, 0.90)  # Max 90%
        
        # Variance factor with more realistic thresholds
        if len(margins) > 1:
            margin_std = np.std(margins)
            # College basketball typical std is 10-20 points
            # Excellent consistency: std < 8 = 0.75
            # Good: std 8-12 = 0.6-0.75
            # Average: std 12-18 = 0.45-0.6
            # Poor: std > 18 = 0.3-0.45
            if margin_std < 8:
                variance_factor = 0.75 - (margin_std / 20)
            elif margin_std < 12:
                variance_factor = 0.6 + (12 - margin_std) / 40
            elif margin_std < 18:
                variance_factor = 0.45 + (18 - margin_std) / 60
            else:
                variance_factor = max(0.3, 0.45 - (margin_std - 18) / 100)
        else:
            variance_factor = 0.4  # Low confidence with only 1 game
        
        # Quality factor - penalize if results are too inconsistent
        if len(margins) >= 3:
            # Check for big swings (winning big then losing big = unreliable)
            max_margin = max(margins)
            min_margin = min(margins)
            swing = max_margin - min_margin
            if swing > 40:  # Big swings reduce confidence
                quality_factor = max(0.3, 1 - (swing - 40) / 100)
            else:
                quality_factor = 0.8
        else:
            quality_factor = 0.5
        
        # Combine factors with weights
        consistency = (sample_size_factor * 0.5 + variance_factor * 0.3 + quality_factor * 0.2)
        consistency = round(max(0.25, min(0.85, consistency)), 3)  # Between 25% and 85%
        
        return {
            'win_rate': win_rate,
            'avg_margin': avg_margin,
            'scoring_trend': scoring_trend,
            'consistency': consistency
        }
    
    def predict_spread(self, home_team_id: int, away_team_id: int, 
                       game_info: Optional[Dict] = None) -> Tuple[float, float]:
        """
        Predict the spread for a game using projected score methodology
        (Similar to KenPom/Haslametrics tempo-free approach)
        
        Args:
            home_team_id: Home team ID
            away_team_id: Away team ID
            game_info: Optional game information dictionary
            
        Returns:
            Tuple of (predicted_spread, confidence) where positive means home team favored
        """
        # Get team stats
        home_stats = self.api.get_team_stats(home_team_id)
        away_stats = self.api.get_team_stats(away_team_id)
        
        # Get recent games
        home_recent = self.api.get_recent_games(home_team_id, limit=10)
        away_recent = self.api.get_recent_games(away_team_id, limit=10)
        
        # Calculate metrics
        home_metrics = self.calculate_team_metrics(home_stats)
        away_metrics = self.calculate_team_metrics(away_stats)
        
        home_form = self.analyze_recent_form(home_recent, home_team_id)
        away_form = self.analyze_recent_form(away_recent, away_team_id)
        
        num_games = len(home_recent) + len(away_recent)
        
        # ========== TEMPO-FREE PROJECTED SCORE APPROACH ==========
        # This is more stable and realistic than spread-based predictions
        
        # Step 1: Calculate expected game pace (possessions per game)
        # Validate and use pace (with sanity checks for bad data)
        def validate_pace(pace, default=70.0, min_val=55.0, max_val=85.0):
            """Validate pace is within reasonable bounds"""
            if pace <= 0 or pace < min_val or pace > max_val:
                return default
            return pace
        
        home_pace = validate_pace(home_metrics['pace'])
        away_pace = validate_pace(away_metrics['pace'])
        game_pace = (home_pace * 0.55 + away_pace * 0.45)  # Home pace slightly more influential
        
        # Step 2: Calculate offensive efficiency expectations (points per 100 possessions)
        # Add sanity checks for bad API data
        def validate_rating(rating, default=100.0, min_val=60.0, max_val=180.0):
            """Validate efficiency rating is within reasonable bounds"""
            # Allow higher max for elite teams (was 140, now 180)
            if rating <= 0 or rating < min_val or rating > max_val:
                return default
            return rating
        
        def validate_pace(pace, default=70.0, min_val=55.0, max_val=85.0):
            """Validate pace is within reasonable bounds"""
            if pace <= 0 or pace < min_val or pace > max_val:
                return default
            return pace
        
        home_off_rating = validate_rating(home_metrics['offensive_rating'])
        away_def_rating = validate_rating(away_metrics['defensive_rating'])
        away_off_rating = validate_rating(away_metrics['offensive_rating'])
        home_def_rating = validate_rating(home_metrics['defensive_rating'])
        
        # Apply adaptive regression based on season progress and talent gap
        # This automatically adjusts: less regression for mismatches, more games = more trust
        base_regression_weight = self.get_adaptive_regression_weight(
            home_stats, away_stats, home_recent, away_recent, game_info
        )
        
        # Safety check: Apply extra regression for unreliable early-season data
        # If teams have 0-0 or 1-0 records with only 2-3 games, data is very unstable
        home_wins = home_stats.get('wins', 0)
        home_losses = home_stats.get('losses', 0)
        away_wins = away_stats.get('wins', 0)
        away_losses = away_stats.get('losses', 0)
        home_games = home_stats.get('games', 0)
        away_games = away_stats.get('games', 0)
        
        # Check for suspicious data (games played but no W/L recorded = exhibitions/bad data)
        home_unreliable = (home_games > 0 and home_wins + home_losses == 0)
        away_unreliable = (away_games > 0 and away_wins + away_losses == 0)
        
        if (home_unreliable or away_unreliable) and (home_games + away_games < 6):
            # Very unreliable data: apply heavy regression
            regression_weight = base_regression_weight * 0.60  # Only trust ratings 60%
        elif home_games + away_games < 4:
            # Extremely limited data: more regression
            regression_weight = base_regression_weight * 0.80  # Only trust ratings 80%
        else:
            regression_weight = base_regression_weight
        
        league_avg = 100.0
        home_off_adj = home_off_rating * regression_weight + league_avg * (1 - regression_weight)
        away_def_adj = away_def_rating * regression_weight + league_avg * (1 - regression_weight)
        away_off_adj = away_off_rating * regression_weight + league_avg * (1 - regression_weight)
        home_def_adj = home_def_rating * regression_weight + league_avg * (1 - regression_weight)
        
        # Calculate expected efficiency using proper formula:
        # Team's expected efficiency = their offense adjusted by opponent's defensive strength
        # LOWER defensive rating = BETTER defense = HURTS opponent offense
        # If opponent has 84 def (16 better than avg 100), offense is HURT: offense + (84-100) = offense - 16
        # If opponent has 110 def (10 worse than avg 100), offense is HELPED: offense + (110-100) = offense + 10
        home_expected_eff = home_off_adj + (away_def_adj - league_avg)
        away_expected_eff = away_off_adj + (home_def_adj - league_avg)
        
        # Step 3: Add home court advantage (typically 3-4 points per 100 possessions)
        home_court_boost = 3.5  # Efficiency points per 100 possessions
        home_expected_eff += home_court_boost
        
        # Step 4: Minor adjustment for recent form
        form_adjustment = (home_form['avg_margin'] - away_form['avg_margin']) * 0.10
        form_adjustment = max(-5, min(5, form_adjustment))  # Cap at ±5 points
        
        # Step 5: Calculate projected scores
        home_projected = (home_expected_eff * game_pace) / 100
        away_projected = (away_expected_eff * game_pace) / 100
        
        # Apply form adjustment
        predicted_spread = (home_projected - away_projected) + form_adjustment
        
        # Market adjustment for mismatches - trust the market when model underestimates
        # This is KEY to avoiding betting underdogs in blowouts
        if game_info and num_games < 15:  # Apply through most of early season
            # Get market spread from odds if available
            odds_data = game_info.get('odds', {})
            spread_data = odds_data.get('spread', {})
            market_spread = spread_data.get('home_spread') if isinstance(spread_data, dict) else None
            
            if market_spread is not None:
                # Determine which team the market favors
                # Negative market_spread means home team is favored
                market_fav_home = market_spread < 0
                model_fav_home = predicted_spread > 0
                
                # Market spread magnitude (always positive)
                market_mag = abs(market_spread)
                model_mag = abs(predicted_spread)
                
                # Only adjust if we agree on favorite but differ in magnitude
                if market_fav_home == model_fav_home:
                    gap = market_mag - model_mag
                    
                    # If market says bigger spread, blend toward market
                    # Lowered threshold from 10 to 5 points
                    if gap > 5:  # Market is 5+ points more extreme
                        # Scale by games played
                        games_factor = max(0.3, (15 - num_games) / 15)  # 0.3-1.0 range
                        
                        # MORE AGGRESSIVE blending for big spreads
                        # The model consistently underestimates blowouts
                        if market_mag >= 25:
                            # Extreme mismatch (25+ point spread): trust market heavily
                            blend_factor = 0.70 + (games_factor * 0.20)  # 70-90%
                        elif market_mag >= 20:
                            # Big mismatch (20+ point spread): trust market significantly
                            blend_factor = 0.60 + (games_factor * 0.20)  # 60-80%
                        elif market_mag >= 15:
                            # Moderate mismatch: trust market moderately
                            blend_factor = 0.50 + (games_factor * 0.15)  # 50-65%
                        else:
                            # Smaller spreads: conservative blend
                            blend_factor = 0.40 + (games_factor * 0.10)  # 40-50%
                        
                        adjustment = gap * blend_factor
                        # Apply adjustment in the correct direction
                        # If home is favored by market, increase home's advantage (more positive spread)
                        if market_fav_home:
                            predicted_spread += adjustment  # More positive (home favored more)
                        else:
                            predicted_spread -= adjustment  # More negative (away favored more)
        
        # Sanity bounds (but much more generous than before)
        predicted_spread = max(-50, min(50, predicted_spread))
        
        # Calculate confidence based on data quality
        base_confidence = (home_form['consistency'] + away_form['consistency']) / 2
        confidence = max(0.40, base_confidence)
        
        # Light adjustment for very small samples
        if num_games < 4:
            confidence *= 0.90
        elif num_games < 8:
            confidence *= 0.95
        
        # Slight penalty for extreme spreads (volatility increases)
        if abs(predicted_spread) > 30:
            confidence *= 0.85
        elif abs(predicted_spread) > 20:
            confidence *= 0.92
        elif abs(predicted_spread) > 15:
            confidence *= 0.96
        
        # Cap maximum confidence
        confidence = min(confidence, 0.85)
        
        return round(predicted_spread, 1), round(confidence, 3)
    
    def predict_total(self, home_team_id: int, away_team_id: int,
                     game_info: Optional[Dict] = None) -> Tuple[float, float]:
        """
        Predict the total points for a game using projected score methodology
        (Matches the spread prediction approach for consistency)
        
        Args:
            home_team_id: Home team ID
            away_team_id: Away team ID
            game_info: Optional game information dictionary
            
        Returns:
            Tuple of (predicted_total, confidence)
        """
        # Get team stats
        home_stats = self.api.get_team_stats(home_team_id)
        away_stats = self.api.get_team_stats(away_team_id)
        
        # Get recent games
        home_recent = self.api.get_recent_games(home_team_id, limit=10)
        away_recent = self.api.get_recent_games(away_team_id, limit=10)
        
        # Calculate metrics
        home_metrics = self.calculate_team_metrics(home_stats)
        away_metrics = self.calculate_team_metrics(away_stats)
        
        home_form = self.analyze_recent_form(home_recent, home_team_id)
        away_form = self.analyze_recent_form(away_recent, away_team_id)
        
        num_games = len(home_recent) + len(away_recent)
        
        # ========== USE SAME APPROACH AS SPREAD PREDICTION ==========
        # This ensures consistency between spread and total predictions
        
        # Step 1: Calculate expected game pace (with validation)
        def validate_rating(rating, default=100.0, min_val=60.0, max_val=180.0):
            """Validate efficiency rating is within reasonable bounds"""
            # Allow higher max for elite teams (was 140, now 180)
            if rating <= 0 or rating < min_val or rating > max_val:
                return default
            return rating
        
        def validate_pace(pace, default=70.0, min_val=55.0, max_val=85.0):
            """Validate pace is within reasonable bounds"""
            if pace <= 0 or pace < min_val or pace > max_val:
                return default
            return pace
        
        home_pace = validate_pace(home_metrics['pace'])
        away_pace = validate_pace(away_metrics['pace'])
        game_pace = (home_pace * 0.55 + away_pace * 0.45)
        
        # Step 2: Get offensive and defensive efficiency ratings (with validation)
        home_off_rating = validate_rating(home_metrics['offensive_rating'])
        away_def_rating = validate_rating(away_metrics['defensive_rating'])
        away_off_rating = validate_rating(away_metrics['offensive_rating'])
        home_def_rating = validate_rating(home_metrics['defensive_rating'])
        
        # Use same adaptive regression as spread prediction
        regression_weight = self.get_adaptive_regression_weight(
            home_stats, away_stats, home_recent, away_recent, game_info
        )
        
        league_avg = 100.0
        home_off_adj = home_off_rating * regression_weight + league_avg * (1 - regression_weight)
        away_def_adj = away_def_rating * regression_weight + league_avg * (1 - regression_weight)
        away_off_adj = away_off_rating * regression_weight + league_avg * (1 - regression_weight)
        home_def_adj = home_def_rating * regression_weight + league_avg * (1 - regression_weight)
        
        # Step 3: Calculate expected efficiency (same formula as spread)
        home_expected_eff = home_off_adj + (away_def_adj - league_avg)
        away_expected_eff = away_off_adj + (home_def_adj - league_avg)
        
        # Home court advantage (in efficiency)
        home_court_boost = 3.5
        home_expected_eff += home_court_boost
        
        # Step 4: Calculate projected scores
        home_projected = (home_expected_eff * game_pace) / 100
        away_projected = (away_expected_eff * game_pace) / 100
        
        # Total = sum of both projected scores
        predicted_total = home_projected + away_projected
        
        # Apply early-season adjustment for totals
        # Early season games tend to score less due to: rust, new lineups, learning systems
        from datetime import datetime
        if game_info and 'start_date' in game_info:
            try:
                start_date_str = game_info['start_date']
                if isinstance(start_date_str, str):
                    game_date = datetime.fromisoformat(start_date_str.split('T')[0].replace('Z', ''))
                    month = game_date.month
                    day = game_date.day
                    
                    # November: Apply 5% reduction (games score less early in season)
                    if month == 11:
                        predicted_total *= 0.95  # Reduce by 5%
                    # Early December (first 2 weeks): Apply 3% reduction
                    elif month == 12 and day <= 14:
                        predicted_total *= 0.97  # Reduce by 3%
                    # Mid-December through rest of season: No adjustment
                    # (by then, teams have found their rhythm)
            except:
                pass  # If we can't parse the date, skip the adjustment
        
        # Sanity bounds
        predicted_total = max(110, min(200, predicted_total))
        
        # Calculate confidence (similar to spread approach)
        base_confidence = (home_form['consistency'] + away_form['consistency']) / 2
        confidence = max(0.35, base_confidence)  # Minimum 35% confidence for totals
        
        # Light adjustment for very small samples
        if num_games < 4:
            confidence *= 0.88  # Slightly more penalty than spreads (totals are harder)
        elif num_games < 8:
            confidence *= 0.94
        
        # Penalty for extreme totals (far from average ~142)
        league_avg_total = 142
        total_deviation = abs(predicted_total - league_avg_total)
        if total_deviation > 30:
            confidence *= 0.80  # Big deviation from normal
        elif total_deviation > 20:
            confidence *= 0.88
        elif total_deviation > 15:
            confidence *= 0.94
        
        # Penalize if pace difference is large (makes total more unpredictable)
        pace_diff = abs(home_pace - away_pace)
        if pace_diff > 15:
            confidence *= 0.90
        
        # Totals are inherently slightly harder to predict than spreads
        confidence *= 0.92
        
        # Cap maximum confidence at 75% for totals
        confidence = max(0.35, min(0.75, confidence))
        
        return round(predicted_total, 1), round(confidence, 3)
    
    def calculate_win_probability(self, predicted_spread: float, confidence: float) -> float:
        """
        Calculate win probability from predicted spread and confidence
        
        Args:
            predicted_spread: Predicted point spread
            confidence: Confidence level (0-1)
            
        Returns:
            Win probability (0-1)
        """
        # Use a logistic function to convert spread to probability
        # Adjusted for college basketball where spreads are generally more volatile
        base_prob = 1 / (1 + np.exp(-predicted_spread / 7))
        
        # Adjust for confidence (pull towards 0.5 if less confident)
        adjusted_prob = 0.5 + (base_prob - 0.5) * confidence
        
        return round(adjusted_prob, 3)

