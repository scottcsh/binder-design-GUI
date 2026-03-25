from typing import Literal, Optional
from pydantic import BaseModel, Field


class ResourceSpec(BaseModel):
    executor: Literal["local", "slurm"] = "local"
    gpus: int = Field(default=1, ge=1, le=8)
    cpus: int = Field(default=8, ge=1, le=256)
    mem_gb: int = Field(default=32, ge=1, le=2048)
    gpu_type: Optional[str] = None
    time_limit: str = "24:00:00"


class JobMeta(BaseModel):
    job_name: str = "binder_job"
    output_root: str = "./data/jobs"
    dry_run: bool = True
