# Binder Design GUI

A lightweight web UI for running and chaining several structure-design workflows:

- **RFdiffusion**
- **EvoEF2**
- **ProteinMPNN**
- **AlphaFold 3**
- **AF3 result filtering**

The interface is designed for local or server-side use and focuses on practical pipeline execution rather than full workflow orchestration frameworks.

---

## Features

### RFdiffusion
- Configure RFdiffusion executable and environment
- Set target / contig / hotspot options in the UI
- Generate and run inference scripts
- Track progress from the web page

### EvoEF2
- Run `ProteinDesign` and `ComputeBinding` for a directory of PDB files
- Rank structures by EvoEF2 binding score
- Keep top `N` structures with **Max PDBs to keep**
- Automatically copy selected best structures into:

```text
<input_directory>/evoef2_beststructures/
```

### ProteinMPNN
- Parse PDB directories and assign design chains
- Configure common ProteinMPNN options:
  - output directory
  - chain to design
  - number of sequences per target
  - sampling temperature
  - seed
  - batch size
- Optional features:
  - omit amino acids
  - amino-acid bias
  - fixed positions
  - generate AlphaFold 3 JSON inputs
- Convert target PDB to FASTA from the UI
- Real-time run progress monitoring

### AlphaFold 3
- Configure AlphaFold 3 environment from the Options page
- Set:
  - input JSON directory
  - output directory
  - GPU
- Compile run scripts from the UI
- Run AlphaFold 3 jobs from the UI
- Monitor progress in real time
- Stop jobs by killing the exact Docker container created for that run

### Filter AF3 Results
- Run `scripts/AF3_filter.sh` from the UI
- Filter based on:
  - `iptm`
  - `ptm`
  - ranking score
  - `PAE`
  - chain ID
  - maximum number of outputs
- Move generated `results.csv` into the selected filtered-result directory
- Copy matching CIF files from the AlphaFold 3 output tree into the filtered-result directory

---

## Repository Structure

```text
app/
  templates/
  static/
  web.py

scripts/
  AF3_filter.sh
  pdb2fasta2.sh
  mpnn2afserver.sh
  ...

data/
  app_config.json
```

---

## System Requirements

This project depends on several **external tools** that are **not Python packages**.

### Required / commonly used tools
- Python 3.10+
- FastAPI
- Uvicorn
- RFdiffusion
- EvoEF2
- ProteinMPNN
- Docker
- AlphaFold 3 runtime/image
- `jq` for scripts that require JSON processing

### Example Ubuntu packages

```bash
sudo apt-get update
sudo apt-get install -y jq docker.io
```

### Python packages

Create a virtual environment and install your Python dependencies:

```bash
python -m venv .venv
source .venv/bin/activate
pip install fastapi uvicorn jinja2 python-multipart
```

Add any additional project-specific Python requirements as needed.

---

## Configuration

Open the **Options** page and configure the paths used by the GUI.

### RFdiffusion
- RFdiffusion executable
- RFdiffusion environment

### EvoEF2
- EvoEF2 executable

### ProteinMPNN
- ProteinMPNN directory
- ProteinMPNN environment

### AlphaFold 3
- Root directory
- Database directory
- Model directory
- Docker profile
- Environment

These values are stored in:

```text
data/app_config.json
```

Do **not** commit personal or machine-specific paths if you are publishing this repository.

---

## Running the App

From the project root:

```bash
uvicorn app.web:app --host 0.0.0.0 --port 8000
```

Then open:

```text
http://localhost:8000
```

---

## Important Runtime Notes

### 1. jq is a system dependency
`jq` must be installed at the OS level.  
It cannot be added through `requirements.txt`.

### 2. Large databases should not be committed
Do not commit AlphaFold databases, model weights, generated JSON files, CIF files, or run outputs.

### 3. Docker is required for AlphaFold 3
The AF3 page assumes that Docker is available and usable by the current user.

### 4. Environment blocks are shell snippets
The environment fields in Options are inserted into generated shell scripts.  
Use valid shell commands only.

---

## Recommended `.gitignore`

Create a `.gitignore` like this:

```gitignore
# Python
__pycache__/
*.pyc
*.pyo

# Virtual environments
.venv/

# Logs
*.log
*.out
*.err

# Generated outputs
outputs/
seqs/
AF3_jsons/
evoef2_beststructures/
results.csv

# AF3 / structure outputs
*.cif
*.json

# Large resources
public_databases/
models/

# Local config / secrets
.env
data/app_config.json

# OS files
.DS_Store
```

If you want to keep a tracked example config, use something like:

```text
data/app_config.example.json
```

instead of committing the real local config.

---

## Suggested Publishing Checklist

Before pushing to GitHub, check the following:

- Remove all machine-specific absolute paths
- Remove personal server paths such as `/home/...`
- Do not commit databases or model weights
- Do not commit generated run outputs
- Do not commit local logs
- Keep scripts and templates only
- Provide setup instructions for external dependencies

---

## Known Assumptions

This GUI assumes a workflow where:
- RFdiffusion, EvoEF2, ProteinMPNN, and AF3 are already installed or accessible
- the user has permission to execute Docker commands
- shell scripts in `scripts/` are available and executable
- output folders are writable

---

## License

Add your preferred license here before publishing.

Example:

```text
MIT License
```

---

## Acknowledgements

This GUI is a thin interface layer around external tools including:
- RFdiffusion
- EvoEF2
- ProteinMPNN
- AlphaFold 3

Please follow the licenses and usage requirements of each upstream project.
