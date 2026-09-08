import os

conda_lib_bin = 'D:/Anaconda/envs/zako_env/Library/bin'

a = Analysis(
    ['zako_app_V3.0.py'],
    pathex=[],
    binaries=[
        (f'{conda_lib_bin}/tcl86t.dll', '.'),
        (f'{conda_lib_bin}/tk86t.dll', '.'),
        (f'{conda_lib_bin}/libcrypto-3-x64.dll', '.'),
        (f'{conda_lib_bin}/libssl-3-x64.dll', '.'),
    ],
    datas=[
        ('assets/nekonn.ico', 'assets'),
        ('assets/nekonn.png', 'assets'),
    ],
    hiddenimports=['ssl', '_ssl'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['matplotlib', 'numpy', 'pandas', 'PyQt5'],
    noarchive=False,
    optimize=0,
)

clean_binaries = []
for dest, src, typ in a.binaries:
    fname = os.path.basename(dest).lower()
    if fname in ('libcrypto-3-x64.dll', 'libssl-3-x64.dll'):
        continue
    clean_binaries.append((dest, src, typ))
clean_binaries.append(('libcrypto-3-x64.dll', f'{conda_lib_bin}/libcrypto-3-x64.dll', 'BINARY'))
clean_binaries.append(('libssl-3-x64.dll', f'{conda_lib_bin}/libssl-3-x64.dll', 'BINARY'))
a.binaries = clean_binaries

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='zako_rollcall_V3_preview',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='assets/nekonn.ico',
)
