from pathlib import Path
from datetime import datetime
import json
import csv
import re
import subprocess
import shlex
import time
import shutil
from typing import Optional

from fastapi import FastAPI, Form, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

BASE_DIR = Path(__file__).resolve().parent.parent
TEMPLATES_DIR = BASE_DIR / "app" / "templates"
STATIC_DIR = BASE_DIR / "app" / "static"
CONFIG_PATH = BASE_DIR / "data" / "app_config.json"
BROWSER_ROOTS = [Path("/")]

app = FastAPI(title="Binder LLM GUI")
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

PROTEINMPNN_RUNS = {}
ALPHAFOLD3_RUNS = {}


def default_spec() -> dict:
    return {
        "mode": "basic",
        "target_pdb": "",
        "target_protein_chain": "",
        "contigs": "",
        "target_chain": "",
        "target_start": "",
        "target_end": "",
        "design_min": "",
        "design_max": "",
        "partial_target_chain": "",
        "partial_target_start": "",
        "partial_target_end": "",
        "partial_design_length": "",
        "custom_contig": "",
        "hotspot_chain": "",
        "hotspot_residues": "",
        "num_backbones": 1000,
        "noise_scale_ca": 1,
        "noise_scale_frame": 1,
        "output_dir": "",
        "output_prefix": "",
        "gpu_id": "0",
        "partial_t_value": "",
        "run_script_path": "",
        "run_log_path": "",
    }


def default_evoef2_spec() -> dict:
    return {
        "input_dir": "",
        "display_input_dir": "(not set)",
        "pdb_count": 0,
        "chain_to_design": "",
        "max_pdbs_to_keep": "",
    }


def default_proteinmpnn_spec() -> dict:
    return {
        "input_dir": "",
        "display_input_dir": "(not set)",
        "pdb_count": 0,
        "output_dir": "",
        "chain_to_design": "",
        "num_seq_per_target": "10",
        "sampling_temp": "0.4",
        "seed": "37",
        "batch_size": "1",
        "run_script_path": "",
        "run_log_path": "",
        "run_pid": "",
        "generate_af3_json_input": False,
        "add_c_term_trp": False,
        "c_term_trp_count": "1",
        "omit_aas_list": "",
        "make_bias_aa_list": "",
        "make_bias_bias_list": "",
        "fixed_position_list": "",
        "omit_aas": False,
        "make_bias": False,
        "fixed_position": False,
    }



def default_alphafold3_spec() -> dict:
    return {
        "root_dir": "",
        "database_dir": "",
        "model_dir": "",
        "docker_profile": "",
        "environment": "",
    }


def default_alphafold3_run_spec() -> dict:
    return {
        "input_json_dir": "",
        "output_dir": "",
        "gpu": "0",
        "run_script_path": "",
        "run_log_path": "",
        "run_id": "",
    }


def default_filter_af3_results_spec() -> dict:
    return {
        "dir": "",
        "iptm": "",
        "ptm": "",
        "filtered_dir": "",
        "score": "",
        "pae": "",
        "chain_id": "",
        "max_output": "",
    }


def default_config() -> dict:
    return {
        "rfd_executable": "/home/data/RFdiffusion/RFdiffusion/scripts/run_inference.py",
        "env_setup": "module load miniforge3/\nsource $(conda info --base)/etc/profile.d/conda.sh\nset +u\nconda activate SE3nv\nset -u",
        "evoef2_executable": "",
        "proteinmpnn_dir": "",
        "proteinmpnn_env_setup": "",
        "alphafold3_root_dir": "",
        "alphafold3_database_dir": "",
        "alphafold3_model_dir": "",
        "alphafold3_docker_profile": "",
        "alphafold3_environment": "",
    }


def load_config() -> dict:
    config = default_config()
    if CONFIG_PATH.exists():
        try:
            data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                config.update(data)
        except Exception:
            pass
    return config


def save_config(config: dict) -> None:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(config, indent=2), encoding="utf-8")


def is_allowed_path(path: Path) -> bool:
    resolved = path.resolve()
    return any(str(resolved).startswith(str(root.resolve())) for root in BROWSER_ROOTS)


def normalize_path(path_str: Optional[str]) -> Path:
    default_root = BROWSER_ROOTS[0].resolve()
    if not path_str:
        return default_root
    try:
        path = Path(path_str).resolve()
    except Exception:
        return default_root
    if not is_allowed_path(path):
        return default_root
    return path


def list_entries(path: Path, select_mode: str) -> list:
    entries = []
    for child in sorted(path.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())):
        if child.name.startswith("."):
            continue
        if child.is_dir():
            entries.append({
                "name": child.name,
                "path": str(child.resolve()),
                "is_dir": True,
                "is_selectable": select_mode == "dir",
            })
        elif select_mode == "file" and child.suffix.lower() == ".pdb":
            entries.append({
                "name": child.name,
                "path": str(child.resolve()),
                "is_dir": False,
                "is_selectable": True,
            })
        elif select_mode == "file_any":
            entries.append({
                "name": child.name,
                "path": str(child.resolve()),
                "is_dir": False,
                "is_selectable": True,
            })
    return entries


def parent_path(path: Path) -> Optional[str]:
    resolved = path.resolve()
    for root in BROWSER_ROOTS:
        root_resolved = root.resolve()
        if resolved == root_resolved:
            return None
        if str(resolved).startswith(str(root_resolved)):
            parent = resolved.parent
            if is_allowed_path(parent):
                return str(parent)
    return None


def tail_text(path: Path, max_chars: int = 12000) -> str:
    if not path.exists():
        return ""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
        return text[-max_chars:]
    except Exception:
        return ""


def tail_lines(path: Path, max_lines: int = 20) -> str:
    if not path.exists():
        return ""
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        return "\n".join(lines[-max_lines:])
    except Exception:
        return ""


def count_completed_designs(path: Path) -> int:
    if not path.exists():
        return 0
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
        return len(re.findall(r"Finished design in .*? minutes", text))
    except Exception:
        return 0


def count_pdb_files_in_directory(path: Path) -> int:
    if not path.exists() or not path.is_dir():
        return 0
    return sum(1 for p in path.iterdir() if p.is_file() and p.suffix.lower() == ".pdb")


def parse_evoef2_total_score(text: str) -> Optional[float]:
    match = re.search(r"Total\s*=\s*([-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?)", text)
    if not match:
        return None
    try:
        return float(match.group(1))
    except Exception:
        return None


def pid_is_running(pid: int) -> bool:
    proc_path = Path("/proc") / str(pid)
    if not proc_path.exists():
        return False
    try:
        stat_text = (proc_path / "stat").read_text(encoding="utf-8", errors="replace")
        fields = stat_text.split()
        if len(fields) >= 3 and fields[2] == "Z":
            return False
    except Exception:
        pass
    return True


def is_log_stale(path: Path, seconds: int = 5) -> bool:
    if not path.exists():
        return False
    try:
        return (time.time() - path.stat().st_mtime) > seconds
    except Exception:
        return False


