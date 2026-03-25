from pathlib import Path
from jinja2 import Environment, FileSystemLoader

from app.schemas.pipeline import BinderPipelineSpec
from app.settings import settings


class RFdiffusionCompiler:
    def __init__(self):
        template_dir = Path(__file__).parent / "templates"
        self.env = Environment(loader=FileSystemLoader(str(template_dir)))

    def compile(self, spec: BinderPipelineSpec, job_dir: Path) -> Path:
        tpl = self.env.get_template("run.sh.j2")

        hotspot_tokens = [f"{spec.hotspot_chain}{x}" for x in spec.hotspot_residues]
        output_prefix = job_dir / "outputs" / "rfdiffusion"
        output_prefix.mkdir(parents=True, exist_ok=True)

        rendered = tpl.render(
            conda_env=settings.rfdiffusion_env,
            script_path=settings.rfdiffusion_script,
            target_pdb=str(Path(spec.target_pdb).resolve()),
            contigs=spec.contigs,
            num_designs=spec.num_backbones,
            hotspot_tokens=hotspot_tokens,
            noise_scale_ca=spec.noise_scale_ca,
            noise_scale_frame=spec.noise_scale_frame,
            output_prefix=str(output_prefix) + "/",
        )

        run_sh = job_dir / "run.sh"
        run_sh.write_text(rendered, encoding="utf-8")
        run_sh.chmod(0o755)

        return run_sh
