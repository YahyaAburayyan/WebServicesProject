from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.modules.applications.router import router as applications_router
from app.modules.applicants.router import router as applicants_router
from app.modules.staff.router import router as staff_router
from app.modules.analytics.router import router as analytics_router

app = FastAPI(
    title="LRMIS API",
    description="Land Registration Management Information System",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(applications_router)
app.include_router(applicants_router)
app.include_router(staff_router)
app.include_router(analytics_router)


@app.get("/", tags=["Health"])
def health_check():
    return {"status": "ok"}