def build_proteinmpnn_script(spec: dict, config: dict) -> str:
    proteinmpnn_root = Path(config.get("proteinmpnn_dir", "")).expanduser().resolve()
    if not proteinmpnn_root.exists():
        raise ValueError("ProteinMPNN directory is not set correctly in Options.")

    env_setup = config.get("proteinmpnn_env_setup", "").strip()
    output_dir = Path(spec["output_dir"]).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    run_script_path = output_dir / "run_proteinmpnn.sh"

    parse_script = proteinmpnn_root / "helper_scripts" / "parse_multiple_chains.py"
    assign_script = proteinmpnn_root / "helper_scripts" / "assign_fixed_chains.py"
    make_bias_script = proteinmpnn_root / "helper_scripts" / "make_bias_AA.py"
    make_fixed_positions_script = proteinmpnn_root / "helper_scripts" / "make_fixed_positions_dict.py"
    mpnn_run_script = proteinmpnn_root / "protein_mpnn_run.py"

    path_for_parsed_chains = '$output_dir/parsed_pdbs.jsonl'
    path_for_assigned_chains = '$output_dir/assigned_pdbs.jsonl'

    use_bias = bool(
        spec.get("make_bias")
        and str(spec.get("make_bias_aa_list", "")).strip()
        and str(spec.get("make_bias_bias_list", "")).strip()
    )
    use_fixed_positions = bool(
        spec.get("fixed_position")
        and str(spec.get("fixed_position_list", "")).strip()
    )
    use_af3 = bool(
        spec.get("generate_af3_json_input")
        and str(spec.get("target_pdb", "")).strip()
    )
    use_c_term_trp = bool(spec.get("add_c_term_trp"))
    c_term_trp_count = str(spec.get("c_term_trp_count", "1")).strip() or "1"
    try:
        c_term_trp_count_value = int(c_term_trp_count)
    except ValueError as exc:
        raise ValueError("C-term Trp count must be an integer.") from exc
    if c_term_trp_count_value < 0:
        raise ValueError("C-term Trp count must be 0 or greater.")

    lines = [
        "#!/bin/bash",
        "set -euo pipefail",
        "",
    ]

    if env_setup:
        lines.extend(env_setup.splitlines())
        lines.append("")

    lines.extend([
        f'folder_with_pdbs={shlex.quote(str(Path(spec["input_dir"]).expanduser().resolve()))}',
        f'output_dir={shlex.quote(str(output_dir))}',
        f'path_for_parsed_chains={path_for_parsed_chains}',
        f'path_for_assigned_chains={path_for_assigned_chains}',
        f'chains_to_design={shlex.quote(spec["chain_to_design"])}',
    ])

    if use_bias:
        lines.extend([
            'path_for_bias=$output_dir"/bias_pdbs.jsonl"',
            f'AA_list={shlex.quote(spec["make_bias_aa_list"])}',
            f'bias_list={shlex.quote(spec["make_bias_bias_list"])}',
        ])

    if use_fixed_positions:
        lines.extend([
            'path_for_fixed_positions=$output_dir"/fixed_pdbs.jsonl"',
            f'fixed_positions={shlex.quote(spec["fixed_position_list"])}',
        ])

    if use_af3:
        fasta_path = Path(spec["target_pdb"]).expanduser().resolve().with_suffix(".fasta")
        af3_script = BASE_DIR / "scripts" / "mpnn2afserver.sh"
        lines.extend([
            'af3_output_dir=$output_dir"/AF3_jsons"',
            f'target_fasta={shlex.quote(str(fasta_path))}',
            f'af3_script={shlex.quote(str(af3_script))}',
        ])

    if use_c_term_trp:
        lines.extend([
            f'c_term_trp_count={shlex.quote(str(c_term_trp_count_value))}',
        ])

    lines.append("")
    lines.append('echo "[1/3] Parsing input PDB files"')
    lines.append(
        f'python -u {shlex.quote(str(parse_script))} '
        '--input_path="$folder_with_pdbs" '
        '--output_path="$path_for_parsed_chains"'
    )
    lines.append('echo "[1/3] Done"')

    lines.append('echo "[2/3] Assigning chains to design"')
    lines.append(
        f'python -u {shlex.quote(str(assign_script))} '
        '--input_path="$path_for_parsed_chains" '
        '--output_path="$path_for_assigned_chains" '
        '--chain_list "$chains_to_design"'
    )
    if use_bias:
        lines.append(
            f'python -u {shlex.quote(str(make_bias_script))} '
            '--output_path=$path_for_bias '
            '--AA_list="$AA_list" '
            '--bias_list="$bias_list"'
        )
    if use_fixed_positions:
        lines.append(
            f'python -u {shlex.quote(str(make_fixed_positions_script))} '
            '--input_path=$path_for_parsed_chains '
            '--output_path=$path_for_fixed_positions '
            '--chain_list "$chains_to_design" '
            '--position_list "$fixed_positions"'
        )
    lines.append('echo "[2/3] Done"')

    cmd = (
        f'python -u {shlex.quote(str(mpnn_run_script))} '
        f'--jsonl_path "$path_for_parsed_chains" '
        f'--chain_id_jsonl "$path_for_assigned_chains" '
        f'--out_folder "$output_dir" '
    )
    if use_bias:
        cmd += '--bias_AA_jsonl $path_for_bias '
    if use_fixed_positions:
        cmd += '--fixed_positions_jsonl $path_for_fixed_positions '
    if spec.get("omit_aas") and spec.get("omit_aas_list"):
        cmd += f'--omit_AAs "{spec["omit_aas_list"]}" '
    cmd += (
        f'--num_seq_per_target {shlex.quote(str(spec["num_seq_per_target"]))} '
        f'--sampling_temp {shlex.quote(str(spec["sampling_temp"]))} '
        f'--seed {shlex.quote(str(spec["seed"]))} '
        f'--batch_size {shlex.quote(str(spec["batch_size"]))}'
    )

    lines.append('echo "[3/3] Running ProteinMPNN"')
    lines.append(cmd)

    if use_c_term_trp:
        lines.append('echo "[Post] Appending C-term Trp to generated sequences"')
        lines.append("python - <<'PY'")
        lines.extend([
            'from pathlib import Path',
            '',
            'seq_dir = Path(r"' + str(output_dir / 'seqs') + '")',
            'suffix = "W" * int(r"' + str(c_term_trp_count_value) + '")',
            '',
            'if suffix:',
            '    for fasta_path in sorted(seq_dir.glob("*.fa")):',
            '        lines = fasta_path.read_text(encoding="utf-8").splitlines()',
            '        records = []',
            '        header = None',
            '        seq_lines = []',
            '        for line in lines:',
            '            if line.startswith(">"):',
            '                if header is not None:',
            '                    records.append((header, "".join(seq_lines)))',
            '                header = line',
            '                seq_lines = []',
            '            else:',
            '                seq_lines.append(line.strip())',
            '        if header is not None:',
            '            records.append((header, "".join(seq_lines)))',
            '        if not records:',
            '            continue',
            '        updated_lines = []',
            '        for idx, (header, sequence) in enumerate(records):',
            '            if idx >= 1:',
            '                sequence = sequence + suffix',
            '            updated_lines.append(header)',
            '            updated_lines.append(sequence)',
            '        fasta_path.write_text("\\n".join(updated_lines) + "\\n", encoding="utf-8")',
        ])
        lines.append('PY')

    if use_af3:
        lines.append('echo "[AF3] Generating AlphaFold3 JSON input"')
        lines.append('mkdir -p "$af3_output_dir"')
        lines.append('/bin/bash "$af3_script" --dir "$output_dir/seqs" --fa "$target_fasta" --max_job 1')
        lines.append('mv "$output_dir/seqs/"*.json "$af3_output_dir"/ 2>/dev/null || true')

    lines.append('echo "[3/3] Done"')
    lines.append('echo "ProteinMPNN run completed."')

    run_script_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    run_script_path.chmod(0o755)
    return str(run_script_path)


def render_home(
    request: Request,
    spec: Optional[dict] = None,
    compile_result: Optional[str] = None,
    message: Optional[str] = None,
    error: Optional[str] = None,
    current_log_path: str = "",
    current_pid: str = "",
    initial_log_tail: str = "",
    completed_designs: int = 0,
    total_designs: int = 0,
):
    if spec is None:
        spec = default_spec()
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "spec": spec,
            "compile_result": compile_result,
            "message": message,
            "error": error,
            "current_log_path": current_log_path,
            "current_pid": current_pid,
            "initial_log_tail": initial_log_tail,
            "completed_designs": completed_designs,
            "total_designs": total_designs,
        },
    )


def render_options(request: Request, message: Optional[str] = None, error: Optional[str] = None):
    return templates.TemplateResponse(
        "options.html",
        {"request": request, "config": load_config(), "message": message, "error": error},
    )


def render_evoef2(
    request: Request,
    evoef2: Optional[dict] = None,
    message: Optional[str] = None,
    error: Optional[str] = None,
):
    if evoef2 is None:
        evoef2 = default_evoef2_spec()
    return templates.TemplateResponse(
        "evoef2.html",
        {
            "request": request,
            "evoef2": evoef2,
            "spec": evoef2,
            "message": message,
            "error": error,
        },
    )


