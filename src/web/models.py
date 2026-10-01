"""Pydantic models for WLAN Test GUI API."""
from typing import Optional
from pydantic import BaseModel


class TestCreate(BaseModel):
    name: str
    tc_id: str
    workspace_json: dict
    python_code: str
    station: str = ""
    model: str = ""


class TestOut(BaseModel):
    id: int
    name: str
    tc_id: str
    created_at: str


class RunCreate(BaseModel):
    test_id: str
    sku: str = ""


class RunOut(BaseModel):
    id: int
    run_id: str
    test_id: str
    test_name: str
    started_at: str
    finished_at: Optional[str] = None
    status: str
    duration_sec: Optional[float] = None


class FileContent(BaseModel):
    content: str


class ScheduleCreate(BaseModel):
    test_id: str
    cron: str
    enabled: bool = True


class ScheduleOut(BaseModel):
    id: int
    test_id: str
    cron: str
    enabled: bool
    next_run: Optional[str] = None


class TopologyPlanCreate(BaseModel):
    name: str
    topology_json: dict  # {"devices": [{"model": "ECS4150-54P", "scripts": ["LinkDetection-0010.py", ...]}, ...]}


class TopologyPlanUpdate(BaseModel):
    topology_json: dict
