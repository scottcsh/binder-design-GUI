<p align="center">
<img src="./app/static/banner.png" alt="banner" width="100%"/>
</p>

# Binder Design GUI

A lightweight web UI for running and chaining several structure-design workflows:

- **RFdiffusion**
- **EvoEF2**
- **ProteinMPNN**
- **AlphaFold 3**
- **AF3 result filtering**

The interface is designed for local or server-side use and focuses on practical pipeline execution rather than full workflow orchestration frameworks.

---

## Table of Contents
- [Installation](#Installation)
- [System Requirements](#System-Requirements)
- [First-run Configuration](#First-run-Configuration)
- [Running the App](#Running-the-App)
- [Acknowledgements](#Acknowledgements)

---

## Installation

```bash
git clone https://github.com/scottcsh/binder-design-GUI
```

## System Requirements

This project depends on several **external tools** that are **not Python packages**.

- RFdiffusion (https://github.com/RosettaCommons/RFdiffusion)
- EvoEF2 (https://github.com/tommyhuangthu/EvoEF2)
- ProteinMPNN (https://github.com/dauparas/ProteinMPNN)
- AlphaFold 3 runtime/image (https://github.com/google-deepmind/alphafold3)
  
- `jq` for scripts that require JSON processing

```bash
yum install jq -y
```

Create a virtual environment and install your Python dependencies:

```bash
python -m venv .venv
source .venv/bin/activate
pip install fastapi uvicorn jinja2 python-multipart
```

Add any additional project-specific Python requirements as needed.

---

## First-run Configuration

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

---

## Running the App

From the project root:

```bash
./scripts/start_server.sh
```

Then open in local web browser:

```text
http://127.0.0.1:65022
```
or in remote browser with IP x.x.x.x
```text
http://x.x.x.x:65022
```

---

## Acknowledgements

This GUI is a thin interface layer around external tools including:
- RFdiffusion
- EvoEF2
- ProteinMPNN
- AlphaFold 3

Please follow the licenses and usage requirements of each upstream project.

</br>
</br>

[Return to top](#Table-of-Contents)
