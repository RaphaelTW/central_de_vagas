@echo off
setlocal
if not exist ".venv\Scripts\python.exe" (
  py -3.14 -m venv .venv
)
call .venv\Scripts\activate.bat
pip install -r requirements.txt
streamlit run app.py
