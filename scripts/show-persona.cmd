@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0.."
set PYTHONIOENCODING=utf-8

echo ==== active persona id ====
.\.venv\Scripts\python.exe -c "import io,json;c=json.load(io.open('data/cmd_config.json',encoding='utf-8-sig'));print(c.get('agent_runner',{}).get('config',{}).get('persona',{}).get('persona_id','(not set)'))"

echo.
echo ==== personas in database ====
.\.venv\Scripts\python.exe -c "import sqlite3;db=sqlite3.connect('data/data_v4.db');[print(' ',p,'(',n,'chars, updated',u,')') for p,n,u in db.execute('select persona_id,length(system_prompt),updated_at from personas order by sort_order')]"

echo.
echo ==== full system prompt of the active persona ====
.\.venv\Scripts\python.exe -c "import io,json,sqlite3;c=json.load(io.open('data/cmd_config.json',encoding='utf-8-sig'));pid=c.get('agent_runner',{}).get('config',{}).get('persona',{}).get('persona_id','default');row=sqlite3.connect('data/data_v4.db').execute('select system_prompt from personas where persona_id=?',(pid,)).fetchone();print(row[0] if row else '(persona not found)')"

echo.
endlocal
