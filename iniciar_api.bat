@echo off
cd C:\xampp\api_fortea
call venv\Scripts\activate
uvicorn main:app --port 8000
pause