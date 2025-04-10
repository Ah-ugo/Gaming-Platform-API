from datetime import datetime, timedelta
from bson import ObjectId
from db.database import get_database
from db.models import TransactionType, GameResult, DepositStatus


async def get_admin_dashboard_stats():
    db = get_database()

    # Get total users
    total_users = await db.users.count_documents({})

    # Get total deposits
    total_deposits_pipeline = [
        {"$match": {"status": DepositStatus.APPROVED}},
        {"$group": {"_id": None, "total": {"$sum": "$amount"}}}
    ]
    total_deposits_result = await db.deposits.aggregate(total_deposits_pipeline).to_list(length=1)
    total_deposits = total_deposits_result[0]["total"] if total_deposits_result else 0

    # Get total games played
    total_games_played = await db.transactions.count_documents({"type": TransactionType.GAME})

    # Get total revenue (sum of lost bets)
    revenue_pipeline = [
        {"$match": {"type": TransactionType.GAME, "result": GameResult.LOSE}},
        {"$group": {"_id": None, "total": {"$sum": "$amount"}}}
    ]
    revenue_result = await db.transactions.aggregate(revenue_pipeline).to_list(length=1)
    revenue = revenue_result[0]["total"] if revenue_result else 0

    return {
        "totalUsers": total_users,
        "totalDeposits": total_deposits,
        "totalGamesPlayed": total_games_played,
        "revenue": revenue
    }


async def get_revenue_history(days: int = 30):
    db = get_database()

    # Calculate date range
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=days)

    # Aggregate daily revenue
    pipeline = [
        {
            "$match": {
                "type": TransactionType.GAME,
                "result": GameResult.LOSE,
                "timestamp": {"$gte": start_date, "$lte": end_date}
            }
        },
        {
            "$group": {
                "_id": {
                    "year": {"$year": "$timestamp"},
                    "month": {"$month": "$timestamp"},
                    "day": {"$dayOfMonth": "$timestamp"}
                },
                "amount": {"$sum": "$amount"}
            }
        },
        {
            "$sort": {"_id.year": 1, "_id.month": 1, "_id.day": 1}
        },
        {
            "$project": {
                "_id": 0,
                "date": {
                    "$dateToString": {
                        "format": "%Y-%m-%d",
                        "date": {
                            "$dateFromParts": {
                                "year": "$_id.year",
                                "month": "$_id.month",
                                "day": "$_id.day"
                            }
                        }
                    }
                },
                "amount": 1
            }
        }
    ]

    result = await db.transactions.aggregate(pipeline).to_list(length=days)

    return {
        "revenueHistory": result
    }


async def get_user_stats(user_id: str):
    db = get_database()

    # Get games played
    games_played = await db.transactions.count_documents({
        "user_id": ObjectId(user_id),
        "type": TransactionType.GAME
    })

    # Get win rate
    if games_played > 0:
        wins = await db.transactions.count_documents({
            "user_id": ObjectId(user_id),
            "type": TransactionType.GAME,
            "result": GameResult.WIN
        })
        win_rate = int((wins / games_played) * 100)
    else:
        win_rate = 0

    # Get total winnings
    winnings_pipeline = [
        {
            "$match": {
                "user_id": ObjectId(user_id),
                "type": TransactionType.GAME,
                "result": GameResult.WIN
            }
        },
        {
            "$group": {"_id": None, "total": {"$sum": "$payout"}}
        }
    ]
    winnings_result = await db.transactions.aggregate(winnings_pipeline).to_list(length=1)
    total_winnings = winnings_result[0]["total"] if winnings_result else 0

    return {
        "gamesPlayed": games_played,
        "winRate": win_rate,
        "totalWinnings": total_winnings
    }
