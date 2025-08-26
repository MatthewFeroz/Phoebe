from fastapi import APIRouter, FastAPI

router = APIRouter()

def create_app():
    app = FastAPI()
    load_sample_data()
    return app

@router.get("/health")
async def health_check() -> dict[str, str]:
    return {"status": "ok"}


def create_app() -> FastAPI:
    app = FastAPI()
    app.include_router(router)
    return app