def render_proteinmpnn(
    request: Request,
    proteinmpnn: Optional[dict] = None,
    message: Optional[str] = None,
    error: Optional[str] = None,
):
    if proteinmpnn is None:
        proteinmpnn = default_proteinmpnn_spec()
    return templates.TemplateResponse(
        "proteinmpnn.html",
        {
            "request": request,
            "proteinmpnn": proteinmpnn,
            "message": message,
            "error": error,
        },
    )


def build_alphafold3_script(spec: dict, config: dict) -> str:
    root_dir = Path(config.get("alphafold3_root_dir", "")).expanduser().resolve()
    database_dir = Path(config.get("alphafold3_database_dir", "")).expanduser().resolve()
    model_dir = Path(config.get("alphafold3_model_dir", "")).expanduser().resolve()

    if not root_dir.exists():
        raise ValueError("AlphaFold 3 Root Directory is not set correctly in Options.")
    if not database_dir.exists():
        raise ValueError("AlphaFold 3 Database Directory is not set correctly in Options.")
    if not model_dir.exists():
        raise ValueError("AlphaFold 3 Model Directory is not set correctly in Options.")

    input_json_dir = Path(spec["input_json_dir"]).expanduser().resolve()
    output_dir = Path(spec["output_dir"]).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    run_script_path = output_dir / "run_alphafold3.sh"
    cidfile_path = output_dir / "alphafold3.cid"

    docker_profile = config.get("alphafold3_docker_profile", "").strip()
    env_setup = config.get("alphafold3_environment", "").strip()

    lines = [
        "#!/bin/bash",
        "set -euo pipefail",
        "",
    ]

    if env_setup:
        lines.extend(env_setup.splitlines())
        lines.append("")

    lines.extend([
        f'cidfile={shlex.quote(str(cidfile_path))}',
        'rm -f "$cidfile"',
        "",
        "docker run \\",
        f'  --cidfile "$cidfile" \\',
        f'  --gpus "device={spec["gpu"]}" \\',
        f'  -v {shlex.quote(str(root_dir))}:/root \\',
        f'  -v {shlex.quote(str(input_json_dir))}:/root/input \\',
        f'  -v {shlex.quote(str(output_dir))}:/root/output \\',
        f'  -v {shlex.quote(str(database_dir))}:/root/public_databases \\',
        f'  -v {shlex.quote(str(model_dir))}:/root/models \\',
        f'  {docker_profile} \\',
        "  python /root/run_alphafold.py \\",
        "    --input_dir=/root/input/ \\",
        "    --output_dir=/root/output \\",
        "    --model_dir=/root/models \\",
        "    --db_dir=/root/public_databases \\",
        "    --db_dir=/root/public_databases_fallback",
    ])

    run_script_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    run_script_path.chmod(0o755)
    return str(run_script_path)


def render_filter_af3_results(
    request: Request,
    filter_af3_results: Optional[dict] = None,
    message: Optional[str] = None,
    error: Optional[str] = None,
):
    if filter_af3_results is None:
        filter_af3_results = default_filter_af3_results_spec()
    return templates.TemplateResponse(
        "filter_af3_results.html",
        {
            "request": request,
            "filter_af3_results": filter_af3_results,
            "message": message,
            "error": error,
        },
    )


def render_alphafold3(
    request: Request,
    config: Optional[dict] = None,
    alphafold3: Optional[dict] = None,
    message: Optional[str] = None,
    error: Optional[str] = None,
):
    if config is None:
        config = load_config()
    if alphafold3 is None:
        alphafold3 = default_alphafold3_run_spec()
    return templates.TemplateResponse(
        "alphafold3.html",
        {
            "request": request,
            "config": config,
            "alphafold3": alphafold3,
            "message": message,
            "error": error,
        },
    )


@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    return render_home(request=request)


@app.get("/evoef2", response_class=HTMLResponse)
def evoef2_page(request: Request):
    evoef2 = default_evoef2_spec()
    return render_evoef2(request=request, evoef2=evoef2)


@app.get("/evoef2/count", response_class=JSONResponse)
def evoef2_count(input_dir: str = Query(default="")):
    try:
        if not input_dir.strip():
            return {"ok": True, "display_input_dir": "(not set)", "pdb_count": 0}
        scan_dir = Path(input_dir).resolve()
        if not is_allowed_path(scan_dir):
            return {"ok": False, "error": "Input directory is not allowed", "display_input_dir": str(scan_dir), "pdb_count": 0}
        if not scan_dir.exists():
            return {"ok": False, "error": f"Directory does not exist: {scan_dir}", "display_input_dir": str(scan_dir), "pdb_count": 0}
        if not scan_dir.is_dir():
            return {"ok": False, "error": f"Path is not a directory: {scan_dir}", "display_input_dir": str(scan_dir), "pdb_count": 0}
        return {
            "ok": True,
            "display_input_dir": str(scan_dir),
            "pdb_count": count_pdb_files_in_directory(scan_dir),
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc), "display_input_dir": input_dir, "pdb_count": 0}


@app.post("/evoef2", response_class=HTMLResponse)
def evoef2_submit(
    request: Request,
    input_dir: str = Form(...),
    chain_to_design: str = Form(""),
    max_pdbs_to_keep: str = Form(""),
):
    evoef2 = default_evoef2_spec()
    spec = evoef2
    evoef2["input_dir"] = input_dir.strip()
    evoef2["display_input_dir"] = input_dir.strip() or "(not set)"
    evoef2["chain_to_design"] = chain_to_design.strip()
    evoef2["max_pdbs_to_keep"] = max_pdbs_to_keep.strip()

    try:
        scan_dir = Path(input_dir).resolve()
        if not is_allowed_path(scan_dir):
            raise ValueError("Input directory is not allowed")
        if not scan_dir.exists():
            raise ValueError(f"Directory does not exist: {scan_dir}")
        if not scan_dir.is_dir():
            raise ValueError(f"Path is not a directory: {scan_dir}")

        evoef2["display_input_dir"] = str(scan_dir)
        evoef2["pdb_count"] = count_pdb_files_in_directory(scan_dir)

        return render_evoef2(
            request=request,
            evoef2=evoef2,
            message="Directory loaded.",
        )
    except Exception as exc:
        return render_evoef2(
            request=request,
            evoef2=evoef2,
            error=str(exc),
        )



