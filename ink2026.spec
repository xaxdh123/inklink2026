# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all
from PyInstaller.building.build_main import Analysis, PYZ, EXE, COLLECT

# -----------------------
# 1️⃣ 收集资源和 PySide6
# -----------------------
datas = [('resources', 'resources')]
binaries = []
hiddenimports = []

tmp_ret = collect_all('PySide6')
datas += tmp_ret[0]
binaries += tmp_ret[1]
hiddenimports += tmp_ret[2]

# -----------------------
# 2️⃣ 分析代码
# -----------------------
a = Analysis(
    ['sub_module.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

# -----------------------
# 3️⃣ 创建每个 exe
# -----------------------
exe_customer = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='customer_service/customer_service',
    debug=False,
    strip=False,
    upx=False,
    console=True,
    icon=['resources/icon.ico'],
    args=['CustomerService'],
)

exe_float = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='floating_plugin/floating_plugin',
    debug=False,
    strip=False,
    upx=False,
    console=False,
    icon=['resources/icon.ico'],
    args=['FloatingPlugin'],
)

exe_setting = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='system_setting/system_setting',
    debug=False,
    strip=False,
    upx=False,
    console=False,
    icon=['resources/icon.ico'],
    args=['SystemSetting'],
)

exe_third = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='third_party/third_party',
    debug=False,
    strip=False,
    upx=False,
    console=False,
    icon=['resources/icon.ico'],
    args=['ThirdParty'],
)

exe_design = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='design_center/design_center',
    debug=False,
    strip=False,
    upx=False,
    console=False,
    icon=['resources/icon.ico'],
    args=['DesignCenter'],
)

exe_audit = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='audit_center/audit_center',
    debug=False,
    strip=False,
    upx=False,
    console=False,
    icon=['resources/icon.ico'],
    args=['AuditCenter'],
)

exe_layout = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='layout_center/layout_center',
    debug=False,
    strip=False,
    upx=False,
    console=False,
    icon=['resources/icon.ico'],
    args=['LayoutCenter'],
)
# -----------------------
# 4️⃣ 每个 exe 一个 COLLECT（独立环境）
# -----------------------
coll_customer = COLLECT(
    exe_customer,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='customer_service',
)

coll_float = COLLECT(
    exe_float,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='floating_plugin',
)

coll_setting = COLLECT(
    exe_setting,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='system_setting',
)

coll_third = COLLECT(
    exe_third,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='third_party',
)

coll_design = COLLECT(
    exe_design,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='design_center',
)

coll_audit = COLLECT(
    exe_audit,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='audit_center',
)
coll_layout= COLLECT(
    exe_layout,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='layout_center',
)
