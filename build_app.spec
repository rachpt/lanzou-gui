# -*- mode: python ; coding: utf-8 -*-

# 本文件用于打包 MacOS 应用
# pyinstaller --clean --noconfirm build_app.spec

version = '0.4.0'
block_cipher = None


a = Analysis(['main.py'],
             pathex=['.'],
             binaries=[],
             datas=[],
             hiddenimports=[],
             hookspath=[],
             runtime_hooks=[],
             excludes=['./lanzou/gui/login_assister.py', ],
             win_no_prefer_redirects=False,
             win_private_assemblies=False,
             cipher=block_cipher,
             noarchive=False)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)
exe = EXE(pyz,
          a.scripts,
          a.binaries,
          a.zipfiles,
          a.datas,
          [],
          name='lanzou-gui',
          debug=False,
          bootloader_ignore_signals=False,
          strip=False,
          upx=True,
          upx_exclude=[],
          runtime_tmpdir=None,
          console=False ,
          icon='app_icon.icns')
app = BUNDLE(exe,
             name='lanzou-gui.app',
             icon='./app_icon.icns',
             info_plist={
                'CFBundleDevelopmentRegion': 'Chinese',
                'CFBundleIdentifier': "cn.rachpt.lanzou-gui",
                'CFBundleVersion': version,
                'CFBundleShortVersionString': version,
                'NSHumanReadableCopyright': u"Copyright © 2021, rachpt, All Rights Reserved"
             },
             bundle_identifier=None)