@app.post("/evoef2/run", response_class=JSONResponse)
def evoef2_run(
    input_dir: str = Form(...),
    chain_to_design: str = Form(""),
    max_pdbs_to_keep: str = Form(""),
):
    spec = default_evoef2_spec()
    spec["input_dir"] = input_dir.strip()
    spec["chain_to_design"] = chain_to_design.strip()
    spec["max_pdbs_to_keep"] = max_pdbs_to_keep.strip()
    try:
        import threading
        run_dir = Path(input_dir).resolve()
        if not is_allowed_path(run_dir):
            return JSONResponse({"ok": False, "error": "Input directory is not allowed"}, status_code=400)
        if not run_dir.exists():
            return JSONResponse({"ok": False, "error": f"Directory does not exist: {run_dir}"}, status_code=400)
        if not run_dir.is_dir():
            return JSONResponse({"ok": False, "error": f"Path is not a directory: {run_dir}"}, status_code=400)

        design_chain = chain_to_design.strip()
        if not design_chain:
            return JSONResponse({"ok": False, "error": "Chain to design is required"}, status_code=400)

        keep_n = None
        if str(max_pdbs_to_keep).strip():
            keep_n = int(str(max_pdbs_to_keep).strip())
            if keep_n <= 0:
                raise ValueError("Max PDBs to keep must be a positive integer")

        pdbs = sorted([p for p in run_dir.iterdir() if p.is_file() and p.suffix.lower() == ".pdb"])
        if not pdbs:
            return JSONResponse({"ok": False, "error": "No pdb files found in the input directory"}, status_code=400)

        run_id = datetime.now().strftime("evoef2-%Y%m%d-%H%M%S-%f")
        log_path = run_dir / f"{run_id}.log"

        PROTEINMPNN_RUNS[run_id] = {
        "pdb_count": spec.get("pdb_count", 0),
            "type": "evoef2",
            "status": "running",
            "processed_count": 0,
            "scored_count": 0,
            "kept_count": 0,
            "results": [],
            "error": "",
            "run_log_path": str(log_path),
            "total_count": len(pdbs),
        }
        log_path.write_text(f"Queued {len(pdbs)} pdb files from {run_dir}\n", encoding="utf-8")

        def append_log(message: str):
            with log_path.open("a", encoding="utf-8") as fh:
                fh.write(message + "\n")

        def worker():
            results = []
            try:
                evoef2_executable = load_config().get("evoef2_executable", "EvoEF2") or "EvoEF2"
                for i, pdb_path in enumerate(pdbs, start=1):
                    append_log(f"[{i}/{len(pdbs)}] ProteinDesign: {pdb_path.name}")
                    with log_path.open("a", encoding="utf-8") as lf:
                        subprocess.run(
                            [
                                evoef2_executable,
                                "--command=ProteinDesign",
                                f"--design_chains={design_chain}",
                                f"--pdb={str(pdb_path)}",
                            ],
                            cwd=str(run_dir),
                            check=True,
                            stdout=lf,
                            stderr=subprocess.STDOUT,
                            text=True,
                        )

                    beststruct_path = pdb_path.with_name(f"{pdb_path.stem}_beststruct.pdb")
                    if not beststruct_path.exists():
                        raise FileNotFoundError(f"Expected output not found: {beststruct_path}")

                    append_log(f"[{i}/{len(pdbs)}] ComputeBinding: {beststruct_path.name}")
                    binding = subprocess.run(
                        [
                            evoef2_executable,
                            "--command=ComputeBinding",
                            f"--pdb={str(beststruct_path)}",
                        ],
                        cwd=str(run_dir),
                        check=True,
                        capture_output=True,
                        text=True,
                    )

                    score = parse_evoef2_total_score(binding.stdout)
                    results.append(
                        {
                            "input_pdb": str(pdb_path),
                            "beststruct_pdb": str(beststruct_path),
                            "score": score,
                        }
                    )
                    PROTEINMPNN_RUNS[run_id]["processed_count"] = i
                    if score is not None:
                        PROTEINMPNN_RUNS[run_id]["scored_count"] += 1
                    append_log(f"[{i}/{len(pdbs)}] Done: {beststruct_path.name} | score={score}")

                scored_results = [r for r in results if r["score"] is not None]
                scored_results.sort(key=lambda x: x["score"])
                kept_results = scored_results[:keep_n] if keep_n is not None else scored_results

                best_dir = run_dir / "evoef2_beststructures"
                best_dir.mkdir(parents=True, exist_ok=True)

                for item in kept_results:
                    src_best = Path(item["beststruct_pdb"])
                    if src_best.exists() and src_best.is_file():
                        shutil.copy2(str(src_best), str(best_dir / src_best.name))

                PROTEINMPNN_RUNS[run_id]["results"] = kept_results
                PROTEINMPNN_RUNS[run_id]["kept_count"] = len(kept_results)
                PROTEINMPNN_RUNS[run_id]["status"] = "completed"
                append_log(f"Copied {len(kept_results)} selected best structures to {best_dir}")
                append_log("EvoEF2 run completed.")
            except Exception as exc:
                PROTEINMPNN_RUNS[run_id]["status"] = "failed"
                PROTEINMPNN_RUNS[run_id]["error"] = str(exc)
                append_log(f"ERROR: {exc}")

        threading.Thread(target=worker, daemon=True).start()
        return {"ok": True, "run_id": run_id}
    except Exception as exc:
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=500)


@app.get("/evoef2/status", response_class=JSONResponse)
def evoef2_status(run_id: str = Query(...)):
    run = PROTEINMPNN_RUNS.get(run_id)
    if not run or run.get("type") != "evoef2":
        return JSONResponse({"ok": False, "error": "Run not found"}, status_code=404)
    log_tail = tail_lines(Path(run["run_log_path"]), 20)
    return {
        "ok": True,
        "status": run["status"],
        "processed_count": run.get("processed_count", 0),
        "scored_count": run.get("scored_count", 0),
        "kept_count": run.get("kept_count", 0),
        "results": run.get("results", []),
        "error": run.get("error", ""),
        "log_tail": log_tail,
        "total_count": run.get("total_count", 0),
    }


@app.get("/proteinmpnn", response_class=HTMLResponse)
def proteinmpnn_page(request: Request):
    return render_proteinmpnn(request=request)


@app.get("/proteinmpnn/count", response_class=JSONResponse)
def proteinmpnn_count(input_dir: str = Query(default="")):
    try:
        if not input_dir.strip():
            return {"ok": True, "display_input_dir": "(not set)", "pdb_count": 0}
        scan_dir = Path(input_dir).expanduser().resolve()
        if not is_allowed_path(scan_dir):
            return {"ok": False, "error": "Input directory is not allowed", "display_input_dir": str(scan_dir), "pdb_count": 0}
        if not scan_dir.exists():
            return {"ok": False, "error": f"Directory does not exist: {scan_dir}", "display_input_dir": str(scan_dir), "pdb_count": 0}
        if not scan_dir.is_dir():
            return {"ok": False, "error": f"Path is not a directory: {scan_dir}", "display_input_dir": str(scan_dir), "pdb_count": 0}
        return {
            "ok": True,
            "display_input_dir": str(scan_dir),
            "pdb_count": count_pdb_files_in_directory(scan_dir),
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc), "display_input_dir": input_dir, "pdb_count": 0}


@app.post("/proteinmpnn/compile", response_class=HTMLResponse)
def proteinmpnn_compile(
    request: Request,
    input_dir: str = Form(...),
    output_dir: str = Form(...),
    chain_to_design: str = Form(""),
    num_seq_per_target: str = Form("10"),
    sampling_temp: str = Form("0.4"),
    seed: str = Form("37"),
    batch_size: str = Form("1"),
    omit_aas_list: str = Form(""),
    make_bias_aa_list: str = Form(""),
    make_bias_bias_list: str = Form(""),
    fixed_position_list: str = Form(""),
    target_pdb: str = Form(""),
    target_protein_chain: str = Form(""),
    c_term_trp_count: str = Form("1"),
    options: list[str] = Form(default=[]),
):
    spec = default_proteinmpnn_spec()
    spec["input_dir"] = input_dir.strip()
    spec["display_input_dir"] = input_dir.strip() or "(not set)"
    spec["output_dir"] = output_dir.strip()
    spec["chain_to_design"] = chain_to_design.strip()
    spec["num_seq_per_target"] = num_seq_per_target.strip() or "10"
    spec["sampling_temp"] = sampling_temp.strip() or "0.4"
    spec["seed"] = seed.strip() or "37"
    spec["batch_size"] = batch_size.strip() or "1"
    spec["omit_aas_list"] = omit_aas_list.strip()
    spec["make_bias_aa_list"] = make_bias_aa_list.strip()
    spec["make_bias_bias_list"] = make_bias_bias_list.strip()
    spec["fixed_position_list"] = fixed_position_list.strip()
    spec["target_pdb"] = target_pdb.strip()
    spec["target_protein_chain"] = target_protein_chain.strip()
    spec["c_term_trp_count"] = c_term_trp_count.strip() or "1"
    spec["generate_af3_json_input"] = "generate_af3_json_input" in options
    spec["add_c_term_trp"] = "add_c_term_trp" in options
    spec["omit_aas"] = "omit_aas" in options
    spec["make_bias"] = "make_bias" in options
    spec["fixed_position"] = "fixed_position" in options
    try:
        scan_dir = Path(spec["input_dir"]).expanduser().resolve()
        if not scan_dir.exists() or not scan_dir.is_dir():
            raise ValueError(f"Directory does not exist: {scan_dir}")
        spec["display_input_dir"] = str(scan_dir)
        spec["pdb_count"] = count_pdb_files_in_directory(scan_dir)
        config = load_config()
        spec["run_script_path"] = build_proteinmpnn_script(spec, config)
        return render_proteinmpnn(request=request, proteinmpnn=spec, message=f'Compiled: {spec["run_script_path"]}')
    except Exception as exc:
        return render_proteinmpnn(request=request, proteinmpnn=spec, error=str(exc))


