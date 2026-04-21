# VS Protocol — Virtual Screening Workflow Manager

A web-based tool for end-to-end virtual screening (VS) workflows: configuration editing, flow control, and live log monitoring.

---

## Pipeline overview

```
Library prep → Receptor prep → Prescreening → Ligand prep → Docking → Results analysis
     (1)            (2)            (3)          (4)           (5)          (6)
```

| Step | Module | Description |
|------|--------|-------------|
| 1 | Library preprocessing | SMILES normalization, deduplication, salt stripping |
| 2 | Receptor preparation | PDB cleanup → PDBQT, automatic docking box extraction |
| 3 | Prescreening | Physicochemical / ADMET / drug-likeness filters (each can be enabled independently) |
| 4 | Ligand preparation | 3D conformer generation, conversion to PDBQT |
| 5 | Docking | UniDock scoring, pose extraction, H-bond key-residue filtering |
| 6 | Results analysis | Consolidate outputs from docking with upstream context into ranked hit lists, summaries, and export-ready reports for triage.|

---

## Repository layout

```
vs_protocol/
├── app.py                    # Flask web server
├── vs_protocol.py            # Main pipeline (CLI entry point)
├── start_web.sh              # One-command web startup
├── requirements.txt          # Python dependencies
├── config.yaml               # Pipeline config template
│
├── templates/index.html      # Frontend
├── static/
│   ├── style.css
│   └── script.js
│
├── pc_filter/                # Physicochemical properties & filtering
│   └── physchem.py
├── admet_filter/             # ADMET prediction & filtering
│   ├── admetlab_prepare.py
│   ├── admetlab_predict.py
│   └── admetlab_score.py
├── druglikeness/             # Deep learning drug-likeness prediction
│   └── druglikeness/
│       ├── launch_dln_tasks.py
│       └── predict.py
├── docking/                  # Docking utilities
│   ├── distributed_prepare_ligand.py
│   ├── distributed_unidock.py
│   ├── extract_vina_score.py
│   ├── hbond_plip.py
│   └── hbond_pymol.py
├── utils/                    # Shared helpers
│   ├── utils.py
│   ├── get_box.py
│   ├── library_preprocess.py
│   └── parse_nvidia_smi.py
│
└── weights/                  # Model weights (download separately; see below)
    └── druglikeness/
```

---

## Installation

### 1. Create a Conda environment (recommended)

```bash
conda create -n vs_protocol python=3.10
conda activate vs_protocol
```

### 2. Install RDKit

```bash
conda install -c conda-forge rdkit
```

### 3. Install Python dependencies

```bash
pip install -r requirements.txt
```

> **Note:** Some packages in `requirements.txt` (PyBioMed, PLIP, PyTorch) need extra steps; see below.

### 4. Install PyBioMed

```bash
pip install git+https://github.com/gadsbyfly/PyBioMed.git
```

### 5. Install PyTorch (match your CUDA version)

```bash
# CUDA 11.8
pip install torch --index-url https://download.pytorch.org/whl/cu118

# CUDA 12.1
pip install torch --index-url https://download.pytorch.org/whl/cu121

# CPU only
pip install torch
```

### 6. Install PLIP (H-bond analysis, optional)

```bash
conda install -c conda-forge plip
```

### 7. Install PyMOL (H-bond analysis; use PLIP **or** PyMOL)

```bash
conda install -c conda-forge pymol-open-source
```

---

## External tools

These cannot be installed via pip alone; configure them manually.

### UniDock (docking engine)

```bash
# Download prebuilt binaries from GitHub
# https://github.com/dptech-corp/Uni-Dock/releases
```

After installation, set the `unidock` executable path in `docking/distributed_unidock.py`.

### prepare_receptor (receptor preparation)

From **ADFR Suite** (AutoDock Tools):

```
https://ccsb.scripps.edu/adfr/downloads/
```

After installation, update the path in `vs_protocol.py`:

```python
PREPARE_RECEPTOR = '/path/to/bin/prepare_receptor'
```

---

## Model weights

### Drug-likeness models

Place weights under `weights/druglikeness/` in five subdirectories:

```
weights/druglikeness/
├── generaldl/       # General drug-likeness model
├── specdl-ftt/      # Specialized model (FTT)
├── specdl-zinc/     # Specialized model (ZINC)
├── specdl-cm/       # Specialized model (CM)
└── specdl-cp/       # Specialized model (CP)
```

