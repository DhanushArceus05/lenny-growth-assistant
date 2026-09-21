from fastapi import APIRouter

from app.providers.factory import list_provider_status

router = APIRouter(prefix="/api/providers", tags=["providers"])


@router.get("")
async def providers():
    return await list_provider_status()