@app.post("/proteinmpnn/run", response_class=JSONResponse)
def proteinmpnn_run(
    input_dir: str = Form(...),
    output_dir: str = Form(...),
    chain_to_design: str = Form(""),
    num_seq_per_target: str = Form("10"),
    sampling_temp: str = Form("0.4"),
    seed: str = Form("37"),
    batch_size: str = Form("1"),
    omit_aas_list: str = Form(""),
    make_bias_aa_list: str = Form(""),
    make_bias_bias_list: str = Form(""),
    fixed_position_list: str = Form(""),
    target_pdb: str = Form(""),
    target_protein_chain: str = Form(""),
    c_term_trp_count: str = Form("1"),
    run_script_path: str = Form(...),
    options: list[str] = Form(default=[]),
):
    spec = default_proteinmpnn_spec()
    spec["input_dir"] = input_dir.strip()
    spec["display_input_dir"] = input_dir.strip() or "(not set)"
    spec["output_dir"] = output_dir.strip()
    spec["chain_to_design"] = chain_to_design.strip()
    spec["num_seq_per_target"] = num_seq_per_target.strip() or "10"
    spec["sampling_temp"] = sampling_temp.strip() or "0.4"
    spec["seed"] = seed.strip() or "37"
    spec["batch_size"] = batch_size.strip() or "1"
    spec["omit_aas_list"] = omit_aas_list.strip()
    spec["make_bias_aa_list"] = make_bias_aa_list.strip()
    spec["make_bias_bias_list"] = make_bias_bias_list.strip()
    spec["fixed_position_list"] = fixed_position_list.strip()
    spec["target_pdb"] = target_pdb.strip()
    spec["target_protein_chain"] = target_protein_chain.strip()
    spec["c_term_trp_count"] = c_term_trp_count.strip() or "1"
    spec["run_script_path"] = run_script_path.strip()
    spec["generate_af3_json_input"] = "generate_af3_json_input" in options
    spec["add_c_term_trp"] = "add_c_term_trp" in options
    spec["omit_aas"] = "omit_aas" in options
    spec["make_bias"] = "make_bias" in options
    spec["fixed_position"] = "fixed_position" in options
    try:
        if not spec["run_script_path"]:
            return JSONResponse({"ok": False, "error": "Compile first."}, status_code=400)

        input_path = Path(spec["input_dir"]).expanduser().resolve()
        if not input_path.exists() or not input_path.is_dir():
            return JSONResponse({"ok": False, "error": f"Directory does not exist: {input_path}"}, status_code=400)
        pdb_count = count_pdb_files_in_directory(input_path)

        output_path = Path(spec["output_dir"]).expanduser().resolve()
        output_path.mkdir(parents=True, exist_ok=True)

        log_path = str(output_path / "proteinmpnn_run.log")
        log_file = open(log_path, "w", encoding="utf-8", buffering=1)
        process = subprocess.Popen(
            ["/bin/bash", spec["run_script_path"]],
            stdout=log_file,
            stderr=subprocess.STDOUT,
            text=True,
        )
        log_file.close()

        run_id = datetime.now().strftime("mpnn-%Y%m%d-%H%M%S-%f")
        PROTEINMPNN_RUNS[run_id] = {
            "type": "proteinmpnn",
            "input_dir": str(input_path),
            "output_dir": str(output_path),
            "run_script_path": spec["run_script_path"],
            "run_log_path": log_path,
            "pid": process.pid,
            "pdb_count": pdb_count,
        }

        return {
            "ok": True,
            "run_id": run_id,
            "run_log_path": log_path,
            "pid": process.pid,
        }
    except Exception as exc:
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=500)


@app.get("/proteinmpnn/status", response_class=JSONResponse)
def proteinmpnn_status(run_id: str = Query(...)):
    run = PROTEINMPNN_RUNS.get(run_id)
    if not run or run.get("type") != "proteinmpnn":
        return JSONResponse({"ok": False, "error": "Run not found"}, status_code=404)

    log_path = Path(run["run_log_path"])
    tail = tail_lines(log_path, 20)
    pid = int(run["pid"])
    running = pid_is_running(pid)

    total_count = int(run.get("pdb_count", 0))
    output_dir = Path(run["output_dir"])
    seqs_dir = output_dir / "seqs"

    processed_count = 0
    if seqs_dir.exists() and seqs_dir.is_dir():
        processed_count = len([p for p in seqs_dir.iterdir() if p.is_file() and p.suffix.lower() in {".fa", ".fasta"}])

    if total_count > 0:
        processed_count = min(processed_count, total_count)

    finished_by_log = False
    stale_log = False
    error_text = ""
    if log_path.exists():
        text = log_path.read_text(encoding="utf-8", errors="replace")
        finished_by_log = "ProteinMPNN run completed." in text
        stale_log = is_log_stale(log_path, 5)
        m = re.findall(r"ERROR:.*", text)
        if m:
            error_text = m[-1]

    status = "finished" if (finished_by_log or ((processed_count >= total_count) and total_count > 0) or stale_log or not running) else "running"

    return {
        "ok": True,
        "status": status,
        "pid": pid,
        "run_log_path": str(log_path),
        "log_tail": tail,
        "completed_steps": processed_count,
        "total_steps": total_count,
        "error": error_text,
    }



@app.post("/proteinmpnn/convert_pdb_to_fasta", response_class=JSONResponse)
def proteinmpnn_convert_pdb_to_fasta(
    target_pdb: str = Form(...),
    target_protein_chain: str = Form(...),
):
    try:
        pdb_path = Path(target_pdb).expanduser().resolve()
        if not is_allowed_path(pdb_path):
            return JSONResponse({"ok": False, "error": "Target PDB path is not allowed"}, status_code=400)
        if not pdb_path.exists():
            return JSONResponse({"ok": False, "error": f"Target PDB does not exist: {pdb_path}"}, status_code=400)
        if not pdb_path.is_file():
            return JSONResponse({"ok": False, "error": f"Target PDB is not a file: {pdb_path}"}, status_code=400)

        chain = target_protein_chain.strip()
        if not chain:
            return JSONResponse({"ok": False, "error": "Target protein chain is required"}, status_code=400)

        script_path = BASE_DIR / "scripts" / "pdb2fasta2.sh"
        if not script_path.exists():
            return JSONResponse({"ok": False, "error": f"pdb2fasta2 not found: {script_path}"}, status_code=400)

        fasta_path = pdb_path.with_suffix(".fasta")
        with fasta_path.open("w", encoding="utf-8") as out_f:
            result = subprocess.run(
                ["/bin/bash", str(script_path), str(pdb_path), chain],
                cwd=str(BASE_DIR),
                stdout=out_f,
                stderr=subprocess.PIPE,
                text=True,
            )

        if result.returncode != 0:
            try:
                fasta_path.unlink(missing_ok=True)
            except Exception:
                pass
            err = (result.stderr or "").strip() or "Failed to convert pdb to fasta."
            return JSONResponse({"ok": False, "error": err}, status_code=500)

        return {
            "ok": True,
            "fasta_path": str(fasta_path),
            "message": f"FASTA created: {fasta_path}",
        }
    except Exception as exc:
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=500)


@app.get("/filter_af3_results", response_class=HTMLResponse)
def filter_af3_results_page(request: Request):
    return render_filter_af3_results(request=request)


