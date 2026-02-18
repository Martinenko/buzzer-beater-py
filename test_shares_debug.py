#!/usr/bin/env python3
import asyncio
import json
from app.database import async_session
from app.models.player_share import PlayerShare
from app.models.team import Team
from app.models.player import Player
from app.models.user import User
from app.models.player_training_plan import PlayerTrainingPlan
from app.models.user_message import UserMessage
from sqlalchemy import select, or_
from sqlalchemy.orm import selectinload

async def list_users():
    async with async_session() as session:
        result = await session.execute(select(User))
        users = result.scalars().all()
        print(f'Found {len(users)} users:')
        for u in users[:15]:
            print(f'  - {u.username}')
        return

async def debug_shares():
    async with async_session() as session:
        # Get all shares
        stmt = (
            select(PlayerShare)
            .options(
                selectinload(PlayerShare.player).selectinload(Player.current_team),
                selectinload(PlayerShare.owner),
            )
        )
        result = await session.execute(stmt)
        shares = result.scalars().all()

        print(f"Total shares: {len(shares)}")
        
        if shares:
            share = shares[0]
            print(f"\nFirst share:")
            print(f"  Share ID: {share.id}")
            print(f"  Owner ID: {share.owner_id}")
            print(f"  Owner Username: {share.owner.username if share.owner else 'None'}")
            print(f"  Player ID: {share.player_id}")
            print(f"  Player Name: {share.player.name if share.player else 'None'}")
            print(f"  Player current_team: {share.player.current_team}")
            print(f"  Player current_team_id: {share.player.current_team_id}")
            print(f"  Player team_name: {share.player.team_name}")
            
            # Now test the resolve logic
            team_ids = {s.player.current_team_id for s in shares if s.player and s.player.current_team_id}
            owner_ids = {s.owner_id for s in shares}
            print(f"\nTeam IDs to fetch: {team_ids}")
            print(f"Owner IDs to fetch: {owner_ids}")
            
            team_map = {}
            teams_by_owner = {}
            teams_by_owner_name = {}
            
            if team_ids or owner_ids:
                team_query = select(Team).where(or_(Team.id.in_(team_ids), Team.coach_id.in_(owner_ids)))
                team_result = await session.execute(team_query)
                teams = team_result.scalars().all()
                print(f"\nFetched {len(teams)} teams")
                for t in teams:
                    print(f"  Team: id={t.id}, team_id={t.team_id}, name={t.name}, coach_id={t.coach_id}")
                
                team_map = {t.id: t for t in teams}
                for t in teams:
                    teams_by_owner.setdefault(t.coach_id, []).append(t)
                    teams_by_owner_name[(t.coach_id, t.name)] = t
            
            # Test resolve logic for first share
            def resolve_owner_team(share):
                if share.player.current_team:
                    result = (share.player.current_team.team_id, share.player.current_team.name)
                    print(f"  -> Resolved via current_team relationship: {result}")
                    return result
                if share.player.current_team_id and team_map.get(share.player.current_team_id):
                    team = team_map.get(share.player.current_team_id)
                    result = (team.team_id, team.name)
                    print(f"  -> Resolved via team_map: {result}")
                    return result
                if share.player.team_name and teams_by_owner_name.get((share.owner_id, share.player.team_name)):
                    team = teams_by_owner_name.get((share.owner_id, share.player.team_name))
                    result = (team.team_id, team.name)
                    print(f"  -> Resolved via teams_by_owner_name: {result}")
                    return result
                owner_teams = teams_by_owner.get(share.owner_id, [])
                if len(owner_teams) == 1:
                    result = (owner_teams[0].team_id, owner_teams[0].name)
                    print(f"  -> Resolved via single owner team: {result}")
                    return result
                print(f"  -> Could not resolve!")
                return None, None
            
            print(f"\nResolving team for first share:")
            team_id, team_name = resolve_owner_team(share)
            print(f"Final result: team_id={team_id}, team_name={team_name}")

async def check_latest_message():
    async with async_session() as session:
        result = await session.execute(select(UserMessage).order_by(UserMessage.created_at.desc()).limit(1))
        msg = result.scalar_one_or_none()
        if msg:
            print('Latest message content (repr):')
            print(repr(msg.content))
            print()
            print('Rendered:')
            print(msg.content)
        else:
            print('No messages found')

asyncio.run(check_latest_message())
