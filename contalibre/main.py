from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from . import __version__
from .database import init_db
from .routers import activos, aeat, asientos, cuentas, ejercicios, facturas, ia, informes, terceros

STATIC_DIR = Path(__file__).parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="ContaLibre",
    description="Contabilidad de código abierto para pymes y autónomos (España)",
    version=__version__,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost", "http://localhost:8000", "http://127.0.0.1:8000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

for router in (cuentas, asientos, terceros, facturas, activos, informes, ejercicios, aeat, ia):
    app.include_router(router.router, prefix="/api/v1")

app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")


def cli():
    """Punto de entrada del comando `contalibre`."""
    import uvicorn

    uvicorn.run("contalibre.main:app", host="127.0.0.1", port=8000)


if __name__ == "__main__":
    cli()