@app.post("/filter_af3_results", response_class=HTMLResponse)
def filter_af3_results_submit(
    request: Request,
    dir: str = Form(""),
    iptm: str = Form(""),
    ptm: str = Form(""),
    filtered_dir: str = Form(""),
    score: str = Form(""),
    pae: str = Form(""),
    chain_id: str = Form(""),
    max_output: str = Form(""),
):
    spec = default_filter_af3_results_spec()
    spec["dir"] = dir.strip()
    spec["iptm"] = iptm.strip()
    spec["ptm"] = ptm.strip()
    spec["filtered_dir"] = filtered_dir.strip()
    spec["score"] = score.strip()
    spec["pae"] = pae.strip()
    spec["chain_id"] = chain_id.strip()
    spec["max_output"] = max_output.strip()

    try:
        af3_filter_script = BASE_DIR / "scripts" / "AF3_filter.sh"
        if not af3_filter_script.exists():
            return render_filter_af3_results(
                request=request,
                filter_af3_results=spec,
                error=f"AF3_filter.sh not found: {af3_filter_script}",
            )

        json_dir = Path(spec["dir"]).expanduser().resolve()
        if not spec["dir"]:
            return render_filter_af3_results(
                request=request,
                filter_af3_results=spec,
                error="AlphaFold 3 output directory is required.",
            )
        if not json_dir.exists() or not json_dir.is_dir():
            return render_filter_af3_results(
                request=request,
                filter_af3_results=spec,
                error=f"Directory does not exist: {json_dir}",
            )

        filtered_dir = Path(spec["filtered_dir"]).expanduser().resolve() if spec["filtered_dir"] else None
        if filtered_dir:
            filtered_dir.mkdir(parents=True, exist_ok=True)

        cmd = [str(af3_filter_script), "--dir", str(json_dir)]
        if spec["iptm"]:
            cmd.extend(["--iptm", spec["iptm"]])
        if spec["ptm"]:
            cmd.extend(["--ptm", spec["ptm"]])
        if spec["score"]:
            cmd.extend(["--score", spec["score"]])
        if spec["pae"]:
            cmd.extend(["--pae", spec["pae"]])
        if spec["chain_id"]:
            cmd.extend(["--chain_id", spec["chain_id"]])
        if spec["max_output"]:
            cmd.extend(["--max_output", spec["max_output"]])

        result = subprocess.run(
            ["/bin/bash", *cmd],
            cwd=str(BASE_DIR),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        if result.returncode != 0:
            err = (result.stderr or "").strip() or "AF3 filter run failed."
            return render_filter_af3_results(
                request=request,
                filter_af3_results=spec,
                error=err,
            )

        project_results_csv = BASE_DIR / "results.csv"
        if filtered_dir and project_results_csv.exists():
            destination = filtered_dir / "results.csv"
            shutil.move(str(project_results_csv), str(destination))

            copied_cif_count = 0
            missing_cif_count = 0

            try:
                with destination.open("r", encoding="utf-8", errors="replace") as f:
                    lines = f.read().splitlines()

                start_idx = None
                for i, line in enumerate(lines):
                    if "filename" in line.lower():
                        start_idx = i + 1
                        break

                if start_idx is not None:
                    for line in lines[start_idx:]:
                        matches = re.findall(r'([^,\s]+\.json)\b', line)
                        if not matches:
                            continue

                        json_name = Path(matches[0]).name
                        json_stem = Path(json_name).stem

                        # Convert e.g.
                        # 1_0_beststruct_job_8_seed-3658293744_sample-1_summary_confidences.json
                        # -> search prefix:
                        # 1_0_beststruct_job_8_seed-3658293744_sample-1
                        search_key = re.sub(r'_summary_confidences$', '', json_stem)

                        matched_cif = None
                        for candidate in sorted(json_dir.rglob("*.cif")):
                            if search_key in candidate.name:
                                matched_cif = candidate
                                break

                        if matched_cif and matched_cif.exists() and matched_cif.is_file():
                            shutil.copy2(str(matched_cif), str(filtered_dir / matched_cif.name))
                            copied_cif_count += 1
                        else:
                            missing_cif_count += 1

                message = (
                    f"AF3 filter run completed. Moved results.csv to {destination}. "
                    f"Copied {copied_cif_count} cif files"
                    + (f"; {missing_cif_count} missing." if missing_cif_count else ".")
                )
            except Exception as exc:
                message = (
                    f"AF3 filter run completed. Moved results.csv to {destination}, "
                    f"but failed to copy cif files: {exc}"
                )
        else:
            message = (result.stdout or "").strip() or "AF3 filter run completed."

        return render_filter_af3_results(
            request=request,
            filter_af3_results=spec,
            message=message,
        )
    except Exception as exc:
        return render_filter_af3_results(
            request=request,
            filter_af3_results=spec,
            error=str(exc),
        )


@app.get("/alphafold3", response_class=HTMLResponse)
def alphafold3_page(request: Request):
    return render_alphafold3(request=request)


@app.post("/alphafold3", response_class=HTMLResponse)
def alphafold3_submit(
    request: Request,
    input_json_dir: str = Form(""),
    output_dir: str = Form(""),
    gpu: str = Form("0"),
):
    spec = default_alphafold3_run_spec()
    spec["input_json_dir"] = input_json_dir.strip()
    spec["output_dir"] = output_dir.strip()
    spec["gpu"] = gpu.strip() or "0"
    try:
        config = load_config()
        spec["run_script_path"] = build_alphafold3_script(spec, config)
        return render_alphafold3(request=request, config=config, alphafold3=spec, message=f'Compiled: {spec["run_script_path"]}')
    except Exception as exc:
        return render_alphafold3(request=request, config=load_config(), alphafold3=spec, error=str(exc))


@app.post("/alphafold3/run", response_class=JSONResponse)
def alphafold3_run(
    input_json_dir: str = Form(""),
    output_dir: str = Form(""),
    gpu: str = Form("0"),
    run_script_path: str = Form(...),
):
    spec = default_alphafold3_run_spec()
    spec["input_json_dir"] = input_json_dir.strip()
    spec["output_dir"] = output_dir.strip()
    spec["gpu"] = gpu.strip() or "0"
    spec["run_script_path"] = run_script_path.strip()
    try:
        if not spec["run_script_path"]:
            return JSONResponse({"ok": False, "error": "Compile first."}, status_code=400)

        input_dir = Path(spec["input_json_dir"]).expanduser().resolve()
        if not input_dir.exists() or not input_dir.is_dir():
            return JSONResponse({"ok": False, "error": f"Directory does not exist: {input_dir}"}, status_code=400)

        output_dir = Path(spec["output_dir"]).expanduser().resolve()
        output_dir.mkdir(parents=True, exist_ok=True)

        log_path = output_dir / "alphafold3_run.log"
        log_file = open(log_path, "w", encoding="utf-8", buffering=1)
        process = subprocess.Popen(
            ["/bin/bash", spec["run_script_path"]],
            stdout=log_file,
            stderr=subprocess.STDOUT,
            text=True,
        )
        log_file.close()

        input_json_count = len([p for p in input_dir.iterdir() if p.is_file() and p.suffix.lower() == ".json"])
        cidfile_path = output_dir / "alphafold3.cid"

        run_id = datetime.now().strftime("af3-%Y%m%d-%H%M%S-%f")
        ALPHAFOLD3_RUNS[run_id] = {
            "type": "alphafold3",
            "input_json_dir": str(input_dir),
            "output_dir": str(output_dir),
            "run_script_path": spec["run_script_path"],
            "run_log_path": str(log_path),
            "pid": process.pid,
            "input_json_count": input_json_count,
            "cidfile_path": str(cidfile_path),
        }

        return {
            "ok": True,
            "run_id": run_id,
            "run_log_path": str(log_path),
            "pid": process.pid,
        }
    except Exception as exc:
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=500)