Each subdirectory should contain `config.json` and `pytorch_model.bin` (or `model.safetensors`).

> Contact the maintainers for weight files, or obtain them from the original repository.

### ChemBERTa pretrained weights

The drug-likeness stack expects ChemBERTa weights (tokenizer and molecular features). Update the path in `druglikeness/druglikeness/druglikeness/model.py`:

```python
pretrained_path = '/path/to/weights/chemberta'
```

Download ChemBERTa from Hugging Face:

```bash
# Option A: huggingface-cli
huggingface-cli download seyonec/ChemBERTa-zinc-base-v1 --local-dir weights/chemberta

# Option B: Python
from transformers import AutoTokenizer, AutoModel
tokenizer = AutoTokenizer.from_pretrained("seyonec/ChemBERTa-zinc-base-v1")
model = AutoModel.from_pretrained("seyonec/ChemBERTa-zinc-base-v1")
```

### ADMET models

ADMET prediction uses pretrained models under `admet_filter/admet_score_data/`; they ship with the repo and need no extra download.

---

## Running the web UI

```bash
# Option A: startup script
./start_web.sh

# Option B: direct
python app.py

# Option C: background
nohup python app.py > web_server.log 2>&1 &
```

Open `http://localhost:5000` in a browser (use the server IP on a remote machine).

---

## Command-line run (no web UI)

```bash
python vs_protocol.py config.yaml
```

---

## Configuration

Configs are YAML; see `config.yaml` for a full example. Main fields:

```yaml
working_directory: /path/to/output      # Output root
project_name: my_project                # Project name (subfolders)
start_module: library                   # Module to start from
receptor_pdb: /path/to/receptor.pdb     # Receptor PDB
ref_ligand_file: /path/to/ligand.mol2   # Reference ligand (docking box)
library_smiles: /path/to/library.smi    # Compound library SMILES

library:
  active: true          # Run library preprocessing
  threads: 60

receptor:
  active: true          # Run receptor preparation

physicochemical:
  active: false         # Physicochemical prescreening
  perform_phychem_predict: true
  perform_phychem_filter: true
  mw_lower: 200
  mw_upper: 600
  # ...

admet:
  active: false         # ADMET prescreening
  # ...

druglikeness:
  active: true          # Drug-likeness prescreening
  perform_dln_pred: true
  perform_dln_filter: true
  gpu_num: 4
  dln_count_lower: 3

prepare_ligand:
  active: true          # Ligand preparation
  dock_strategy: single # single or repeated
  perform_prepare: true
  prepare_threads: 90

docking:
  active: true          # Docking
  perform_dock: true
  dock_threads: 4
  search_mode: fast
  perform_extract: true
  perform_hbond: true
  method: pymol         # plip or pymol
  key_residues: 57,67,59,82,133,136
  perform_residue_filter: true
```

Valid `start_module` values: `library` / `receptor` / `physicochemical` / `admet` / `druglikeness` / `prepare_ligand` / `docking` / `result`

---

## FAQ

**Q: Port 5000 is already in use?**
```bash
lsof -i :5000    # find the process
kill -9 <PID>
```

**Q: Firewall blocks access?**
```bash
# CentOS/RHEL
sudo firewall-cmd --add-port=5000/tcp --permanent && sudo firewall-cmd --reload
# Ubuntu
sudo ufw allow 5000/tcp
```

**Q: Using PBS/Slurm?**

`utils/parse_pbsstat.py` parses PBS node status; `docking/distributed_unidock.py` supports multi-node docking with a `blocked_nodes` list to skip bad nodes.

**Q: ADMET prediction is slow?**

Increase `admet_predict_threads` and consider lowering `admet_predict_chunk` (molecules per batch).

---

## Dependency quick reference

| Package | Version | Install |
|---------|---------|---------|
| Python | ≥ 3.9 | conda |
| RDKit | ≥ 2022.09 | conda |
| PyTorch | ≥ 2.0 | pip (pin CUDA wheel for GPU) |
| transformers | ≥ 4.30 | pip |
| datasets | ≥ 2.14 | pip |
| Flask | ≥ 3.0 | pip |
| prody | ≥ 2.4 | pip |
| biopython | ≥ 1.81 | pip |
| scikit-learn | ≥ 1.3 | pip |
| PyBioMed | latest | pip (GitHub) |
| PLIP | latest | conda |
| PyMOL | latest | conda |
| UniDock | latest | GitHub release |
| ADFR Suite | latest | Official download |
