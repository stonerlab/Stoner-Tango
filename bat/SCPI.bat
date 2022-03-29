echo "Starting SCPI class with ionstance %1" > C:\TEMP\py.log
call C:\ProgramData\Anaconda3\Scripts\activate.bat >> C:\temp\py.log 2>&1
echo Activated Conda >> C:\TEMP\py.log
call conda activate tango >> C:\temp\py.log 2>&1
where python >> C:\TEMP\py.log
set PYTHONPATH=C:\Stoner-Tango
set >> C:\temp\py.log
call python.exe C:\Stoner-Tango\stoner_tango\instr\base\SCPI.py %1 >> C:\temp\py.log 2>&1
x
