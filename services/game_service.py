import asyncio
import logging
from datetime import datetime
from typing import List, Optional
from bson import ObjectId
from bson.errors import InvalidId
from db.database import get_database
from db.models import Game, GameCreate, GameUpdate

logger = logging.getLogger(__name__)


async def get_game_by_id(game_id: str) -> Optional[Game]:
    """Get game by ID with proper ObjectId handling"""
    try:
        db = get_database()

        # Validate game_id format
        if not ObjectId.is_valid(game_id):
            raise ValueError("Invalid game ID format")

        # Query database
        game_data = await db.games.find_one({"_id": ObjectId(game_id)})
        if not game_data:
            return None

        # Convert ObjectId to string and validate model
        game_data["_id"] = str(game_data["_id"])
        return Game.model_validate(game_data)

    except Exception as e:
        logger.error(f"Error getting game {game_id}: {str(e)}")
        return None


async def get_games(skip: int = 0, limit: int = 100) -> List[Game]:
    """Get paginated list of games with proper model validation"""
    try:
        db = get_database()
        games = []
        cursor = db.games.find({"is_active": True}).skip(skip).limit(limit)

        async for game_doc in cursor:
            try:
                # Convert ObjectId to string
                game_doc["_id"] = str(game_doc["_id"])
                # Validate against Game model
                game = Game.model_validate(game_doc)
                games.append(game)
            except Exception as e:
                logger.error(f"Skipping invalid game document: {str(e)}")
                logger.debug(f"Problematic document: {game_doc}")

        return games

    except Exception as e:
        logger.error(f"Error getting games: {str(e)}")
        return []


async def get_featured_games(limit: int = 3) -> List[Game]:
    db = get_database()
    games = []
    cursor = db.games.find({"is_active": True, "category": "popular"}).limit(limit)
    async for game in cursor:
        games.append(Game(**game))
    return games


async def create_game(game_data: GameCreate) -> Game:
    """Create new game with comprehensive validation"""
    db = get_database()

    try:
        # Create game document
        game_doc = {
            **game_data.dict(),
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }

        # Insert document
        result = await db.games.insert_one(game_doc)
        if not result.inserted_id:
            raise ValueError("Game creation failed - no ID returned")

        # Get and validate created game
        created_game = await get_game_by_id(str(result.inserted_id))
        if not created_game:
            raise ValueError("Failed to fetch created game")

        return created_game

    except Exception as e:
        logger.error(f"Game creation error: {str(e)}")
        raise ValueError(f"Failed to create game: {str(e)}")


async def update_game(game_id: str, game_data: GameUpdate) -> Optional[Game]:
    db = get_database()

    # Remove None values
    update_data = {k: v for k, v in game_data.dict().items() if v is not None}
    update_data["updated_at"] = datetime.utcnow()

    # Update game
    result = await db.games.update_one(
        {"_id": ObjectId(game_id)},
        {"$set": update_data}
    )

    if result.modified_count:
        return await get_game_by_id(game_id)
    return None


async def delete_game(game_id: str) -> Optional[Game]:
    db = get_database()

    # Get game before deletion
    game = await get_game_by_id(game_id)
    if not game:
        return None

    # Delete game
    result = await db.games.delete_one({"_id": ObjectId(game_id)})

    if result.deleted_count:
        return game
    return None
