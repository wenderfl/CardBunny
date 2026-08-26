@echo off
echo Criando ambiente virtual...
python -m venv venv
echo Ativando ambiente virtual e instalando dependencias...
call venv\Scripts\activate.bat
pip install -r requirements.txt
echo Setup concluido!
pause
