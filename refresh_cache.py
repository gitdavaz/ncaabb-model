#!/usr/bin/env python3
"""
Cache refresh script for NCAAB predictions
Run this periodically (e.g., daily via cron) to keep cache fresh
"""

import os
import sys
from dotenv import load_dotenv
from datetime import datetime, timedelta
from database import SupabaseCache
from api_client import CollegeBasketballAPI
from typing import List


def refresh_team_stats(api_client: CollegeBasketballAPI, cache: SupabaseCache, season: int):
    """
    Refresh team stats for all D1 teams
    
    Args:
        api_client: API client instance
        cache: Cache instance
        season: Season year
    """
    print(f"📊 Refreshing team stats for season {season}...")
    start_time = datetime.now()
    
    try:
        # Get all teams
        print(f"   Fetching team list from API...")
        teams = api_client.teams_api.get_teams()
        d1_teams = [t for t in teams if hasattr(t, 'conference') and t.conference]
        
        print(f"   Found {len(d1_teams)} D1 teams")
        print(f"   Starting refresh... (progress shown every 10 teams)")
        
        refreshed = 0
        errors = 0
        for i, team in enumerate(d1_teams, 1):
            try:
                team_id = team.id if hasattr(team, 'id') else None
                team_name = team.school if hasattr(team, 'school') else f"Team {team_id}"
                
                if not team_id:
                    continue
                
                # Get fresh stats from API
                stats = api_client.get_team_stats(team_id, season)
                
                if stats:
                    # Update cache
                    cache.cache_team_stats(team_id, season, stats, team_name=team_name, conference=team.conference if hasattr(team, 'conference') else None)
                    refreshed += 1
                    
                    # Progress every 10 teams
                    if refreshed % 10 == 0:
                        elapsed = (datetime.now() - start_time).total_seconds()
                        rate = refreshed / elapsed if elapsed > 0 else 0
                        eta = (len(d1_teams) - refreshed) / rate if rate > 0 else 0
                        print(f"   Progress: {refreshed}/{len(d1_teams)} teams ({refreshed/len(d1_teams)*100:.1f}%) | Rate: {rate:.1f} teams/sec | ETA: {eta/60:.1f} min")
                
            except Exception as e:
                errors += 1
                if errors <= 5:  # Only show first 5 errors
                    print(f"   ⚠️  Error refreshing {team_name} (ID: {team_id}): {str(e)[:50]}")
                continue
        
        elapsed = (datetime.now() - start_time).total_seconds()
        print(f"   ✅ Refreshed {refreshed} team stats in {elapsed:.1f}s ({errors} errors)")
        return refreshed
        
    except Exception as e:
        print(f"   ❌ Error refreshing team stats: {e}")
        return 0


def refresh_recent_games(api_client: CollegeBasketballAPI, cache: SupabaseCache, 
                        season: int, days_back: int = 7):
    """
    Refresh recent games for the past N days
    
    Args:
        api_client: API client instance
        cache: Cache instance
        season: Season year
        days_back: Number of days to refresh
    """
    print(f"🎮 Refreshing games from past {days_back} days...")
    start_time = datetime.now()
    
    try:
        total_games = 0
        
        for days_ago in range(days_back):
            target_date = (datetime.now() - timedelta(days=days_ago)).strftime('%Y-%m-%d')
            
            print(f"   Fetching {target_date}...", end=" ", flush=True)
            
            # Get all games for this date
            games = api_client.get_todays_games(
                date=target_date,
                d1_only=True,
                upcoming_only=False
            )
            
            if games:
                # Cache the games
                cache.cache_games(games, season)
                total_games += len(games)
                print(f"{len(games)} games cached")
            else:
                print("no games found")
        
        elapsed = (datetime.now() - start_time).total_seconds()
        print(f"   ✅ Cached {total_games} games in {elapsed:.1f}s")
        return total_games
        
    except Exception as e:
        print(f"   ❌ Error refreshing games: {e}")
        return 0


