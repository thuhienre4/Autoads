from fastapi import APIRouter

from app.services.analysis import generate_recommendations

router = APIRouter()


@router.get("")
async def recommendations():
    return generate_recommendations()


@router.get("/daily-report")
async def daily_report():
    rows = generate_recommendations()
    return {
        "title": "Bao cao toi uu hang ngay",
        "priority_order": ["Tang Click", "Tang Conversion", "Giam CPC", "Tang ROAS"],
        "pause": [row for row in rows if row["type"] == "PAUSE_KEYWORD"],
        "increase_budget": [row for row in rows if row["type"] == "INCREASE_BID"],
        "add_negative": [row for row in rows if row["type"] == "ADD_NEGATIVE"],
        "create_ads": [row for row in rows if row["type"] == "CREATE_AD"],
    }
