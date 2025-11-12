"""
Best bets selection logic
"""

from typing import List, Dict, Tuple
import numpy as np


def american_odds_to_probability(odds: int) -> float:
    """
    Convert American odds to implied probability
    
    Args:
        odds: American odds (e.g., -110, +150)
        
    Returns:
        Implied probability (0-1)
    """
    if odds < 0:
        return abs(odds) / (abs(odds) + 100)
    else:
        return 100 / (odds + 100)


def american_odds_to_decimal(odds: int) -> float:
    """
    Convert American odds to decimal odds
    
    Args:
        odds: American odds
        
    Returns:
        Decimal odds
    """
    if odds < 0:
        return 1 + (100 / abs(odds))
    else:
        return 1 + (odds / 100)


class BestBetsSelector:
    """
    Selects the best betting opportunities based on statistical likelihood
    """
    
    def __init__(self, max_odds: int = -125):
        """
        Initialize best bets selector
        
        Args:
            max_odds: Maximum odds to consider (e.g., -125 means -125 or better like -130, -150)
        """
        self.max_odds = max_odds
    
    def calculate_bet_score(self, predicted_prob: float, odds: int, 
                           confidence: float) -> float:
        """
        Calculate a score for ranking bets balancing win probability and model confidence
        
        Args:
            predicted_prob: Model's predicted probability of winning (0-1)
            odds: American odds for the bet
            confidence: Model confidence (0-1)
            
        Returns:
            Bet score (higher is better)
        """
        # Balance between bets likely to win AND bets we're confident in
        # 60% weight on win probability, 40% weight on model confidence
        
        # This ensures we're betting on the model's strongest convictions
        # while still considering the likelihood of cashing
        base_score = predicted_prob * 0.6
        confidence_score = confidence * 0.4
        
        # Slight penalty for very low odds (they tie up more bankroll)
        # But don't penalize too much since we're looking for likely winners
        implied_prob = american_odds_to_probability(odds)
        odds_factor = 1 - (implied_prob - 0.5) * 0.2  # Small adjustment
        
        # Final score
        score = (base_score + confidence_score) * odds_factor
        
        return round(score, 4)
    
    def meets_odds_criteria(self, odds: int) -> bool:
        """
        Check if odds meet the criteria (-125 or better)
        
        Args:
            odds: American odds
            
        Returns:
            True if odds are acceptable
        """
        # For negative odds, "better" means CLOSER to even money (less negative)
        # -110 is better than -125 (less risk to win same amount)
        # -150 is worse than -125 (more risk)
        # So -125 or better means odds >= -125 (e.g., -125, -120, -110, +100, etc.)
        if odds >= 0:
            return True  # All positive odds are better than any negative odds
        return odds >= self.max_odds  # For negative odds, higher (closer to 0) is better
    
    def select_best_bets(self, all_bets: List[Dict]) -> List[Dict]:
        """
        Select the top 5 best bets from all available options
        
        Args:
            all_bets: List of bet dictionaries with keys:
                - game_id: Game identifier
                - game_description: Description of the game
                - bet_type: Type of bet (spread, total, moneyline)
                - pick: The specific pick (e.g., "Team A -5.5", "Over 145.5")
                - odds: American odds
                - predicted_prob: Predicted probability of winning
                - confidence: Model confidence
                - reasoning: Why this bet was selected
                
        Returns:
            List of top 5 best bets, sorted by score
        """
        # Filter by odds criteria
        eligible_bets = [bet for bet in all_bets if self.meets_odds_criteria(bet['odds'])]
        
        # Calculate scores for each bet
        for bet in eligible_bets:
            bet['score'] = self.calculate_bet_score(
                bet['predicted_prob'],
                bet['odds'],
                bet['confidence']
            )
        
        # Sort by score (highest first)
        sorted_bets = sorted(eligible_bets, key=lambda x: x['score'], reverse=True)
        
        # Return top 5
        return sorted_bets[:5]
    
    def create_bet_from_prediction(self, game: Dict, prediction_type: str,
                                   prediction: float, confidence: float,
                                   odds_data: Dict) -> List[Dict]:
        """
        Create bet dictionaries from a prediction
        
        Args:
            game: Game information dictionary
            prediction_type: 'spread' or 'total'
            prediction: Predicted value
            confidence: Model confidence
            odds_data: Odds information from API
            
        Returns:
            List of bet dictionaries
        """
        bets = []
        
        home_team = game.get('home_team', 'Home')
        away_team = game.get('away_team', 'Away')
        game_desc = f"{away_team} @ {home_team}"
        
        if prediction_type == 'spread':
            # Predicted spread positive means home team favored
            market_spread = odds_data.get('spread', {})
            home_spread = market_spread.get('home_spread', 0)
            away_spread = market_spread.get('away_spread', 0)
            home_odds = market_spread.get('home_odds', -110)
            away_odds = market_spread.get('away_odds', -110)
            
            # Determine which side to bet based on prediction vs market
            edge = 0  # Track the edge for confidence adjustment
            
            if prediction > 0:  # Home team favored in prediction
                if prediction > abs(home_spread):  # Prediction more favorable than market
                    pick_team = home_team
                    pick_spread = home_spread
                    pick_odds = home_odds
                    edge = prediction - home_spread
                    win_prob = self._spread_to_probability(edge)
                else:
                    pick_team = away_team
                    pick_spread = away_spread
                    pick_odds = away_odds
                    edge = away_spread - prediction
                    win_prob = self._spread_to_probability(edge)
            else:  # Away team favored in prediction
                if abs(prediction) > abs(away_spread):
                    pick_team = away_team
                    pick_spread = away_spread
                    pick_odds = away_odds
                    edge = abs(prediction) - abs(away_spread)
                    win_prob = self._spread_to_probability(edge)
                else:
                    pick_team = home_team
                    pick_spread = home_spread
                    pick_odds = home_odds
                    edge = home_spread + abs(prediction)
                    win_prob = self._spread_to_probability(edge)
            
            # Adjust confidence based on edge size
            # Very large edges reduce confidence (extreme predictions are less reliable)
            adjusted_confidence = self._adjust_confidence_for_edge(confidence, edge, 'spread')
            
            # Create more specific reasoning
            if prediction > 0:
                reasoning = f"Model predicts {home_team} by {abs(prediction):.1f}"
            elif prediction < 0:
                reasoning = f"Model predicts {away_team} by {abs(prediction):.1f}"
            else:
                reasoning = f"Model predicts even game"
            
            bets.append({
                'game_id': game.get('id', ''),
                'game_description': game_desc,
                'bet_type': 'Spread',
                'pick': f"{pick_team} {pick_spread:+.1f}",
                'odds': pick_odds,
                'predicted_prob': win_prob,
                'confidence': adjusted_confidence,
                'reasoning': reasoning
            })
        
        elif prediction_type == 'total':
            market_total = odds_data.get('total', {})
            total_line = market_total.get('line', 140)
            over_odds = market_total.get('over_odds', -110)
            under_odds = market_total.get('under_odds', -110)
            
            # Determine over/under based on prediction vs market
            if prediction > total_line:
                pick = f"Over {total_line}"
                pick_odds = over_odds
                edge = prediction - total_line
                win_prob = self._total_to_probability(edge)
            else:
                pick = f"Under {total_line}"
                pick_odds = under_odds
                edge = total_line - prediction
                win_prob = self._total_to_probability(edge)
            
            # Adjust confidence based on edge size
            adjusted_confidence = self._adjust_confidence_for_edge(confidence, edge, 'total')
            
            # Create more specific reasoning for total
            if prediction > total_line:
                reasoning = f"Model predicts {prediction:.1f} (Over {total_line:.1f} by {edge:.1f})"
            else:
                reasoning = f"Model predicts {prediction:.1f} (Under {total_line:.1f} by {edge:.1f})"
            
            bets.append({
                'game_id': game.get('id', ''),
                'game_description': game_desc,
                'bet_type': 'Total',
                'pick': pick,
                'odds': pick_odds,
                'predicted_prob': win_prob,
                'confidence': adjusted_confidence,
                'reasoning': reasoning
            })
        
        return bets
    
    def _adjust_confidence_for_edge(self, base_confidence: float, edge: float, bet_type: str) -> float:
        """
        Adjust confidence based on the size of the edge
        
        Very large edges suggest extreme predictions which are inherently less reliable
        Small to moderate edges maintain or slightly boost confidence
        
        Args:
            base_confidence: Base confidence from model (0-1)
            edge: Point differential between model and market
            bet_type: 'spread' or 'total'
            
        Returns:
            Adjusted confidence (0-1)
        """
        abs_edge = abs(edge)
        
        if bet_type == 'spread':
            # Spread confidence adjustments
            if abs_edge < 2:
                # Very small edge - slight confidence reduction (close call)
                adjustment = 0.95
            elif abs_edge < 5:
                # Small-medium edge - maintain confidence
                adjustment = 1.0
            elif abs_edge < 10:
                # Medium edge - slightly boost confidence
                adjustment = 1.05
            elif abs_edge < 15:
                # Large edge - maintain confidence but don't boost
                adjustment = 1.0
            elif abs_edge < 20:
                # Very large edge - reduce confidence (extreme prediction)
                adjustment = 0.92
            else:
                # Huge edge - significantly reduce confidence
                adjustment = 0.85
        
        else:  # total
            # Total confidence adjustments (more conservative)
            if abs_edge < 3:
                # Very small edge - reduce confidence (marginal call)
                adjustment = 0.92
            elif abs_edge < 7:
                # Small-medium edge - maintain confidence
                adjustment = 1.0
            elif abs_edge < 12:
                # Medium edge - slight boost
                adjustment = 1.03
            elif abs_edge < 18:
                # Large edge - reduce confidence
                adjustment = 0.94
            else:
                # Very large edge - significant reduction
                adjustment = 0.87
        
        adjusted = base_confidence * adjustment
        
        # Keep within reasonable bounds
        return round(max(0.25, min(0.88, adjusted)), 3)
    
    def _spread_to_probability(self, edge: float) -> float:
        """
        Convert point spread edge to a value rating
        
        IMPORTANT: This is NOT a true win probability! Spread bets are designed to be 50/50
        against the market. This represents how strongly the model disagrees with the market,
        scaled to a 50-70% range to reflect that the market is also sophisticated.
        
        Args:
            edge: Point differential edge (model prediction - market spread)
            
        Returns:
            Value rating (0.50-0.70) - model's conviction about edge
        """
        if abs(edge) < 0.5:
            return 0.50  # No edge
        
        # Conservative scaling that acknowledges market wisdom
        # Even 30-point disagreements only reach 70% "value rating"
        # This is more honest about spread betting reality
        
        if abs(edge) <= 5:
            prob = 0.50 + edge * 0.015  # 1.5% per point → 57.5% at 5 pts
        elif abs(edge) <= 10:
            base = 0.50 + 5 * 0.015  # 57.5% at 5 pts
            additional = (abs(edge) - 5) * 0.012  # 1.2% per point
            prob = base + (additional if edge > 0 else -additional)
        elif abs(edge) <= 20:
            base = 0.50 + 5 * 0.015 + 5 * 0.012  # 63.5% at 10 pts
            additional = (abs(edge) - 10) * 0.006  # 0.6% per point
            prob = base + (additional if edge > 0 else -additional)
        else:
            # Cap at 70% for extreme edges - market is rarely that wrong
            base = 0.50 + 5 * 0.015 + 5 * 0.012 + 10 * 0.006  # 69.5% at 20 pts
            additional = min((abs(edge) - 20) * 0.001, 0.005)  # Minimal increase, max 70%
            prob = base + (additional if edge > 0 else -additional)
        
        # Realistic bounds: 50-70% range
        return max(0.50, min(0.70, prob))
    
    def _total_to_probability(self, edge: float) -> float:
        """
        Convert total points edge to a value rating
        
        IMPORTANT: Like spreads, this is NOT a true win probability! Total bets are also
        designed to be 50/50. This represents model conviction, scaled conservatively to
        50-65% range (totals are harder to predict than spreads).
        
        Args:
            edge: Point total differential (model total - market total)
            
        Returns:
            Value rating (0.50-0.65) - model's conviction about edge
        """
        abs_edge = abs(edge)
        
        if abs_edge < 0.5:
            return 0.50  # No edge
        
        # Even more conservative than spreads (totals are harder to predict)
        # Cap at 65% since totals have more variance
        
        if abs_edge <= 6:
            prob = 0.50 + edge * 0.012  # 1.2% per point → 57.2% at 6 pts
        elif abs_edge <= 12:
            base = 0.50 + 6 * 0.012  # 57.2% at 6 pts
            additional = (abs_edge - 6) * 0.008  # 0.8% per point
            prob = base + (additional if edge > 0 else -additional)
        elif abs_edge <= 20:
            base = 0.50 + 6 * 0.012 + 6 * 0.008  # 62.0% at 12 pts
            additional = (abs_edge - 12) * 0.003  # 0.3% per point
            prob = base + (additional if edge > 0 else -additional)
        else:
            # Cap at 65% - market is sophisticated on totals too
            base = 0.50 + 6 * 0.012 + 6 * 0.008 + 8 * 0.003  # 64.4% at 20 pts
            additional = min((abs_edge - 20) * 0.0005, 0.006)  # Minimal increase, max 65%
            prob = base + (additional if edge > 0 else -additional)
        
        # Totals are harder to predict - tighter bounds than spreads
        return max(0.50, min(0.65, prob))

