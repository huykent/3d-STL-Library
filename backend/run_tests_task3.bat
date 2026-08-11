@echo off
cd /d f:\code\3d-STL-Library\backend
f:\code\3d-STL-Library\backend\.venv\Scripts\python.exe -m pytest tests/test_api_models.py tests/test_api_tags.py -v
