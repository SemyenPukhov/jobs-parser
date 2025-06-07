# from fastapi import APIRouter, Depends
# from sqlmodel import select, Session
# from app.models import Job
# from app.db import get_session

# router = APIRouter()


# @router.get("/jobs", response_model=list[Job])
# def read_jobs(session: Session = Depends(get_session)):
#     jobs = session.exec(select(Job)).all()
#     return jobs


# @router.post("/scrape/startup-jobs")
# async def run_scrape():
#     jobs = await scrape_startup_jobs()
#     return {"added": len(jobs)}
