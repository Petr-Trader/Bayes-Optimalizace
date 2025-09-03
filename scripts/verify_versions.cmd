@echo off
echo === Versions check ===
where python
if errorlevel 1 echo Python NOT found & goto :end
python --version
git --version
:end
