import json
from datetime import datetime
from pathlib import Path
import yaml

from app.schemas.pipeline import BinderPipelineSpec
from app.settings import settings


def create_job_dir(spec: BinderPipelineSpec) -> Path:
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    job_dir = settings.jobs_root / f"job-{ts}"
    job_dir.mkdir(parents=True, exist_ok=False)

    (job_dir / "logs").mkdir()
    (job_dir / "outputs").mkdir()

    return job_dir


def write_request(job_dir: Path, request_text: str) -> None:
    (job_dir / "request.txt").write_text(request_text, encoding="utf-8")


def write_spec(job_dir: Path, spec: BinderPipelineSpec) -> None:
    (job_dir / "spec.json").write_text(
        json.dumps(spec.model_dump(), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    (job_dir / "spec.yaml").write_text(
        yaml.safe_dump(spec.model_dump(), sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
