@echo off
chcp 65001 > nul
set PYTHONIOENCODING=utf-8
title Javshani Full System
cd /d "C:\Users\For Home\Desktop\Javshani-main"

echo [1/2] Starting User Synchronization...
start powershell -NoProfile -ExecutionPolicy Bypass -File ".\sync.ps1"

echo [2/2] Starting Checker...
python checker.py
pause