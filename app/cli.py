import json
import typer
from rich import print
from rich.syntax import Syntax

from app.jobs.manager import create_job_dir, write_request, write_spec
from app.planner.nl_parser import parse_nl_to_spec
from app.plugins.rfdiffusion.compiler import RFdiffusionCompiler
from app.validators.workflows import validate_spec

app = typer.Typer(help="Protein binder workflow compiler")


@app.command()
def plan(text: str):
    spec = parse_nl_to_spec(text)
    print(json.dumps(spec.model_dump(), indent=2, ensure_ascii=False))


@app.command()
def compile(text: str):
    spec = parse_nl_to_spec(text)
    spec = validate_spec(spec)

    job_dir = create_job_dir(spec)
    write_request(job_dir, text)
    write_spec(job_dir, spec)

    compiler = RFdiffusionCompiler()
    run_sh = compiler.compile(spec, job_dir)

    print(f"[bold green]Compiled:[/bold green] {job_dir}")
    print(f"[bold]Run script:[/bold] {run_sh}")

    content = run_sh.read_text(encoding="utf-8")
    print(Syntax(content, "bash", line_numbers=True))


if __name__ == "__main__":
    app()
