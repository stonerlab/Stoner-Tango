echo "Starting SCPI class with ionstance %1" > C:\TEMP\k24xx.log
call C:\ProgramData\Anaconda3\Scripts\activate.bat >> C:\temp\k24xx.log 2>&1
echo Activated Conda >> C:\TEMP\k24xx.log
call conda activate tango >> C:\temp\k24xx.log 2>&1
where python >> C:\TEMP\k24xx.log
set PYTHONPATH=C:\Stoner-Tango
set >> C:\temp\k24xx.log
call python.exe ..\stoner_tango\instr\keithley\k24xx.py %1 >> C:\temp\k24xx.log 2>&1

