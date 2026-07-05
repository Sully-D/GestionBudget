from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.accounts.router import router as accounts_router
from app.budget.router import router as budget_router
from app.budget.targets_router import router as budget_targets_router
from app.budget.tracking_router import router as budget_tracking_router
from app.core.config import settings
from app.import_pipeline.router import router as import_router
from app.tags.router import router as tags_router
from app.tags.rules_router import router as rules_router
from app.transactions.router import router as transactions_router

app = FastAPI(title="GestionDuBudget")


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    # Normalise l'enveloppe d'erreur au format documenté {"detail": "<string>"}
    # (le handler par défaut de FastAPI renvoie une liste d'objets).
    messages = [
        f"{'.'.join(str(part) for part in error['loc'][1:])}: {error['msg']}"
        for error in exc.errors()
    ]
    return JSONResponse(status_code=422, content={"detail": "; ".join(messages)})


@app.get("/health")
def health():
    return {"data": {"status": "ok"}}


app.include_router(accounts_router)
app.include_router(transactions_router)
app.include_router(tags_router)
app.include_router(rules_router)
app.include_router(budget_router)
app.include_router(budget_targets_router)
app.include_router(budget_tracking_router)
app.include_router(import_router)

app.frontend("/", directory=settings.frontend_dist_dir, fallback="index.html")
