
# How to Run (Windows)

This document explains how to set up a clean, reproducible Python environment and run the pipeline reliably.

It is written to avoid common Windows issues such as installing packages into one Python interpreter while running the project with another.

---

## 1. Python Version

**Recommended:** Python **3.14**

**Minimum:** Python **3.10+**

On Windows, it is strongly recommended to use the **Python Launcher** (`py`) so you can select the exact Python version explicitly.

Check which Python versions are installed:

```bat  
py -0p  
```

## Install Python 3.14 (Optional, Recommended)

If Python 3.14 is not installed, you can install it via winget:

winget install -e --id Python.Python.3.14

Verify that Python 3.14 is available:

py -3.14 -c "import sys; print(sys.executable); print(sys.version)"

## 2. Create Virtual Environment

From the repository root, create a virtual environment using Python 3.14:
```
py -3.14 -m venv .venv
```
Activate the Environment (Optional)

You may activate it:
```
.\.venv\Scripts\activate
```
Activation is optional. You can also run everything by calling the venv interpreter directly (recommended for consistency).

## 3. Install Dependencies

Install dependencies using the venv interpreter to ensure packages are installed into the correct environment:

```
.\.venv\Scripts\python.exe -m pip install --upgrade pip

.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```
Optional verification (example: reportlab):
```
.\.venv\Scripts\python.exe -c "import reportlab; print('reportlab OK', reportlab.Version)"
```
## 4. Run The Pipeline

Display available CLI options:
```
.\.venv\Scripts\python.exe src\main.py --help
```
Example run (with an explicit input file):
```
.\.venv\Scripts\python.exe src\main.py --sample-size 1000000 --input-file data\eve_sample_1000000.jsonl
```
Recommendation: store datasets under data/ and keep it excluded from git (via .gitignore).

## 5. Output Location

By default, outputs are written under:

```
results/data_{sample_size}/{run_id}/
```
## 6. Troubleshooting

####  6.1 “Missing dependency” even though pip says “Requirement already satisfied”

This almost always indicates you installed packages into one interpreter but ran the project with another.

Correct approach: always install and run using:
```
.\.venv\Scripts\python.exe
```
Compare which pip you are using:
```
python -m pip -V
.\.venv\Scripts\python.exe -m pip -V
```
If the paths differ, the environments differ.

#### 6.2 py -3.14 is not recognized

This means Python 3.14 is not installed or not registered with the launcher.

Install it:
```
winget install -e --id Python.Python.3.14
```
Close and reopen your terminal, then verify:
```
py -0p
```
#### 6.3 Using Python 3.10 instead of 3.14 (Fallback)

If you prefer or only have Python 3.10 installed, create the venv with 3.10:
```
py -3.10 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```
Then run as usual:
```
.\.venv\Scripts\python.exe src\main.py --help
```
