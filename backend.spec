import os
import akshare
import py_mini_racer

block_cipher = None

# 获取 akshare 数据文件路径
akshare_path = os.path.dirname(akshare.__file__)
akshare_data = os.path.join(akshare_path, 'file_fold')

# 获取 py_mini_racer native library 路径
mini_racer_path = os.path.dirname(py_mini_racer.__file__)
mini_racer_lib = os.path.join(mini_racer_path, 'libmini_racer.dylib')  # macOS
if not os.path.exists(mini_racer_lib):
    mini_racer_lib = os.path.join(mini_racer_path, 'libmini_racer.so')  # Linux
if not os.path.exists(mini_racer_lib):
    mini_racer_lib = os.path.join(mini_racer_path, 'mini_racer.dll')  # Windows

# 获取 py_mini_racer 数据文件（icudtl.dat）
mini_racer_data = os.path.join(mini_racer_path, 'icudtl.dat')

binaries_list = []
datas_list = []
if os.path.exists(mini_racer_lib):
    binaries_list.append((mini_racer_lib, 'py_mini_racer'))
if os.path.exists(mini_racer_data):
    datas_list.append((mini_racer_data, 'py_mini_racer'))

a = Analysis(
    ['backend/run.py'],
    pathex=['backend'],
    binaries=binaries_list,
    datas=[
        ('backend/app', 'app'),
        (akshare_data, 'akshare/file_fold'),
        ('frontend/dist', 'fundval-live'),
    ] + datas_list,
    hiddenimports=[
        'uvicorn.logging',
        'uvicorn.loops',
        'uvicorn.loops.auto',
        'uvicorn.protocols',
        'uvicorn.protocols.http',
        'uvicorn.protocols.http.auto',
        'uvicorn.protocols.websockets',
        'uvicorn.protocols.websockets.auto',
        'uvicorn.lifespan',
        'uvicorn.lifespan.on',
        'akshare',
        'numpy',
        'pandas',
        'requests',
        'fastapi',
        'pydantic',
        'sqlite3',
        'email.mime.text',
        'email.mime.multipart',
        'smtplib',
        'cryptography',
        'cryptography.fernet',
        'cryptography.hazmat',
        'cryptography.hazmat.primitives',
        'cryptography.hazmat.backends',
        'langchain_openai',
        'langchain_core',
        'langchain_core.output_parsers',
        'langchain_core.prompts',
        'duckduckgo_search',
        'py_mini_racer',
        'mini_racer',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='fundval-backend',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='fundval-backend',
)
