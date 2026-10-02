import os
import sys

if getattr(sys, 'frozen', False):
    _base = os.path.dirname(sys.executable)
    _internal = os.path.join(_base, "_internal")
    if os.path.isdir(_internal):
        _base = _internal

    # 1) Añadir la carpeta raíz del bundle al PATH de DLLs
    os.add_dll_directory(_base)

    # 2) Localizar python313.dll (la DLL de Python que necesita pythonnet)
    #    Normalmente está en la raíz del bundle o en _internal
    _python_dll = os.path.join(_base, "python313.dll")
    if not os.path.exists(_python_dll):
        # Buscar en subcarpetas por si acaso
        for root, dirs, files in os.walk(_base):
            if "python313.dll" in files:
                _python_dll = os.path.join(root, "python313.dll")
                break

    if os.path.exists(_python_dll):
        os.environ["PYTHONNET_PYDLL"] = _python_dll

    # 3) Localizar Python.Runtime.dll y añadir su carpeta al PATH
    _runtime_dir = os.path.join(_base, "pythonnet", "runtime")
    if os.path.isdir(_runtime_dir):
        os.add_dll_directory(_runtime_dir)
        os.environ["PYTHONNET_RUNTIME"] = "netfx"