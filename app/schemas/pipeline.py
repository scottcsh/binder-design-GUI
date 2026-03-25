from typing import Literal, List
from pydantic import BaseModel, Field, model_validator

from app.schemas.common import JobMeta, ResourceSpec


class BinderPipelineSpec(BaseModel):
    workflow: Literal["binder_pipeline"]
    target_pdb: str

    contigs: str = "[C1-118/0 60-80]"
    num_backbones: int = Field(ge=1, le=5000)

    hotspot_chain: str = "C"
    hotspot_residues: List[int] = Field(default_factory=list)

    noise_scale_ca: float = 1.0
    noise_scale_frame: float = 1.0

    sequences_per_backbone: int = Field(default=4, ge=1, le=64)
    af3_top_k_backbones: int = Field(default=20, ge=1, le=1000)

    resources: ResourceSpec = Field(default_factory=ResourceSpec)
    meta: JobMeta = Field(default_factory=JobMeta)

    @model_validator(mode="after")
    def validate_hotspots(self):
        if len(self.hotspot_chain) != 1:
            raise ValueError("hotspot_chain must be a single character")
        if any(x <= 0 for x in self.hotspot_residues):
            raise ValueError("hotspot_residues must be positive integers")
        return self
