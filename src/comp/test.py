"""This file is used to test the compiler by compiling a test .ltcir file and then running the generated C code. It also compiles and runs a test C file to ensure that the generated C code is correct."""
import os
last_exit_code = 0

if last_exit_code == 0:
    last_exit_code = os.system("rustc src\\comp\\ltcir\\main.rs -o src\\comp\\ltcirc.exe")
    print(f"--- AUTO COMPILER --- main.rs -> ltcirc.exe:     {last_exit_code}")

if last_exit_code == 0:
    last_exit_code = os.system('src\\comp\\ltcirc.exe examples\\comp\\test.ltcir')
    print(f"--- AUTO COMPILER --- .ltcir -> .cpp:     {last_exit_code}")

if last_exit_code == 0:
    last_exit_code = os.system("g++ examples\\comp\\test.cpp -o examples\\comp\\test.exe")
    print(f"--- AUTO COMPILER --- .cpp -> .exe:     {last_exit_code}")

if last_exit_code == 0:
    print("--- AUTO COMPILER --- Running the generated .exe file:")
    last_exit_code = os.system("examples\\comp\\test.exe")
    print(f"--- AUTO COMPILER --- .exe exit code:     {last_exit_code}")