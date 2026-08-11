from fastapi import FastAPI, APIRouter

app = FastAPI()

router1 = APIRouter()
@router1.get("/settings")
def settings():
    return {"msg": "settings"}

router2 = APIRouter()
@router2.get("/upload")
def upload():
    return {"msg": "upload"}

app.include_router(router1, prefix="/api/admin")
app.include_router(router2, prefix="/api/admin")

if __name__ == "__main__":
    for route in app.routes:
        print(getattr(route, "path", route.name))
