@echo off
rem SSH_ASKPASS helper: prints the root password from the environment.
rem The password is never written to this file or to the repo.
echo %ASTROOT_PASS%