@app.post("/alphafold3/stop", response_class=JSONResponse)
def alphafold3_stop(run_id: str = Form(...)):
    run = ALPHAFOLD3_RUNS.get(run_id)
    if not run or run.get("type") != "alphafold3":
        return JSONResponse({"ok": False, "error": "Run not found"}, status_code=404)

    try:
        container_id = ""
        cidfile_str = run.get("cidfile_path")
        if cidfile_str:
            cidfile_path = Path(cidfile_str)
            if cidfile_path.exists() and cidfile_path.is_file():
                container_id = cidfile_path.read_text(encoding="utf-8", errors="replace").strip()

        if not container_id:
            return JSONResponse({"ok": False, "error": "Container ID not found for this run"}, status_code=404)

        kill_res = subprocess.run(
            ["docker", "kill", container_id],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        if kill_res.returncode != 0:
            err = (kill_res.stderr or "").strip() or "Failed to stop container."
            return JSONResponse({"ok": False, "error": err}, status_code=500)

        return {"ok": True, "container_id": container_id}

    except Exception as exc:
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=500)


@app.get("/alphafold3/status", response_class=JSONResponse)
def alphafold3_status(run_id: str = Query(...)):
    run = ALPHAFOLD3_RUNS.get(run_id)
    if not run or run.get("type") != "alphafold3":
        return JSONResponse({"ok": False, "error": "Run not found"}, status_code=404)

    log_path = Path(run["run_log_path"])
    tail = tail_lines(log_path, 50)
    pid = int(run["pid"])
    running = pid_is_running(pid)
    output_dir = Path(run["output_dir"])
    input_json_count = int(run.get("input_json_count", 0))

    output_folder_count = 0
    if output_dir.exists() and output_dir.is_dir():
        output_folder_count = len([
            p for p in output_dir.iterdir()
            if p.is_dir() and not p.name.startswith(".")
        ])

    if input_json_count > 0:
        output_folder_count = min(output_folder_count, input_json_count)

    finished_by_log = False
    stale_log = False
    error_text = ""
    if log_path.exists():
        text = log_path.read_text(encoding="utf-8", errors="replace")
        finished_by_log = (
            "Done" in text
            or "done" in text
            or "Completed" in text
            or "completed" in text
        )
        stale_log = is_log_stale(log_path, 5)
        if "Traceback" in text:
            error_text = "AlphaFold 3 run failed."
        else:
            matches = re.findall(r"ERROR:.*", text)
            if matches:
                error_text = matches[-1]

    status = "finished" if (
        (input_json_count > 0 and output_folder_count >= input_json_count)
        or (finished_by_log and not running)
        or (stale_log and not running)
        or (not running and output_folder_count >= input_json_count and input_json_count > 0)
    ) else "running"

    return {
        "ok": True,
        "status": status,
        "pid": pid,
        "run_log_path": str(log_path),
        "log_tail": tail,
        "completed_steps": output_folder_count,
        "total_steps": input_json_count,
        "output_folder_count": output_folder_count,
        "error": error_text,
    }


@app.get("/alphafold3/count_json", response_class=JSONResponse)
def alphafold3_count_json(input_json_dir: str = Query(default="")):
    try:
        if not input_json_dir.strip():
            return {"ok": True, "json_count": 0, "display_input_json_dir": "(not set)"}
        path = Path(input_json_dir).expanduser().resolve()
        if not is_allowed_path(path):
            return JSONResponse({"ok": False, "error": "Input json file directory is not allowed", "json_count": 0, "display_input_json_dir": str(path)}, status_code=400)
        if not path.exists():
            return JSONResponse({"ok": False, "error": f"Directory does not exist: {path}", "json_count": 0, "display_input_json_dir": str(path)}, status_code=400)
        if not path.is_dir():
            return JSONResponse({"ok": False, "error": f"Path is not a directory: {path}", "json_count": 0, "display_input_json_dir": str(path)}, status_code=400)
        count = len([p for p in path.iterdir() if p.is_file() and p.suffix.lower() == ".json"])
        return {"ok": True, "json_count": count, "display_input_json_dir": str(path)}
    except Exception as exc:
        return JSONResponse({"ok": False, "error": str(exc), "json_count": 0, "display_input_json_dir": input_json_dir or "(not set)"}, status_code=500)


@app.get("/options", response_class=HTMLResponse)
def options_page(request: Request):
    return render_options(request=request)


@app.post("/options/save", response_class=HTMLResponse)
def save_options(
    request: Request,
    rfd_executable: str = Form(...),
    env_setup: str = Form(...),
    evoef2_executable: str = Form(""),
    proteinmpnn_dir: str = Form(""),
    proteinmpnn_env_setup: str = Form(""),
    alphafold3_root_dir: str = Form(""),
    alphafold3_database_dir: str = Form(""),
    alphafold3_model_dir: str = Form(""),
    alphafold3_docker_profile: str = Form(""),
    alphafold3_environment: str = Form(""),
):
    config = load_config()
    config["rfd_executable"] = rfd_executable.strip()
    config["env_setup"] = env_setup.strip()
    config["evoef2_executable"] = evoef2_executable.strip()
    config["proteinmpnn_dir"] = proteinmpnn_dir.strip()
    config["proteinmpnn_env_setup"] = proteinmpnn_env_setup.strip()
    config["alphafold3_root_dir"] = alphafold3_root_dir.strip()
    config["alphafold3_database_dir"] = alphafold3_database_dir.strip()
    config["alphafold3_model_dir"] = alphafold3_model_dir.strip()
    config["alphafold3_docker_profile"] = alphafold3_docker_profile.strip()
    config["alphafold3_environment"] = alphafold3_environment.strip()
    try:
        save_config(config)
        return render_options(request=request, message="Options saved.")
    except Exception as exc:
        return render_options(request=request, error=str(exc))


@app.get("/browse", response_class=HTMLResponse)
def browse(
    request: Request,
    path: Optional[str] = Query(default=None),
    target_id: str = Query(default="target_pdb"),
    select: str = Query(default="file"),
):
    current = normalize_path(path)
    return templates.TemplateResponse(
        "browser.html",
        {
            "request": request,
            "current_path": str(current),
            "entries": list_entries(current, select),
            "parent_path": parent_path(current),
            "target_id": target_id,
            "select_mode": select,
        },
    )


@app.get("/run-status", response_class=JSONResponse)
def run_status(log_path: str = Query(...), pid: int = Query(...), total_designs: int = Query(0)):
    log_file = Path(log_path).resolve()
    if not is_allowed_path(log_file):
        return JSONResponse({"error": "log path is not allowed"}, status_code=400)
    return {
        "is_running": pid_is_running(pid),
        "log_tail": tail_lines(log_file, max_lines=20),
        "completed_designs": count_completed_designs(log_file),
        "total_designs": total_designs,
    }


def start_background_run(run_path: Path, log_path: Path, workdir: Path) -> int:
    launcher_path = workdir / f".launch_{run_path.stem}.sh"
    launcher_text = "\n".join([
        "#!/bin/bash -l",
        "set -e",
        f"cd '{workdir}'",
        "{",
        f"  echo '[launcher] started at {datetime.now().isoformat(timespec='seconds')}'",
        f"  echo '[launcher] cwd: {workdir}'",
        f"  echo '[launcher] script: {run_path}'",
        f"  bash '{run_path}'",
        "  rc=$?",
        "  echo \"[launcher] finished with exit code: $rc\"",
        "  exit $rc",
        "} >> '" + str(log_path) + "' 2>&1",
    ]) + "\n"
    launcher_path.write_text(launcher_text, encoding="utf-8")
    launcher_path.chmod(0o755)

    cmd = f"nohup /bin/bash -l '{launcher_path}' >/dev/null 2>&1 & echo $!"
    result = subprocess.run(["/bin/bash", "-lc", cmd], capture_output=True, text=True, check=True)
    pid_text = result.stdout.strip().splitlines()[-1].strip()
    if not pid_text.isdigit():
        raise RuntimeError(f"Failed to start run. Launcher output: {result.stdout}\n{result.stderr}")
    return int(pid_text)


