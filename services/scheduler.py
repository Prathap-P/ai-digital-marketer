"""
APScheduler singleton.

Import `scheduler` from this module wherever you need to add or inspect jobs.
The scheduler is started once by the FastAPI lifespan handler in main.py.
"""

from apscheduler.schedulers.background import BackgroundScheduler

scheduler = BackgroundScheduler(timezone="UTC")
