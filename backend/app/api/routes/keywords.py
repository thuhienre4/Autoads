from fastapi import APIRouter

from app.services.analysis import classify_keywords, classify_search_terms
from app.services.sample_data import KEYWORDS

router = APIRouter()


@router.get("")
async def list_keywords():
    return KEYWORDS


@router.get("/waste")
async def waste_keywords():
    return classify_keywords()["waste"]


@router.get("/growth")
async def growth_keywords():
    return classify_keywords()["growth"]


@router.get("/search-terms")
async def search_terms():
    return classify_search_terms()