def build_run_script(spec: dict, config: dict) -> str:
    executable = config.get("rfd_executable", "").strip()
    if not executable:
        raise ValueError("RFdiffusion executable is not set in Options.")

    env_setup = config.get("env_setup", "").strip()
    output_prefix = Path(spec["output_dir"]).resolve() / "rfd_result" / (spec["output_prefix"] or "result")

    lines = [
        "#!/bin/bash",
        "set -euo pipefail",
        "",
    ]

    if env_setup:
        for line in env_setup.splitlines():
            line = line.strip()
            if line:
                lines.append(line)
        lines.append("")

    lines.extend([
        f"export CUDA_VISIBLE_DEVICES={spec['gpu_id']}",
        "",
        f"python {executable} \\",
        f"  'contigmap.contigs={spec['contigs']}' \\",
        f"  inference.input_pdb={spec['target_pdb']} \\",
        f"  inference.output_prefix={output_prefix} \\",
    ])

    if spec["partial_t_value"]:
        lines.append(f"  diffuser.partial_T={spec['partial_t_value']} \\")

    if spec["hotspot_chain"] and spec["hotspot_residues"]:
        residues = [x.strip() for x in spec["hotspot_residues"].split(",") if x.strip()]
        hotspot_list = ", ".join(f"{spec['hotspot_chain']}{r}" for r in residues)
        lines.append(f"  'ppi.hotspot_res=[{hotspot_list}]' \\")

    lines.extend([
        f"  inference.num_designs={spec['num_backbones']} \\",
        f"  denoiser.noise_scale_ca={spec['noise_scale_ca']} \\",
        f"  denoiser.noise_scale_frame={spec['noise_scale_frame']}",
    ])
    return "\n".join(lines)


def parse_form_to_spec(
    mode: str,
    target_pdb: str,
    contigs: str,
    target_chain: str,
    target_start: str,
    target_end: str,
    design_min: str,
    design_max: str,
    partial_target_chain: str,
    partial_target_start: str,
    partial_target_end: str,
    partial_design_length: str,
    custom_contig: str,
    hotspot_chain: str,
    hotspot_residues: str,
    num_backbones: int,
    noise_scale_ca: float,
    noise_scale_frame: float,
    output_dir: str,
    output_prefix: str,
    partial_t_value: str,
    gpu_id: str,
    run_script_path: str = "",
    run_log_path: str = "",
) -> dict:
    return {
        "mode": mode.strip() or "basic",
        "target_pdb": target_pdb.strip(),
        "contigs": contigs.strip(),
        "target_chain": target_chain.strip(),
        "target_start": target_start.strip(),
        "target_end": target_end.strip(),
        "design_min": design_min.strip(),
        "design_max": design_max.strip(),
        "partial_target_chain": partial_target_chain.strip(),
        "partial_target_start": partial_target_start.strip(),
        "partial_target_end": partial_target_end.strip(),
        "partial_design_length": partial_design_length.strip(),
        "custom_contig": custom_contig.strip(),
        "hotspot_chain": hotspot_chain.strip(),
        "hotspot_residues": hotspot_residues.strip(),
        "num_backbones": num_backbones,
        "noise_scale_ca": noise_scale_ca,
        "noise_scale_frame": noise_scale_frame,
        "output_dir": output_dir.strip(),
        "output_prefix": output_prefix.strip(),
        "partial_t_value": partial_t_value.strip(),
        "gpu_id": gpu_id.strip() or "0",
        "run_script_path": run_script_path.strip(),
        "run_log_path": run_log_path.strip(),
    }


@app.post("/compile", response_class=HTMLResponse)
def compile_workflow(
    request: Request,
    target_pdb: str = Form(...),
    contigs: str = Form(""),
    mode: str = Form("basic"),
    target_chain: str = Form(""),
    target_start: str = Form(""),
    target_end: str = Form(""),
    design_min: str = Form(""),
    design_max: str = Form(""),
    partial_target_chain: str = Form(""),
    partial_target_start: str = Form(""),
    partial_target_end: str = Form(""),
    partial_design_length: str = Form(""),
    custom_contig: str = Form(""),
    hotspot_chain: str = Form(""),
    hotspot_residues: str = Form(""),
    num_backbones: int = Form(1000),
    noise_scale_ca: float = Form(1),
    noise_scale_frame: float = Form(1),
    output_dir: str = Form(...),
    output_prefix: str = Form(""),
    partial_t_value: str = Form(""),
    gpu_id: str = Form("0"),
    submit_action: str = Form("compile"),
    run_script_path: str = Form(""),
    run_log_path: str = Form(""),
):
    spec = parse_form_to_spec(
        mode=mode,
        target_pdb=target_pdb,
        contigs=contigs,
        target_chain=target_chain,
        target_start=target_start,
        target_end=target_end,
        design_min=design_min,
        design_max=design_max,
        partial_target_chain=partial_target_chain,
        partial_target_start=partial_target_start,
        partial_target_end=partial_target_end,
        partial_design_length=partial_design_length,
        custom_contig=custom_contig,
        hotspot_chain=hotspot_chain,
        hotspot_residues=hotspot_residues,
        num_backbones=num_backbones,
        noise_scale_ca=noise_scale_ca,
        noise_scale_frame=noise_scale_frame,
        output_dir=output_dir,
        output_prefix=output_prefix,
        partial_t_value=partial_t_value,
        gpu_id=gpu_id,
        run_script_path=run_script_path,
        run_log_path=run_log_path,
    )

    try:
        outdir = Path(spec["output_dir"]).resolve()
        if not is_allowed_path(outdir):
            raise ValueError("Output directory is not allowed")
        outdir.mkdir(parents=True, exist_ok=True)

        if submit_action == "compile":
            if not spec["contigs"]:
                raise ValueError("Contig is required")

            timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            prefix = spec["output_prefix"] or "rfd"

            config = load_config()
            run_script = build_run_script(spec, config)
            spec_json = json.dumps(spec, indent=2)

            run_path = outdir / f"{prefix}_{timestamp}.sh"
            spec_path = outdir / f"{prefix}_{timestamp}.json"
            log_path = outdir / f"{prefix}_{timestamp}.log"

            run_path.write_text(run_script, encoding="utf-8")
            run_path.chmod(0o755)
            spec_path.write_text(spec_json, encoding="utf-8")

            spec["run_script_path"] = str(run_path)
            spec["run_log_path"] = str(log_path)

            details = [
                f"Output directory: {outdir}",
                "",
                "Generated files:",
                str(run_path),
                str(spec_path),
                "",
                "Run script preview:",
                run_script,
            ]

            return render_home(
                request=request,
                spec=spec,
                compile_result="\n".join(details),
                message="Compile completed",
            )

        if submit_action == "run":
            run_path = Path(spec["run_script_path"]).resolve()
            log_path = Path(spec["run_log_path"]).resolve() if spec["run_log_path"] else (outdir / "rfd_run.log")

            if not spec["run_script_path"]:
                raise ValueError("Compile first to generate a run script.")
            if not is_allowed_path(run_path):
                raise ValueError("Run script path is not allowed")
            if not run_path.exists():
                raise ValueError("Compiled run script does not exist. Compile again.")
            if not is_allowed_path(log_path):
                raise ValueError("Log path is not allowed")

            log_path.write_text(
                "[web] run requested\n"
                f"[web] script: {run_path}\n"
                f"[web] requested at: {datetime.now().isoformat(timespec='seconds')}\n",
                encoding="utf-8",
            )

            pid = start_background_run(run_path=run_path, log_path=log_path, workdir=outdir)
            initial_log_tail = tail_lines(log_path, max_lines=20)
            completed_designs = count_completed_designs(log_path)

            details = [
                f"Output directory: {outdir}",
                "",
                "Run file:",
                str(run_path),
                "",
                f"Run started with PID: {pid}",
                f"Log file: {log_path}",
            ]

            return render_home(
                request=request,
                spec=spec,
                compile_result="\n".join(details),
                message="RFdiffusion run started",
                current_log_path=str(log_path),
                current_pid=str(pid),
                initial_log_tail=initial_log_tail,
                completed_designs=completed_designs,
                total_designs=spec["num_backbones"],
            )

        raise ValueError(f"Unknown submit action: {submit_action}")

    except Exception as exc:
        return render_home(
            request=request,
            spec=spec,
            error=str(exc),
        )
