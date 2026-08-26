from fastapi import APIRouter

from app.schemas.ads import ConversionPredictionRequest
from app.services.ai_service import predict_conversion

router = APIRouter()


@router.post("/conversion")
async def conversion_prediction(payload: ConversionPredictionRequest):
    return predict_conversion(payload.ctr, payload.cpc, payload.device, payload.audience, payload.hour, payload.day)
