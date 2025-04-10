from typing import List
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from api.deps import get_admin_user, get_current_active_user
from db.models import Game, GameCreate, GameUpdate, User
from services.game_service import (
    create_game,
    get_game_by_id,
    get_games,
    update_game,
    delete_game,
    get_featured_games
)
from services.cloudinary_service import upload_image
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/", response_model=List[Game])
async def read_games(
        skip: int = 0,
        limit: int = 100,
        current_user: User = Depends(get_current_active_user)
):
    games = await get_games(skip, limit)
    return games


@router.get("/featured", response_model=List[Game])
async def read_featured_games(
        limit: int = 3,
        current_user: User = Depends(get_current_active_user)
):
    games = await get_featured_games(limit)
    return games


@router.post("/", response_model=Game)
async def create_new_game(
    game_data: GameCreate,
    current_user: User = Depends(get_admin_user)
):
    try:
        game = await create_game(game_data)
        return game
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Internal server error creating game: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error during game creation",
        )


@router.post("/with-image")
async def create_game_with_image(
        title: str = Form(...),
        description: str = Form(...),
        min_stake: float = Form(...),
        category: str = Form(...),
        icon: str = Form(None),
        rules: str = Form(...),
        is_active: bool = Form(True),
        image: UploadFile = File(None),
        current_user: User = Depends(get_admin_user)
):
    image_url = None
    if image:
        image_url = await upload_image(image)

    game_data = GameCreate(
        title=title,
        description=description,
        min_stake=min_stake,
        category=category,
        icon=icon,
        image_url=image_url,
        rules=rules,
        is_active=is_active
    )

    game = await create_game(game_data)
    return game


@router.get("/{game_id}", response_model=Game)
async def read_game(
        game_id: str,
        current_user: User = Depends(get_current_active_user)
):
    game = await get_game_by_id(game_id)
    if game is None:
        raise HTTPException(status_code=404, detail="Game not found")
    return game


@router.put("/{game_id}", response_model=Game)
async def update_game_data(
        game_id: str,
        game_data: GameUpdate,
        current_user: User = Depends(get_admin_user)
):
    game = await update_game(game_id, game_data)
    if game is None:
        raise HTTPException(status_code=404, detail="Game not found")
    return game


@router.delete("/{game_id}", response_model=Game)
async def delete_game_data(
        game_id: str,
        current_user: User = Depends(get_admin_user)
):
    game = await delete_game(game_id)
    if game is None:
        raise HTTPException(status_code=404, detail="Game not found")
    return game
