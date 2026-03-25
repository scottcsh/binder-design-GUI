from pathlib import Path

from app.schemas.pipeline import BinderPipelineSpec
from app.settings import settings


def ensure_allowed_path(path_str: str) -> Path:
    path = Path(path_str).resolve()
    allowed = [p.resolve() for p in settings.allowed_roots]

    if not any(str(path).startswith(str(root)) for root in allowed):
        raise ValueError(f"Path not allowed: {path}")

    return path


def validate_spec(spec: BinderPipelineSpec) -> BinderPipelineSpec:
    target_path = Path(spec.target_pdb).resolve()

    if not target_path.exists():
        raise ValueError(f"Target PDB does not exist: {target_path}")

    ensure_allowed_path(str(target_path))

    if spec.af3_top_k_backbones > spec.num_backbones:
        raise ValueError("af3_top_k_backbones cannot exceed num_backbones")

    return spec