def refresh_team_info(api_client: CollegeBasketballAPI, cache: SupabaseCache):
    """
    Refresh team information (names, conferences, etc.)
    
    Args:
        api_client: API client instance
        cache: Cache instance
    """
    print("🏫 Refreshing team information...")
    start_time = datetime.now()
    
    try:
        print(f"   Fetching team list from API...")
        teams = api_client.teams_api.get_teams()
        print(f"   Found {len(teams)} teams, caching...")
        
        refreshed = 0
        errors = 0
        for team in teams:
            try:
                team_info = {
                    'id': team.id if hasattr(team, 'id') else None,
                    'name': team.school if hasattr(team, 'school') else '',
                    'conference': team.conference if hasattr(team, 'conference') else '',
                    'abbreviation': team.abbreviation if hasattr(team, 'abbreviation') else '',
                    'mascot': team.mascot if hasattr(team, 'mascot') else ''
                }
                
                if team_info['id']:
                    cache.cache_team_info(team_info)
                    refreshed += 1
                    
            except Exception as e:
                errors += 1
                continue
        
        elapsed = (datetime.now() - start_time).total_seconds()
        print(f"   ✅ Refreshed {refreshed} teams in {elapsed:.1f}s ({errors} errors)")
        return refreshed
        
    except Exception as e:
        print(f"   ❌ Error refreshing team info: {e}")
        return 0


def cleanup_old_cache(cache: SupabaseCache, days_to_keep: int = 30):
    """
    Clean up old cache entries
    
    Args:
        cache: Cache instance
        days_to_keep: Number of days to keep
    """
    print(f"🧹 Cleaning up cache entries older than {days_to_keep} days...")
    
    try:
        cache.clear_old_cache(days=days_to_keep)
        print("   ✅ Cleanup complete")
    except Exception as e:
        print(f"   ❌ Error cleaning cache: {e}")


def main():
    """Main refresh script"""
    script_start = datetime.now()
    
    print("=" * 60)
    print("NCAAB PREDICTIONS - CACHE REFRESH")
    print(f"Time: {script_start.strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    print()
    
    # Load environment
    load_dotenv()
    
    # Get credentials
    api_key = os.getenv('API_KEY')
    supabase_url = os.getenv('SUPABASE_URL')
    supabase_key = os.getenv('SUPABASE_SERVICE_KEY')
    
    if not api_key:
        print("❌ Error: API_KEY not found in environment variables")
        sys.exit(1)
    
    if not supabase_url or not supabase_key:
        print("❌ Error: SUPABASE_URL or SUPABASE_SERVICE_KEY not found")
        sys.exit(1)
    
    # Initialize
    print("🔧 Initializing...")
    cache = SupabaseCache(supabase_url, supabase_key)
    api_client = CollegeBasketballAPI(api_key, cache=None)  # No cache for refresh
    
    # Get current season
    season = api_client._get_current_season()
    print(f"   Season: {season}")
    print()
    
    # Track statistics
    stats = {
        'teams_refreshed': 0,
        'team_stats_refreshed': 0,
        'games_cached': 0
    }
    
    # Refresh team information (rarely changes)
    stats['teams_refreshed'] = refresh_team_info(api_client, cache)
    print()
    
    # Refresh team stats (daily)
    stats['team_stats_refreshed'] = refresh_team_stats(api_client, cache, season)
    print()
    
    # Refresh recent games (daily)
    stats['games_cached'] = refresh_recent_games(api_client, cache, season, days_back=7)
    print()
    
    # Cleanup old entries
    cleanup_old_cache(cache, days_to_keep=30)
    print()
    
    # Update metadata
    try:
        cache.client.table('cache_metadata').upsert({
            'key': f'team_stats_{season}',
            'last_refresh': datetime.now().isoformat(),
            'notes': f'Team statistics for {season} season'
        }, on_conflict='key').execute()
    except:
        pass
    
    # Summary
    total_elapsed = (datetime.now() - script_start).total_seconds()
    print("=" * 60)
    print("✅ CACHE REFRESH COMPLETE")
    print("=" * 60)
    print(f"📊 Summary:")
    print(f"   Teams cached: {stats['teams_refreshed']}")
    print(f"   Team stats cached: {stats['team_stats_refreshed']}")
    print(f"   Games cached: {stats['games_cached']}")
    print(f"   API calls made: {api_client.api_calls}")
    print(f"   Total time: {total_elapsed/60:.1f} minutes ({total_elapsed:.1f}s)")
    print("=" * 60)


if __name__ == '__main__':
    main()

