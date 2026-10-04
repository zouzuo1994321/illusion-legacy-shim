# -*- coding: utf-8 -*-
"""
Illusion 老游戏兼容性修复工具 (PySide6)
=======================================
解决 2006 年 Illusion 引擎老游戏（Direct3D 9）在现代 Windows 11 上的
启动闪退 + 操作即"未响应"问题。

支持的游戏：
  - RapeLay_cn.exe    （主程序）
  - BotuPlay.exe      （特典包，位于 [特典包BotuPlay] 子目录）
两者均静态导入 Direct3DCreate9 + d3dx9_24，问题根因完全相同。

完整修复 = 两层叠加：
  ① 渲染层：DXVK 2.4.1（D3D9→Vulkan 翻译）+ 窗口化，解决启动闪退
  ② 兼容层：游戏 exe 设「Windows XP (Service Pack 3) 兼容模式 + 管理员运行」
             解决老引擎在 Win11 下的多核拓扑 / GetVersion / DPI / DirectInput
             错乱导致的"一操作就未响应"

三种运行方案：
  方案A - DXVK 2.4.1       (推荐，实测可正常打开)
  方案B - dgVoodoo2 2.87.5 (备选)
  方案0 - 原生无补丁        (还原初始状态)

主要功能：
  - 自动搜索游戏目录（注册表 INSTALLDIR + 常见盘符扫描）
  - 手动选择游戏目录
  - 每个游戏独立部署/还原方案
  - 一键设置兼容性标志（WINXPSP3 + RUNASADMIN）
  - 一键启动游戏（自动 UAC 提权）
  - 每次切换前自动备份
  - 方案文件内置，首次运行自动释放（无需外部 _方案切换 目录）
"""

import os
import sys
import shutil
import subprocess
import datetime
import zipfile
import ctypes
import time

from PySide6.QtCore import (
    Qt, QTimer, QPropertyAnimation, QEasingCurve, QUrl, QFile, QRandomGenerator,
    QRect,
)
from PySide6.QtGui import QFont, QIcon, QPixmap, QPalette, QColor, QPainter
from PySide6.QtMultimedia import QSoundEffect
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QGroupBox, QMessageBox, QSizePolicy, QFileDialog, QTabWidget,
    QDialog, QPlainTextEdit, QFrame, QSplashScreen,
)

APP_TITLE = "Illusion 老游戏兼容性修复工具"
APP_VER = "v3.10"
APP_COPYRIGHT = "Copyright © 2026 肆月Aperture"
# 主窗口默认尺寸：启动画面与主窗口共用，保证启动画面「只覆盖软件界面」且两者对齐
APP_WIN_W, APP_WIN_H = 700, 620
APP_LICENSE = "本软件为开源软件，未经授权禁止用于商业用途。"

# 作者联系方式（(键, 显示名, 账号/地址, 跳转URL, logo文件名)）
CONTACTS = [
    ("github", "GitHub", "github.com/zouzuo1994321",
     "https://github.com/zouzuo1994321", "github.png"),
    ("bilibili", "哔哩哔哩", "space.bilibili.com/13715",
     "https://space.bilibili.com/13715", "bilibili.png"),
    ("weibo", "微博", "weibo.com/u/5189652182",
     "https://weibo.com/u/5189652182", "weibo.png"),
    ("mail", "邮箱", "921103025@qq.com",
     "mailto:921103025@qq.com", "mail.png"),
]

# ----------------------------------------------------------------------------
# 常量
# ----------------------------------------------------------------------------
GAMES = [
    {
        "key": "rapelay",
        "name": "RapeLay_cn.exe",
        "display": "电车之狼R（本体）",
        "rel": "RapeLay_cn.exe",          # 相对游戏根目录
        "reg_key": r"SOFTWARE\Illusion\Rapelay",
        "keywords": ["电车之狼", "RapeLay", "rapelay"],
    },
    {
        "key": "botuplay",
        "name": "BotuPlay.exe",
        "display": "电车之狼R（特典包）",
        "rel": r"[特典包BotuPlay]\BotuPlay.exe",
        "reg_key": r"SOFTWARE\Illusion\BotuPlay",
        "keywords": ["特典包", "BotuPlay"],
    },
    {
        "key": "vr",
        "name": "IPVR.exe",
        "display": "电车之狼VR（本体）",
        "rel": r"IPVR.exe",
        "reg_key": r"SOFTWARE\Illusion\IPVR",
        "keywords": ["电车之狼VR", "IPVR", "VR"],
        # IPVR.exe 只导入 ddraw.dll（DirectDraw，2001 年老引擎），
        # 不含任何 d3d9.dll 调用 —— DXVK 对它完全无效，
        # 必须用 dgVoodoo 的 ddraw.dll 做 DirectDraw → D3D11 翻译。
        "overrides": {"B": "方案B_dgVoodoo_VR"},
        # 该游戏只有 dgVoodoo（方案B）可用，方案A 不适用
        "plans": ["B", "0"],
        "plan_hint": "本作是 2001 年 DirectDraw 老引擎，仅方案B（dgVoodoo）可用。",
    },
    {
        "key": "os2",
        "name": "OS2cn.exe",
        "display": "波动少女2（本体）",
        "rel": r"OS2cn.exe",
        "reg_key": r"SOFTWARE\Illusion\OS2",
        "keywords": ["OS2", "波动少女"],
        # 备用候选（若 OS2cn.exe 不存在则尝试这些）
        "alts": ["OS2cn.exe", "OS2.exe"],
        # 该目录原本已带一套旧版 dgVoodoo（大写命名），实测可玩，
        # 因此方案B 使用专为该游戏保留的版本目录
        "overrides": {"B": "方案B_dgVoodoo_OS2"},
    },
    {
        "key": "custom",
        "name": None,
        "display": "自定义程序",
        "rel": None,
        "reg_key": None,
        "keywords": [],
        "custom": True,
    },
]

# 每种方案要部署的文件（目标名 -> 方案目录内源文件名）
PLANS = {
    "A": {
        "name": "方案A - DXVK 2.4.1",
        "short": "A · DXVK",
        "desc": "D3D9 → Vulkan 翻译层 + 窗口化。实测可正常打开，推荐。",
        "dir": "方案A_DXVK",
        "files": {
            "d3d9.dll": "d3d9.dll",
            "d3d8.dll": "d3d8.dll",
            "d3d11.dll": "d3d11.dll",
            "d3d10core.dll": "d3d10core.dll",
            "dxgi.dll": "dxgi.dll",
            "dxvk.conf": "dxvk.conf",
        },
        "remove": ["ddraw.dll", "d3dimm.dll", "dgVoodooCpl.exe"],
        "disable_conf": ["dgVoodoo.conf"],
    },
    "B": {
        "name": "方案B - dgVoodoo2 2.87.5",
        "short": "B · dgVoodoo",
        "desc": "D3D9 → D3D11 翻译层（官方原版）。老游戏兼容性经典工具。",
        "dir": "方案B_dgVoodoo",
        "files": {
            "d3d9.dll": "d3d9.dll",
            "d3d8.dll": "d3d8.dll",
            "ddraw.dll": "ddraw.dll",
            "d3dimm.dll": "d3dimm.dll",
            "dgVoodooCpl.exe": "dgVoodooCpl.exe",
            "dgVoodoo.conf": "dgVoodoo.conf",
        },
        "remove": ["dxgi.dll", "d3d11.dll", "d3d10core.dll"],
        "disable_conf": ["dxvk.conf"],
    },
    "0": {
        "name": "方案0 - 原生无补丁",
        "short": "0 · 原生",
        "desc": "移除全部代理 DLL，游戏恢复原始状态。",
        "dir": "方案0_原生无补丁",
        "files": {},
        "remove": ["d3d9.dll", "d3d8.dll", "d3d11.dll", "d3d10core.dll",
                   "dxgi.dll", "ddraw.dll", "d3dimm.dll", "dgVoodooCpl.exe",
                   "d3d9_dxvk.dll"],
        "disable_conf": ["dxvk.conf", "dgVoodoo.conf"],
    },
}

ALL_PROXY = ["d3d9.dll", "d3d8.dll", "d3d11.dll", "d3d10core.dll",
             "dxgi.dll", "ddraw.dll", "d3dimm.dll"]
ALL_CONF = ["dxvk.conf", "dgVoodoo.conf"]
PLAN_FILES = ALL_PROXY + ALL_CONF + ["dgVoodooCpl.exe", "d3d9_dxvk.dll"]


def find_existing(game_dir, name):
    """
    不区分大小写地查找 game_dir 中名为 name 的文件，返回其真实路径。
    Windows 上同名不同大小写会互相覆盖，必须先找到已存在的真实文件名。
    """
    low = name.lower()
    try:
        for f in os.listdir(game_dir):
            if f.lower() == low:
                p = os.path.join(game_dir, f)
                if os.path.isfile(p):
                    return p
    except OSError:
        pass
    return None


def real_case_name(game_dir, name):
    """返回 game_dir 中该名字实际使用的大小写；不存在则返回原 name。"""
    p = find_existing(game_dir, name)
    return os.path.basename(p) if p else name


def remove_case_insensitive(game_dir, name, log=None):
    """不区分大小写地删除文件。返回是否删除了某个文件。"""
    p = find_existing(game_dir, name)
    if not p:
        return False
    try:
        os.remove(p)
        if log:
            log("  已移除 %s", os.path.basename(p))
        return True
    except Exception as e:
        if log:
            log("  [警告] 无法移除 %s：%s", os.path.basename(p), e)
        return False


def scan_files(game_dir):
    """扫描已部署的代理 DLL / 配置（不区分大小写）。"""
    out = []
    for n in PLAN_FILES:
        p = find_existing(game_dir, n)
        if p:
            try:
                out.append((os.path.basename(p), os.path.getsize(p)))
            except OSError:
                out.append((os.path.basename(p), -1))
    return out

# 兼容性标志：老引擎必须的完整修复组合
COMPAT_FLAG = "~ WINXPSP3 RUNASADMIN"

# 内置方案包（打包时 --add-data "_plans.zip;."）
PLANS_ZIP_NAME = "_plans.zip"

# 内置 DirectX 运行库（打包时 --add-data "_dx;."）
DX_PACKAGES = {
    "dx9": {
        "file": r"_dx\DirectX9\DXSETUP.exe",
        "label": "DirectX 9.0c 运行库（精简版）",
        "desc": "安装 d3dx9_24~43 / D3DCompiler 等 Direct3D 9 组件，"
                "解决老游戏提示缺少 d3dx9_*.dll。",
        "args": "",
    },
    "dx6": {
        "dir": r"_dx\DirectX6",
        "copy_dlls": True,
        "label": "DirectX 6/7 老组件",
        "desc": "把 DX6/7 时代的旧组件（d3drm.dll 等，Win11 已移除）"
                "复制到游戏目录，解决老游戏缺少 d3drm 等组件的报错。",
    },
}


# ----------------------------------------------------------------------------
# 内置方案包释放
# ----------------------------------------------------------------------------
def res_path(name):
    """定位打包内资源。同名文件也会在 _social/ 子目录里找一次。"""
    if getattr(sys, "frozen", False):
        base = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    for cand in (os.path.join(base, name),
                 os.path.join(base, "_social", name)):
        if os.path.exists(cand):
            return cand
    return None


def app_dir():
    """程序所在目录（exe 的目录，不是 _MEIPASS）。"""
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


def open_url(url):
    """用系统默认浏览器打开链接（QQ 邮箱等 mailto: 也走这里）。"""
    try:
        if url.lower().startswith("mailto:"):
            os.startfile(url)
        else:
            os.startfile(url)
        return True
    except Exception:
        try:
            import webbrowser
            webbrowser.open(url)
            return True
        except Exception:
            return False


def plans_root(root_dir):
    """统一的方案根目录：<游戏根>/_方案切换。"""
    return os.path.join(root_dir, "_方案切换")


def ensure_plans_extracted(root_dir, log=None, force=False):
    """
    确保 _方案切换 目录存在且完整。
    若不存在（或强制），从内置 _plans.zip 解压。
    返回 (ok, msg)
    """
    dst = plans_root(root_dir)
    marker = os.path.join(dst, ".extracted_ok")

    # 判断是否需要释放：目录不存在 / 缺少关键 DLL / 强制
    need = force
    if not need:
        key_dll = os.path.join(dst, "方案A_DXVK", "d3d9.dll")
        if not os.path.exists(key_dll):
            need = True

    if not need:
        return True, "方案文件已就绪"

    zp = res_path(PLANS_ZIP_NAME)
    if not zp:
        return False, "内置方案包缺失（%s）" % PLANS_ZIP_NAME

    try:
        if log:
            log("正在释放内置方案文件 → %s", dst)
        os.makedirs(dst, exist_ok=True)
        n = 0
        base_ok = os.path.normpath(dst)
        with zipfile.ZipFile(zp, "r") as z:
            for m in z.namelist():
                if m.endswith("/"):
                    continue
                # 安全：防止路径穿越（只检查 zip 内相对路径）
                rel = os.path.normpath(m.replace("/", os.sep))
                if rel.startswith("..") or os.path.isabs(rel):
                    continue
                target = os.path.join(base_ok, rel)
                os.makedirs(os.path.dirname(target), exist_ok=True)
                with z.open(m) as src, open(target, "wb") as out:
                    shutil.copyfileobj(src, out)
                n += 1
        try:
            with open(marker, "w", encoding="utf-8") as f:
                f.write("ok %s\n" % datetime.datetime.now().isoformat())
        except OSError:
            pass
        if log:
            log("已释放 %d 个文件", n)
        return True, "已释放 %d 个方案文件" % n
    except Exception as e:
        return False, "释放失败：%s" % e


# ----------------------------------------------------------------------------
# 目录搜索
# ----------------------------------------------------------------------------
def _read_reg_installdir(reg_key):
    """读 HKLM\\SOFTWARE\\<reg_key> 的 INSTALLDIR。用 winreg（不依赖 reg.exe）。"""
    try:
        import winreg
        for hive in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
            for view in (winreg.KEY_WOW64_32KEY, winreg.KEY_WOW64_64KEY, 0):
                try:
                    with winreg.OpenKey(hive, reg_key, 0,
                                        winreg.KEY_READ | view) as k:
                        v, _ = winreg.QueryValueEx(k, "INSTALLDIR")
                        v = str(v).strip().strip('"')
                        if v and os.path.isdir(v):
                            return os.path.abspath(v)
                except OSError:
                    continue
    except Exception:
        pass
    return None


def _candidate_roots():
    roots = []
    try:
        import string
        for ch in string.ascii_uppercase:
            d = ch + ":\\"
            if os.path.exists(d):
                roots.append(d)
    except Exception:
        pass
    return roots


_KEYWORDS = ["RapeLay", "rapelay", "电车之狼", "Illusion", "特典包", "BotuPlay",
             "OS2", "波动少女", "SexyBeach"]


def search_games(progress=None, max_depth=3):
    found = {}

    def push(gkey, exe_path):
        if gkey in found:
            return
        found[gkey] = (os.path.dirname(exe_path), exe_path)

    for g in GAMES:
        if g.get("custom") or not g.get("rel"):
            continue
        if progress:
            progress("读取注册表 %s ..." % g["display"])
        d = _read_reg_installdir(g["reg_key"]) if g.get("reg_key") else None
        if d:
            exe = os.path.join(d, os.path.basename(g["rel"].replace("\\", "/")))
            cand = os.path.join(d, g["rel"].split("\\")[-1])
            trials = [cand, exe, os.path.join(d, g["name"])]
            trials += [os.path.join(d, a) for a in g.get("alts", [])]
            for trial in trials:
                if os.path.exists(trial):
                    push(g["key"], os.path.abspath(trial))
                    break

    for root in _candidate_roots():
        if progress:
            progress("扫描 %s ..." % root)
        try:
            _scan_dir(root, found, push, 0, max_depth, progress)
        except Exception:
            continue

    return found


def _scan_dir(path, found, push, depth, max_depth, progress):
    if depth > max_depth:
        return
    try:
        entries = list(os.scandir(path))
    except (OSError, PermissionError):
        return
    for e in entries:
        try:
            if e.is_file():
                low = e.name.lower()
                for g in GAMES:
                    if g.get("custom") or not g.get("name"):
                        continue
                    names = [g["name"]] + list(g.get("alts", []))
                    if any(low == n.lower() for n in names):
                        push(g["key"], e.path)
            elif e.is_dir():
                nm = e.name
                hit = any(k.lower() in nm.lower() for k in _KEYWORDS)
                if hit and depth < max_depth:
                    _scan_dir(e.path, found, push, depth + 1, max_depth, progress)
                elif depth < 1:
                    if nm.lower() in ("games", "game", "illusion", "电车之狼r",
                                      "program files", "program files (x86)"):
                        _scan_dir(e.path, found, push, depth + 1, max_depth, progress)
        except (OSError, PermissionError):
            continue


def find_local_game_root():
    """优先：exe 同目录。"""
    base = app_dir()
    for g in GAMES:
        if g.get("custom") or not g.get("rel"):
            continue
        if os.path.exists(os.path.join(base, g["rel"])):
            return base
    cur = base
    for _ in range(3):
        cur = os.path.dirname(cur)
        for g in GAMES:
            if g.get("custom") or not g.get("rel"):
                continue
            if os.path.exists(os.path.join(cur, g["rel"])):
                return cur
    return base


# ----------------------------------------------------------------------------
# 兼容性标志
# ----------------------------------------------------------------------------
COMPAT_LAYERS = (r"SOFTWARE\Microsoft\Windows NT\CurrentVersion"
                 r"\AppCompatFlags\Layers")


def read_compat(exe_path):
    """读当前 exe 的兼容性标志（HKCU 层）。返回字符串或 None。"""
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, COMPAT_LAYERS, 0,
                            winreg.KEY_READ) as k:
            try:
                v, _ = winreg.QueryValueEx(k, exe_path)
                return str(v)
            except FileNotFoundError:
                return None
    except OSError:
        return None
    except Exception:
        return None


def write_compat(exe_path, flag=COMPAT_FLAG, log=None):
    """
    写兼容性标志。同时尝试 HKCU（总能成功）与 HKLM（需管理员）。
    返回 (ok, msg)
    """
    import winreg
    wrote = []
    errors = []
    for label, hive, extra in (
        ("HKCU", winreg.HKEY_CURRENT_USER, 0),
        ("HKLM", winreg.HKEY_LOCAL_MACHINE, winreg.KEY_WOW64_64KEY),
    ):
        try:
            k = winreg.CreateKeyEx(hive, COMPAT_LAYERS, 0,
                                   winreg.KEY_SET_VALUE | extra)
            try:
                winreg.SetValueEx(k, exe_path, 0, winreg.REG_SZ, flag)
                wrote.append(label)
            finally:
                winreg.CloseKey(k)
        except PermissionError:
            errors.append("%s(需管理员)" % label)
        except Exception as e:
            errors.append("%s(%s)" % (label, e))
    if wrote:
        if log:
            log("  兼容性标志已写入 [%s]：%s", "+".join(wrote), flag)
        tail = ("；%s 未写入 %s" % ("、".join(errors), flag)) if errors else ""
        return True, "已设置「Windows XP (SP3) 兼容模式 + 管理员运行」%s" % tail
    return False, "写入失败：%s" % ("、".join(errors) or "未知")


def fix_all_compat(root_dir, log=None):
    """给所有已知游戏的 exe 批量设置兼容性标志。返回 (ok_count, total, detail)"""
    targets = []
    for g in GAMES:
        if g.get("custom") or not g.get("rel"):
            continue
        p = os.path.join(root_dir, g["rel"])
        if os.path.exists(p):
            targets.append((g["display"], p))
    if not targets:
        return 0, 0, "未找到任何游戏 exe，请先定位。"
    ok = 0
    lines = []
    for disp, p in targets:
        o, m = write_compat(p, log=log)
        if o:
            ok += 1
        lines.append("  %s %s：%s" % ("✔" if o else "✘", disp, m))
    return ok, len(targets), "\n".join(lines)


# ----------------------------------------------------------------------------
# 部署逻辑
# ----------------------------------------------------------------------------
def detect_plan(game_dir):
    def ex(n):
        return find_existing(game_dir, n) is not None
    if ex("dxgi.dll") or ex("dxvk.conf"):
        return "A"
    if ex("ddraw.dll") or ex("d3dimm.dll") or ex("dgVoodoo.conf"):
        return "B"
    return "0"


# ---------------------------------------------------------------------------
# 方案部署
# ---------------------------------------------------------------------------
def backup_dir(game_dir, tag=""):
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    bdir = os.path.join(game_dir, "_switcher_backup",
                        ts + ("_" + tag if tag else ""))
    os.makedirs(bdir, exist_ok=True)
    n = 0
    for name in PLAN_FILES:
        p = find_existing(game_dir, name)   # 大小写不敏感
        if p:
            try:
                shutil.copy2(p, os.path.join(bdir, os.path.basename(p)))
                n += 1
            except Exception:
                pass
    return bdir, n


def deploy(game_dir, plan_key, src_root, log, overrides=None):
    """
    在 game_dir 部署 plan_key 方案。
    src_root 为 '方案切换' 总目录。
    overrides: {方案名: 覆盖用的子目录名}，用于某游戏专用版本
               （如 OS2 用旧版 dgVoodoo：{"B": "方案B_dgVoodoo_OS2"}）
    """
    plan = PLANS.get(plan_key)
    if not plan:
        return False, "未知方案：%s" % plan_key
    log("=" * 54)
    log("部署【%s】", plan["name"])

    # 先备份现有代理文件
    try:
        bdir, n = backup_dir(game_dir, plan_key)
        if n:
            log("  已备份 %d 个文件 → _switcher_backup\\%s"
                % (n, os.path.basename(bdir)))
    except Exception as e:
        log("  [警告] 备份失败：%s" % e)

    # 决定源目录（支持 overrides 指定专用目录）
    subdir = (overrides or {}).get(plan_key) or plan["dir"]
    src_dir = os.path.join(src_root, subdir)
    if not os.path.isdir(src_dir):
        # 回退到默认目录
        src_dir = os.path.join(src_root, plan["dir"])
        if not os.path.isdir(src_dir):
            return False, "找不到方案目录：%s" % src_dir
    if subdir != plan["dir"]:
        log("  （使用该程序专用方案目录：%s）" % subdir)

    # 1) 移除方案不需要的代理 DLL
    for name in plan.get("remove", []):
        remove_case_insensitive(game_dir, name)

    # 2) 停用不该生效的配置文件（改名成 .off）
    for name in plan.get("disable_conf", []):
        p = find_existing(game_dir, name)
        if p and not p.lower().endswith(".off"):
            try:
                os.remove(p + ".off") if os.path.exists(p + ".off") else None
                os.rename(p, p + ".off")
                log("  已停用 %s" % name)
            except Exception as e:
                log("  [警告] 无法停用 %s：%s" % (name, e))

    # 3) 拷贝方案文件
    copied = 0
    for dst, src in plan.get("files", {}).items():
        sp = os.path.join(src_dir, src)
        if not os.path.exists(sp):
            continue
        try:
            shutil.copy2(sp, os.path.join(game_dir, dst))
            copied += 1
        except Exception as e:
            log("  [警告] 拷贝 %s 失败：%s" % (dst, e))

    # 4) 恢复被 .off 的配置文件（如果方案自带同名 conf）
    for name in PLAN_FILES:
        if not name.endswith(".conf"):
            continue
        target = os.path.join(game_dir, name)
        off = target + ".off"
        if os.path.exists(target) and os.path.exists(off):
            try:
                os.remove(off)
                log("  已恢复 %s" % name)
            except Exception as e:
                log("  [警告] 恢复 %s 失败：%s" % (name, e))

    if copied == 0 and plan_key != "0":
        return False, "方案目录里没有可用文件：%s" % src_dir
    return True, "已部署【%s】，共写入 %d 个文件。" % (plan["name"], copied)


# ---------------------------------------------------------------------------
# 启动游戏（需要 UAC 提权，并抓取 PID 供日志使用）
# ---------------------------------------------------------------------------
def _cfg_path():
    base = os.environ.get("APPDATA") or app_dir()
    d = os.path.join(base, "IllusionFixTool")
    try:
        os.makedirs(d, exist_ok=True)
    except OSError:
        d = app_dir()
    return os.path.join(d, "custom.json")


def load_custom():
    """读取记忆的自定义程序路径。返回 exe 路径或 None。"""
    try:
        import json
        with open(_cfg_path(), "r", encoding="utf-8") as f:
            return json.load(f).get("exe") or None
    except Exception:
        return None


def save_custom(exe_path):
    try:
        import json
        with open(_cfg_path(), "w", encoding="utf-8") as f:
            json.dump({"exe": exe_path}, f, ensure_ascii=False, indent=2)
        return True
    except Exception:
        return False


# ---------------------------------------------------------------------------
# 启动游戏（需要 UAC 提权）
# ---------------------------------------------------------------------------
def launch_exe(exe_path, workdir, log):
    """用 ShellExecuteW(runas) 启动游戏，返回 (ok, msg, pid)。

    pid 可能为 None（提权后抓进程需要轮询 tasklist）。
    """
    if not exe_path or not os.path.exists(exe_path):
        return False, "找不到 %s" % exe_path, None
    name = os.path.basename(exe_path)
    try:
        r = ctypes.windll.shell32.ShellExecuteW(
            None, "runas", exe_path, None, workdir or None, 1)
    except Exception as e:
        return False, "启动失败：%s" % e, None
    if int(r) <= 32:
        return False, "启动失败（错误码 %d），可能取消了 UAC。" % int(r), None
    if log:
        log("启动 %s（已弹 UAC 提权）" % name)
    # 轮询拿 PID（游戏已提权，OpenProcess 拿不到，只能查 tasklist）
    pid = None
    for _ in range(50):
        time.sleep(0.5)
        try:
            out = subprocess.run(
                ["tasklist", "/FI", "IMAGENAME eq %s" % name,
                 "/FO", "CSV", "/NH"],
                capture_output=True, text=True, errors="replace").stdout
        except Exception:
            continue
        for ln in out.splitlines():
            if name.lower() in ln.lower():
                parts = [p.strip('"') for p in ln.split('","')]
                if len(parts) >= 2 and parts[1].isdigit():
                    pid = int(parts[1])
                    break
        if pid:
            break
    return True, "启动成功", pid


# ----------------------------------------------------------------------------
# 界面样式常量
# ----------------------------------------------------------------------------
GROUP_QSS = ("QGroupBox{color:#89b4fa;font-size:9pt;font-weight:bold;"
             "border:1px solid #313244;border-radius:6px;margin-top:8px;"
             "padding:8px 6px 5px 6px;background:#181825;}"
             "QGroupBox::title{subcontrol-origin:margin;left:10px;padding:0 3px;}"
             # 关闭子控件继承的浅灰底板，避免圆角处透出方块
             "QGroupBox QLabel{background:transparent;border:none;}")
_BASE = ("QPushButton{border:none;border-radius:5px;padding:4px 10px;"
         "font-size:9pt;font-weight:bold;min-height:18px;"
         "background-clip:padding;}")
# 兜底：避免任何按钮沿用系统浅灰调色板（圆角下透出灰块）
_BTN_RESET = ("QPushButton{background:#313244;color:#cdd6f4;}"
              "QPushButton:hover{background:#45475a;}")
BTN_PLAN = {
    "A": _BASE + "QPushButton{background:#fab387;color:#1e1e2e;}QPushButton:hover{background:#f9e2af;}",
    "B": _BASE + "QPushButton{background:#89b4fa;color:#1e1e2e;}QPushButton:hover{background:#b4befe;}",
    "0": _BASE + "QPushButton{background:#6c7086;color:#cdd6f4;}QPushButton:hover{background:#7f849c;}",
}
BTN_RUN = _BASE + "QPushButton{background:#a6e3a1;color:#1e1e2e;}QPushButton:hover{background:#94e2d5;}"
BTN_FIX = _BASE + "QPushButton{background:#f9e2af;color:#1e1e2e;}QPushButton:hover{background:#fab387;}"
BTN_PLAIN = _BASE + "QPushButton{background:#313244;color:#cdd6f4;}QPushButton:hover{background:#45475a;}"


class GameTab(QWidget):
    def __init__(self, spec, root_dir, logger):
        super().__init__()
        self.spec = spec
        self.root_dir = root_dir
        self.logger = logger
        self.exe_path = None
        self.game_dir = None
        self.is_custom = bool(spec.get("custom"))
        self._build()
        if self.is_custom:
            self._load_custom()
        else:
            self.locate()

    def _build(self):
        v = QVBoxLayout(self)
        v.setContentsMargins(10, 10, 10, 10)
        v.setSpacing(8)
        # 给内容区一个最小高度，避免 QTabWidget 首帧把 GameTab 压扁
        self.setMinimumHeight(372)

        # --- 程序位置 ---
        gb = QGroupBox("程序位置")
        gb.setStyleSheet(GROUP_QSS)
        gl = QVBoxLayout(gb)
        gl.setSpacing(4)
        self.lbl_path = QLabel("未定位")
        self.lbl_path.setWordWrap(True)
        self.lbl_path.setStyleSheet("color:#a6e3a1;font-size:9pt;")
        gl.addWidget(self.lbl_path)

        row = QHBoxLayout()
        row.setSpacing(6)
        if self.is_custom:
            b_browse = QPushButton("选择任意程序 (.exe) ...")
        else:
            b_browse = QPushButton("手动选择 %s" % self.spec["display"])
        b_browse.setStyleSheet(BTN_PLAIN)
        b_browse.setMinimumHeight(26)
        b_browse.clicked.connect(self.browse)
        row.addWidget(b_browse)
        if not self.is_custom:
            b_auto = QPushButton("自动搜索")
            b_auto.setStyleSheet(BTN_PLAIN)
            b_auto.setMinimumHeight(26)
            b_auto.clicked.connect(self.auto_search)
            row.addWidget(b_auto)
        else:
            b_clr = QPushButton("清除")
            b_clr.setStyleSheet(BTN_PLAIN)
            b_clr.setMinimumHeight(26)
            b_clr.clicked.connect(self.clear_custom)
            row.addWidget(b_clr)
        row.addStretch(1)
        gl.addLayout(row)
        v.addWidget(gb)

        # --- 运行环境（DirectX 安装包）---
        gb5 = QGroupBox("运行环境（DirectX 运行库）")
        gb5.setStyleSheet(GROUP_QSS)
        g5 = QVBoxLayout(gb5)
        g5.setSpacing(4)
        r5 = QHBoxLayout()
        r5.setSpacing(8)
        self.b_dx9 = QPushButton("安装 DirectX 9.0c")
        self.b_dx9.setMinimumHeight(28)
        self.b_dx9.setMinimumWidth(140)
        self.b_dx9.setStyleSheet(BTN_PLAIN)
        self.b_dx9.clicked.connect(lambda: self.install_dx("dx9"))
        r5.addWidget(self.b_dx9, 0)
        self.b_dx6 = QPushButton("安装 DirectX 6")
        self.b_dx6.setMinimumHeight(28)
        self.b_dx6.setMinimumWidth(140)
        self.b_dx6.setStyleSheet(BTN_PLAIN)
        self.b_dx6.clicked.connect(lambda: self.install_dx("dx6"))
        r5.addWidget(self.b_dx6, 0)
        d5 = QLabel("若提示缺少 d3dx9_*.dll / ddraw / dplay 等组件，点此安装。"
                    "安装包已内置在工具里，无需联网。")
        d5.setStyleSheet("color:#a6adc8;font-size:8.5pt;")
        d5.setWordWrap(True)
        d5.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        r5.addWidget(d5, 1)
        g5.addLayout(r5)
        v.addWidget(gb5)

        # --- 当前方案 ---
        gb2 = QGroupBox("当前方案")
        gb2.setStyleSheet(GROUP_QSS)
        g2 = QVBoxLayout(gb2)
        g2.setSpacing(2)
        self.lbl_plan = QLabel("检测中 ...")
        f = QFont()
        f.setPointSize(10)
        f.setBold(True)
        self.lbl_plan.setFont(f)
        self.lbl_plan.setStyleSheet("color:#a6e3a1;")
        g2.addWidget(self.lbl_plan)
        self.lbl_files = QLabel("")
        self.lbl_files.setStyleSheet("color:#7f849c;font-size:8.5pt;")
        self.lbl_files.setWordWrap(True)
        g2.addWidget(self.lbl_files)
        self.lbl_compat = QLabel("兼容性：检测中 ...")
        self.lbl_compat.setStyleSheet("color:#f9e2af;font-size:9pt;")
        self.lbl_compat.setWordWrap(True)
        g2.addWidget(self.lbl_compat)
        v.addWidget(gb2)

        # --- 切换方案 ---
        gb3 = QGroupBox("切换方案（渲染层修复）")
        gb3.setStyleSheet(GROUP_QSS)
        g3 = QVBoxLayout(gb3)
        g3.setSpacing(4)
        avail = self.spec.get("plans") or ["A", "B", "0"]
        if self.spec.get("plan_hint"):
            hint = QLabel(self.spec["plan_hint"])
            hint.setStyleSheet("color:#fab387;font-size:8.5pt;")
            hint.setWordWrap(True)
            g3.addWidget(hint)
        for k in avail:
            r = QHBoxLayout()
            r.setSpacing(8)
            b = QPushButton(PLANS[k]["name"])
            b.setMinimumHeight(30)
            b.setMinimumWidth(206)
            b.setStyleSheet(BTN_PLAN.get(k, BTN_PLAIN))
            b.clicked.connect(lambda _=False, key=k: self.switch(key))
            r.addWidget(b, 0)
            d = QLabel(PLANS[k]["desc"])
            d.setStyleSheet("color:#a6adc8;font-size:8.5pt;")
            d.setWordWrap(True)
            d.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
            r.addWidget(d, 1)
            g3.addLayout(r)
        v.addWidget(gb3)

        # --- 兼容性修复 ---
        gb4 = QGroupBox("兼容层修复（解决「一操作就未响应」）")
        gb4.setStyleSheet(GROUP_QSS)
        g4 = QVBoxLayout(gb4)
        g4.setSpacing(4)
        r4 = QHBoxLayout()
        r4.setSpacing(8)
        self.b_fix = QPushButton("设置「XP SP3 兼容 + 管理员运行」")
        self.b_fix.setMinimumHeight(28)
        self.b_fix.setMinimumWidth(200)
        self.b_fix.setStyleSheet(BTN_FIX)
        self.b_fix.clicked.connect(self.fix_compat)
        r4.addWidget(self.b_fix, 0)
        d4 = QLabel("老引擎在 Win11 下多核 / 版本上报 / DPI / DirectInput 错乱，"
                    "必须叠加上此兼容标志才能正常操作。")
        d4.setStyleSheet("color:#a6adc8;font-size:8.5pt;")
        d4.setWordWrap(True)
        d4.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        r4.addWidget(d4, 1)
        g4.addLayout(r4)
        v.addWidget(gb4)

        # --- 操作 ---
        ops = QHBoxLayout()
        ops.setSpacing(8)
        self.b_run = QPushButton("▶  启动游戏（管理员）")
        self.b_run.setMinimumHeight(34)
        self.b_run.setStyleSheet(BTN_RUN)
        self.b_run.clicked.connect(self.run_game)
        ops.addWidget(self.b_run, 2)
        b_ref = QPushButton("刷新")
        b_ref.setMinimumHeight(34)
        b_ref.setStyleSheet(BTN_PLAIN)
        b_ref.clicked.connect(self.refresh)
        ops.addWidget(b_ref, 1)
        v.addLayout(ops)

        v.addStretch(0)

    # -------- 定位 --------
    def _apply_location(self, game_dir, exe_path):
        self.game_dir = game_dir
        self.exe_path = exe_path
        self.lbl_path.setText("✔ 已定位：%s" % exe_path)
        self.refresh()

    def _load_custom(self):
        """自定义面板：从记忆恢复上次选择。"""
        p = load_custom()
        if p and os.path.exists(p):
            self._apply_location(os.path.dirname(p), p)
            self.logger("已恢复上次自定义程序：%s" % p)
        else:
            self.lbl_path.setText("未选择。点「选择任意程序」指定一个 .exe"
                                  "（会记住路径，下次自动恢复）。")
            self.lbl_plan.setText("—")
            self.lbl_compat.setText("兼容性：—")

    def locate(self):
        cand = os.path.join(self.root_dir, self.spec["rel"])
        if os.path.exists(cand):
            self._apply_location(os.path.dirname(cand), cand)
            return
        # 显式 alts 候选（如 OS2cn.exe / OS2.exe）
        for a in self.spec.get("alts", []):
            c = os.path.join(self.root_dir, a)
            if os.path.exists(c):
                self._apply_location(os.path.dirname(c), c)
                return
        # 同级目录扫描：游戏根目录的兄弟目录（如 E:\Illusion\OS2）
        parent = os.path.dirname(os.path.abspath(self.root_dir))
        names = [self.spec.get("name")] + list(self.spec.get("alts", []))
        names = [n for n in names if n]
        try:
            for entry in os.scandir(parent):
                if not entry.is_dir():
                    continue
                for n in names:
                    c = os.path.join(entry.path, n)
                    if os.path.exists(c):
                        self._apply_location(os.path.dirname(c), c)
                        return
        except OSError:
            pass
        d = _read_reg_installdir(self.spec["reg_key"]) if self.spec.get("reg_key") else None
        if d:
            trials = [os.path.join(d, self.spec["name"]),
                      os.path.join(d, self.spec["rel"].split("\\")[-1])]
            trials += [os.path.join(d, a) for a in self.spec.get("alts", [])]
            for trial in trials:
                if os.path.exists(trial):
                    self._apply_location(os.path.dirname(trial), trial)
                    return
        self.lbl_path.setText("✘ 未找到 %s，请点「手动选择」或「自动搜索」" % self.spec["name"])
        self.lbl_plan.setText("—")
        self.lbl_compat.setText("兼容性：—")

    def set_root(self, root):
        self.root_dir = root
        if self.is_custom:
            return
        self.locate()

    def browse(self):
        start = self.root_dir if os.path.isdir(self.root_dir) else "C:\\"
        title = ("选择任意程序" if self.is_custom
                 else "选择 %s" % self.spec["name"])
        p, _ = QFileDialog.getOpenFileName(
            self, title, start, "可执行文件 (*.exe);;所有文件 (*.*)")
        if p:
            self._apply_location(os.path.dirname(p), p)
            self.logger("已手动定位 %s → %s" % (self.spec["display"], p))
            if self.is_custom:
                save_custom(p)
                self.logger("已记住该路径，下次打开自动恢复")

    def clear_custom(self):
        self.exe_path = None
        self.game_dir = None
        save_custom("")
        self.lbl_path.setText("未选择。点「选择任意程序」指定一个 .exe。")
        self.lbl_plan.setText("—")
        self.lbl_files.setText("")
        self.lbl_compat.setText("兼容性：—")

    def auto_search(self):
        self.logger("开始自动搜索 %s ..." % self.spec["display"])
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            found = search_games(progress=lambda m: self.logger("  " + m))
        finally:
            QApplication.restoreOverrideCursor()
        gk = self.spec["key"]
        if gk in found:
            gd, exe = found[gk]
            self._apply_location(gd, exe)
            self.logger("✔ 找到 %s → %s" % (self.spec["display"], exe))
        else:
            QMessageBox.information(self, "未找到",
                "自动搜索未找到 %s。\n请用「手动选择」指定文件。" % self.spec["name"])
            self.logger("✘ 自动搜索未找到 %s" % self.spec["display"])

    # -------- 方案 --------
    def refresh(self):
        if not self.game_dir:
            return
        cur = detect_plan(self.game_dir)
        self.lbl_plan.setText("当前：%s" % PLANS[cur]["name"])
        files = scan_files(self.game_dir)
        self.lbl_files.setText("已部署：" + ("、".join(n for n, _ in files)
                                          if files else "（无）"))
        # 兼容性状态
        if self.exe_path:
            v = read_compat(self.exe_path)
            if v and "WINXPSP3" in v and "RUNASADMIN" in v:
                self.lbl_compat.setText("兼容性：✔ 已设置 XP SP3 + 管理员运行")
                self.lbl_compat.setStyleSheet("color:#a6e3a1;font-size:10pt;")
            elif v:
                self.lbl_compat.setText("兼容性：⚠ 已设置但版本可能不对 → %r" % v)
                self.lbl_compat.setStyleSheet("color:#f9e2af;font-size:10pt;")
            else:
                self.lbl_compat.setText("兼容性：✘ 未设置（可能导致一操作就未响应）")
                self.lbl_compat.setStyleSheet("color:#f38ba8;font-size:10pt;")

    def _need_locate_msg(self):
        if self.is_custom:
            return "请先用「选择任意程序」指定一个 .exe。"
        return "请先定位 %s。" % self.spec["name"]

    def switch(self, key):
        if not self.game_dir:
            QMessageBox.warning(self, "未定位程序", self._need_locate_msg())
            return
        # 确保方案文件已释放
        ok0, msg0 = ensure_plans_extracted(self.root_dir, self.logger)
        if not ok0:
            QMessageBox.critical(self, "方案文件缺失", msg0)
            return
        ok, msg = deploy(self.game_dir, key, plans_root(self.root_dir),
                         self.logger, overrides=self.spec.get("overrides"))
        self.refresh()
        if ok:
            # 提示顺带设置兼容性
            msg2 = (msg + "\n\n可点「启动游戏」测试。\n\n"
                    "提示：若启动后一操作就未响应，请点上方"
                    "「设置 XP SP3 兼容 + 管理员运行」。")
            QMessageBox.information(self, "完成", msg2)
        else:
            QMessageBox.critical(self, "失败", msg)

    def fix_compat(self):
        if not self.exe_path:
            QMessageBox.warning(self, "未定位程序", self._need_locate_msg())
            return
        ok, msg = write_compat(self.exe_path, log=self.logger)
        self.refresh()
        if ok:
            QMessageBox.information(self, "完成", msg)
        else:
            QMessageBox.critical(self, "失败", msg)

    def run_game(self):
        if not self.exe_path:
            QMessageBox.warning(self, "未定位程序", self._need_locate_msg())
            return
        ok, msg, pid = launch_exe(self.exe_path, self.game_dir, self.logger)
        if not ok:
            QMessageBox.warning(self, "启动失败", msg)
            return
        if pid:
            self.logger("游戏已启动（PID %d）" % pid)

    def install_dx(self, which):
        """安装 / 修复 DirectX 运行库。

        dx9：运行内置的精简版 DirectX 9.0c 安装程序（安装 d3dx9_24~43 等）。
        dx6：把 DX6/DX7 时代的旧组件（d3drm 等，Win11 已移除）
             复制到游戏目录（DLL 搜索顺序优先取程序目录）。
        """
        pkg = DX_PACKAGES.get(which)
        if not pkg:
            return

        # ---------- DX6 老组件：直接复制 DLL 到游戏目录 ----------
        if pkg.get("copy_dlls"):
            src_dir = res_path(pkg["dir"])
            if not src_dir or not os.path.isdir(src_dir):
                QMessageBox.warning(
                    self, "组件缺失",
                    "未找到内置的 %s 组件目录。" % pkg["label"])
                return
            dlls = [f for f in os.listdir(src_dir) if f.lower().endswith(".dll")]
            if not dlls:
                QMessageBox.warning(self, "组件缺失", "内置组件目录里没有 DLL。")
                return
            if not self.game_dir:
                QMessageBox.warning(self, "未定位程序", self._need_locate_msg())
                return
            r = QMessageBox.question(
                self, "安装 %s" % pkg["label"],
                "将把以下旧版 DirectX 组件复制到游戏目录：\n\n  %s\n\n"
                "目标：%s\n\n"
                "（%s）\n\n是否继续？"
                % ("\n  ".join(dlls), self.game_dir, pkg["desc"]),
                QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
            if r != QMessageBox.Yes:
                return
            ok = 0
            for d in dlls:
                try:
                    shutil.copy2(os.path.join(src_dir, d),
                                 os.path.join(self.game_dir, d))
                    self.logger("  已安装组件 %s" % d)
                    ok += 1
                except Exception as e:
                    self.logger("[警告] 复制 %s 失败：%s" % (d, e))
            msg = ("已安装 %d/%d 个 DirectX 老组件到游戏目录。\n\n"
                   "说明：这些是 DirectX 6/7 时代的旧组件（如 d3drm.dll），"
                   "Windows 11 已不再自带，老游戏若提示缺少它们可用此方式补齐。"
                   % (ok, len(dlls)))
            self.logger("[完成] " + msg.replace("\n", " "))
            QMessageBox.information(self, "完成", msg)
            self.refresh()
            return

        # ---------- DX9：运行内置安装程序 ----------
        if not self.exe_path:
            QMessageBox.warning(self, "未定位程序", self._need_locate_msg())
            return
        path = res_path(pkg["file"])
        if not path or not os.path.exists(path):
            QMessageBox.warning(
                self, "安装包缺失",
                "未找到内置安装包 %s。\n\n"
                "可手动从微软官网下载 DirectX 最终用户运行库安装。" % pkg["file"])
            return
        r = QMessageBox.question(
            self, "安装 %s" % pkg["label"],
            "即将运行内置的 %s 安装包：\n%s\n\n"
            "安装过程可能需要管理员权限并重启，是否继续？\n"
            "（%s）" % (pkg["label"], pkg["file"], pkg["desc"]),
            QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
        if r != QMessageBox.Yes:
            return
        self.logger("启动 %s 安装包 ..." % pkg["label"])
        try:
            # 用 runas 提权运行安装包
            rc = ctypes.windll.shell32.ShellExecuteW(
                None, "runas", path,
                pkg.get("args", ""), os.path.dirname(path), 1)
            if rc <= 32:
                self.logger("[警告] 启动安装包返回码 %d（可能取消了 UAC）" % rc)
                QMessageBox.warning(self, "未能启动",
                                    "安装包启动失败（返回码 %d），可能取消了 UAC 提权。" % rc)
            else:
                self.logger("已启动 %s 安装程序（请在安装向导中完成）。" % pkg["label"])
        except Exception as e:
            self.logger("[错误] 启动安装包失败：%s" % e)
            QMessageBox.critical(self, "失败", str(e))


# ----------------------------------------------------------------------------
# 联系方式对话框
# ----------------------------------------------------------------------------
class ContactDialog(QDialog):
    """「联系作者」窗口：四个带 logo 的入口，点击直达对应主页 / 邮箱。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("联系作者 — %s" % APP_TITLE)
        self.setMinimumWidth(420)
        icon = res_path("logo.ico") or res_path("logo.png")
        if icon:
            self.setWindowIcon(QIcon(icon))
        self.setStyleSheet("QDialog{background:#1e1e2e;}")

        v = QVBoxLayout(self)
        v.setContentsMargins(16, 14, 16, 14)
        v.setSpacing(10)

        t = QLabel("联系作者")
        f = QFont()
        f.setPointSize(12)
        f.setBold(True)
        t.setFont(f)
        t.setStyleSheet("color:#89b4fa;")
        v.addWidget(t)

        sub = QLabel("点击下方任一项即可打开对应主页 / 邮箱")
        sub.setStyleSheet("color:#7f849c;font-size:9pt;")
        v.addWidget(sub)

        for _key, name, account, url, icn in CONTACTS:
            v.addWidget(self._make_row(name, account, url, icn))

        v.addSpacing(2)
        tip = QLabel("邮箱：%s" % CONTACTS[-1][2])
        tip.setStyleSheet("color:#6c7086;font-size:8.5pt;")
        tip.setTextInteractionFlags(Qt.TextSelectableByMouse)
        v.addWidget(tip)

        row = QHBoxLayout()
        row.addStretch(1)
        b = QPushButton("关闭")
        b.setMinimumHeight(30)
        b.setMinimumWidth(90)
        b.setStyleSheet(BTN_PLAIN)
        b.clicked.connect(self.close)
        row.addWidget(b)
        v.addLayout(row)

    def _make_row(self, name, account, url, icn):
        """一行：logo + 名称 + 账号，整行可点击。"""
        row = QFrame()
        row.setCursor(Qt.PointingHandCursor)
        row.setStyleSheet(
            "QFrame{background:#181825;border:1px solid #313244;"
            "border-radius:6px;}QFrame:hover{border:1px solid #89b4fa;}")
        h = QHBoxLayout(row)
        h.setContentsMargins(8, 6, 10, 6)
        h.setSpacing(10)

        ip = res_path(icn)
        ic = QLabel()
        if ip:
            ic.setPixmap(QPixmap(ip).scaled(26, 26, Qt.KeepAspectRatio,
                                            Qt.SmoothTransformation))
        else:
            ic.setText("●")
            ic.setStyleSheet("color:#89b4fa;font-size:14pt;")
        ic.setFixedSize(28, 28)
        ic.setStyleSheet("border:none;")
        h.addWidget(ic)

        col = QVBoxLayout()
        col.setSpacing(0)
        n = QLabel(name)
        n.setStyleSheet("color:#cdd6f4;font-size:9.5pt;font-weight:bold;"
                        "border:none;")
        col.addWidget(n)
        a = QLabel(account)
        a.setStyleSheet("color:#7f849c;font-size:8.5pt;border:none;")
        col.addWidget(a)
        h.addLayout(col, 1)

        h.addStretch(0)

        def _open(_e=None, u=url):
            open_url(u)

        row.mousePressEvent = lambda e, fn=_open: fn()
        return row


# ----------------------------------------------------------------------------
# 运行日志对话框
# ----------------------------------------------------------------------------
LOG_QSS = ("QPlainTextEdit{background:#11111b;color:#cdd6f4;"
           "font-family:Consolas,'Courier New',monospace;font-size:9pt;"
           "border:1px solid #313244;border-radius:5px;padding:6px;}")


class LogDialog(QDialog):
    """运行日志窗口：独立弹窗显示日志，支持导出 / 复制 / 清空。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("运行日志 — %s" % APP_TITLE)
        self.resize(860, 560)
        self.setMinimumSize(560, 360)
        icon = res_path("logo.ico") or res_path("logo.png")
        if icon:
            self.setWindowIcon(QIcon(icon))
        self.setStyleSheet("QDialog{background:#1e1e2e;}")

        v = QVBoxLayout(self)
        v.setContentsMargins(10, 10, 10, 10)
        v.setSpacing(8)

        self.box = QPlainTextEdit()
        self.box.setReadOnly(True)
        self.box.setStyleSheet(LOG_QSS)
        self.box.setLineWrapMode(QPlainTextEdit.NoWrap)
        v.addWidget(self.box, 1)

        row = QHBoxLayout()
        row.setSpacing(8)
        self.lbl_cnt = QLabel("共 0 行")
        self.lbl_cnt.setStyleSheet("color:#7f849c;font-size:9pt;")
        row.addWidget(self.lbl_cnt)
        row.addStretch(1)

        b_copy = QPushButton("复制全部")
        b_copy.setMinimumHeight(30)
        b_copy.setStyleSheet(BTN_PLAIN)
        b_copy.clicked.connect(self.copy_all)
        row.addWidget(b_copy)

        b_clear = QPushButton("清空")
        b_clear.setMinimumHeight(30)
        b_clear.setStyleSheet(BTN_PLAIN)
        b_clear.clicked.connect(self.clear_log)
        row.addWidget(b_clear)

        b_exp = QPushButton("导出日志 ...")
        b_exp.setMinimumHeight(30)
        b_exp.setStyleSheet(BTN_FIX)
        b_exp.clicked.connect(self.export_log)
        row.addWidget(b_exp)

        b_close = QPushButton("关闭")
        b_close.setMinimumHeight(30)
        b_close.setStyleSheet(BTN_PLAIN)
        b_close.clicked.connect(self.close)
        row.addWidget(b_close)
        v.addLayout(row)

    def set_text(self, text):
        self.box.setPlainText(text or "")
        n = self.box.document().blockCount()
        self.lbl_cnt.setText("共 %d 行" % n)
        sb = self.box.verticalScrollBar()
        sb.setValue(sb.maximum())

    def copy_all(self):
        QApplication.clipboard().setText(self.box.toPlainText())
        self.lbl_cnt.setText(self.lbl_cnt.text() + "　·　已复制到剪贴板")

    def clear_log(self):
        # 通知主窗口清空缓冲区，保持两处一致
        p = self.parent()
        if p is not None and hasattr(p, "_log_lines"):
            p._log_lines = []
            p._save_log_cache()
        self.box.clear()
        self.lbl_cnt.setText("共 0 行")

    def export_log(self):
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        default = os.path.join(app_dir(), "运行日志_%s.txt" % ts)
        path, _ = QFileDialog.getSaveFileName(
            self, "导出运行日志", default, "文本文件 (*.txt);;所有文件 (*)")
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write("运行日志 — %s %s\n" % (APP_TITLE, APP_VER))
                f.write("导出时间：%s\n" % datetime.datetime.now().strftime(
                    "%Y-%m-%d %H:%M:%S"))
                f.write("=" * 64 + "\n")
                f.write(self.box.toPlainText())
                f.write("\n")
        except Exception as e:
            QMessageBox.critical(self, "导出失败", str(e))
            return
        QMessageBox.information(self, "导出成功", "日志已保存到：\n%s" % path)


# ----------------------------------------------------------------------------
# 主窗口
# ----------------------------------------------------------------------------
class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.root_dir = find_local_game_root()
        self.setWindowTitle("%s %s" % (APP_TITLE, APP_VER))
        self.resize(APP_WIN_W, APP_WIN_H)
        self.setMinimumSize(620, 520)
        icon = res_path("logo.ico") or res_path("logo.png")
        if icon:
            self.setWindowIcon(QIcon(icon))
        self._build()
        # 首帧强制重新布局，修复「初次打开 UI 高度不对」
        QTimer.singleShot(0, self._fix_initial_layout)

    def _fix_initial_layout(self):
        """首帧后强制激活布局：解决初次打开标签页内控件被压扁/重叠。"""
        try:
            # 切一遍 tab 强制每个 GameTab 重新计算 sizeHint
            cur = self.tabs.currentIndex()
            if self.tabs.count() > 1:
                self.tabs.setCurrentIndex(1 - cur if cur == 0 else 0)
                self.tabs.setCurrentIndex(cur)
            self.layout().activate()
            for w in self.tab_widgets.values():
                lay = w.layout()
                if lay:
                    lay.invalidate()
                    lay.activate()
            self.tabs.updateGeometry()
            self.updateGeometry()
            self.adjustSize()
            w, h = self.width(), self.height()
            mw, mh = self.minimumSize().width(), self.minimumSize().height()
            if h < mh:
                self.resize(max(w, mw), mh)
        except Exception:
            pass

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 8, 10, 8)
        root.setSpacing(6)

        # 日志缓冲区（先建：标签页初始化时可能就要写日志）
        self._log_lines = []
        self._log_dialog = None
        self._contact_dialog = None

        # 顶栏（单行紧凑标题，版权信息只在此处出现一次）
        top = QHBoxLayout()
        top.setSpacing(8)
        lp = res_path("logo_big.png") or res_path("logo.png")
        if lp:
            lab = QLabel()
            lab.setPixmap(QPixmap(lp).scaled(36, 36, Qt.KeepAspectRatio,
                                             Qt.SmoothTransformation))
            lab.setFixedSize(36, 36)
            top.addWidget(lab)
        t1 = QLabel(APP_TITLE)
        f = QFont()
        f.setPointSize(12)
        f.setBold(True)
        t1.setFont(f)
        t1.setStyleSheet("color:#cdd6f4;")
        top.addWidget(t1)
        t2 = QLabel(APP_VER)
        t2.setStyleSheet("color:#89b4fa;font-size:9pt;")
        top.addWidget(t2)
        top.addStretch(1)

        # 「运行日志」按钮（点开独立日志窗口）
        self.b_log = QPushButton("运行日志")
        self.b_log.setMinimumHeight(26)
        self.b_log.setMinimumWidth(84)
        self.b_log.setStyleSheet(BTN_PLAIN)
        self.b_log.setToolTip("查看运行日志，可导出为 txt 文件")
        self.b_log.clicked.connect(self.open_log)
        top.addWidget(self.b_log)

        t3 = QLabel(APP_COPYRIGHT)
        t3.setStyleSheet("color:#6c7086;font-size:8pt;")
        t3.setCursor(Qt.PointingHandCursor)
        t3.setToolTip("点击查看作者联系方式")
        t3.mousePressEvent = lambda e: self.open_contact()
        top.addWidget(t3)
        root.addLayout(top)

        # 标签页
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet(
            "QTabWidget::pane{border:1px solid #313244;border-radius:6px;"
            "background:#1e1e2e;top:-1px;}"
            "QTabBar{background:transparent;}"
            "QTabBar::tab{background:#252537;color:#a6adc8;padding:6px 14px;"
            "border:1px solid #313244;border-bottom:none;"
            "border-top-left-radius:6px;border-top-right-radius:6px;"
            "margin-right:3px;margin-top:3px;font-size:9pt;}"
            "QTabBar::tab:hover{background:#313244;color:#cdd6f4;}"
            "QTabBar::tab:selected{background:#1e1e2e;color:#89b4fa;"
            "font-weight:bold;border-color:#89b4fa;}"
            "QTabBar::tab:!selected{margin-top:5px;}")
        self.tab_widgets = {}
        for g in GAMES:
            w = GameTab(g, self.root_dir, self.log)
            self.tabs.addTab(w, g["display"])
            self.tab_widgets[g["key"]] = w
        root.addWidget(self.tabs, 1)

        self.log("程序已启动 %s" % APP_VER)
        # 启动时自动释放内置方案文件
        QTimer.singleShot(200, self._auto_extract)

    def _auto_extract(self):
        ok, msg = ensure_plans_extracted(self.root_dir, self.log)
        if not ok:
            self.log("[警告] %s" % msg)
            self.log("  可点任意方案按钮重试释放，或手动放置 _方案切换 目录。")

    def log(self, msg, *args):
        """写一条日志到缓冲区；若日志窗口已打开则同步刷新。"""
        if args:
            try:
                msg = msg % args
            except Exception:
                pass
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        line = "[%s] %s" % (ts, msg)
        lines = getattr(self, "_log_lines", None)
        if lines is None:
            return
        lines.append(line)
        dlg = getattr(self, "_log_dialog", None)
        if dlg is not None and dlg.isVisible():
            dlg.set_text("\n".join(lines))

    def open_contact(self):
        """打开「联系作者」窗口。"""
        dlg = getattr(self, "_contact_dialog", None)
        if dlg is None:
            dlg = ContactDialog(self)
            self._contact_dialog = dlg
        dlg.show()
        dlg.raise_()
        dlg.activateWindow()

    def open_log(self):
        """打开（或前置）运行日志窗口。"""
        dlg = getattr(self, "_log_dialog", None)
        if dlg is None:
            dlg = LogDialog(self)
            self._log_dialog = dlg
        dlg.set_text("\n".join(self._log_lines))
        dlg.show()
        dlg.raise_()
        dlg.activateWindow()

    def _save_log_cache(self):
        """把当前日志落盘到 app_dir()/last_run.log（便于出错后回看）。"""
        try:
            with open(os.path.join(app_dir(), "last_run.log"),
                      "w", encoding="utf-8") as f:
                f.write("运行日志 — %s %s\n" % (APP_TITLE, APP_VER))
                f.write("=" * 64 + "\n")
                f.write("\n".join(self._log_lines))
                f.write("\n")
        except Exception:
            pass

    def closeEvent(self, ev):
        """退出前把日志落盘，方便事后排查。"""
        self._save_log_cache()
        super().closeEvent(ev)

    def change_root(self):
        p = QFileDialog.getExistingDirectory(self, "选择游戏根目录", self.root_dir)
        if not p:
            return
        self.root_dir = p
        for w in self.tab_widgets.values():
            w.set_root(p)
        self.log("已更改根目录 → %s" % p)
        ok, msg = ensure_plans_extracted(self.root_dir, self.log)
        self.log(msg)


class SplashScreen(QSplashScreen):
    """启动动画：白底 logo（尺寸 = 软件主窗口，只覆盖软件界面）+ 淡入淡出 + 启动音同步。

    - 画布尺寸 = 软件主窗口大小（700×620），**不铺满整屏**；由 `run()` 居中摆放，
      与随后出现的主窗口同位置同大小，视觉上像"软件窗口自己启动"。
    - logo 下方依次是黑色「イリュージョン」美术字（logo_illusion.png）+ 版权行。
    - 淡入淡出用 windowOpacity（比 QGraphicsOpacityEffect 稳，不依赖事件循环时序）。
    - 可挂启动音 + 时长：`attach_audio(player, dur_ms)`；淡入时播放，
      音频放完（或到达最小停留时长）后淡出，二者同步。
    """

    FADE_MS = 320           # 淡入 / 淡出各用多久
    HOLD_MS = 900           # 无音频（或音频很短）时的最小停留
    AUDIO_TAIL_MS = 250     # 音频放完后再多停一会儿才淡出
    MAX_WAIT_MS = 7000      # 兜底：最多等这么久一定淡出

    def __init__(self, size=None, geometry=None):
        # 显式几何（屏幕坐标）：由 run() 传入，使启动画面恰好盖住软件窗口区域。
        # 若未传入，则按 QSplashScreen 默认行为在主屏居中（与主窗口一致，仍可对齐）。
        self._explicit_geom = geometry
        # logo（白底画布上画，透明/白底素材都行）
        pm = None
        for name in ("logo_splash.png", "logo_big.png", "logo.png"):
            p = res_path(name)
            if p:
                pm = QPixmap(p)
                if not pm.isNull():
                    break
        if pm is None or pm.isNull():
            pm = QPixmap(200, 200)
            pm.fill(QColor("#ffffff"))

        if size is not None:
            sw, sh = int(size[0]), int(size[1])
        else:
            sw, sh = APP_WIN_W, APP_WIN_H
        canvas = QPixmap(sw, sh)
        canvas.fill(QColor("#ffffff"))
        painter = QPainter(canvas)

        # 1) logo：高约 36% 画布高，水平居中、靠上
        logo_size = max(120, int(sh * 0.36))
        scaled = pm.scaled(logo_size, logo_size, Qt.KeepAspectRatio,
                           Qt.SmoothTransformation)
        logo_y = int(sh * 0.10)
        painter.drawPixmap((sw - scaled.width()) // 2, logo_y, scaled)

        # 2) 黑色「イリュージョン」
        ill_y = logo_y + scaled.height() + int(sh * 0.02)
        ill = QPixmap(res_path("logo_illusion.png") or "")
        if not ill.isNull():
            ill_s = ill.scaledToWidth(int(sw * 0.70), Qt.SmoothTransformation)
            painter.drawPixmap((sw - ill_s.width()) // 2, ill_y, ill_s)
            ill_bottom = ill_y + ill_s.height()
        else:
            # 兜底：用系统字体直接画（中文字体普遍含假名）
            f = QFont()
            f.setFamilies(["Yu Gothic", "Meiryo", "MS Gothic",
                           "Microsoft YaHei", "SimHei"])
            f.setPointSize(max(18, int(sh * 0.055)))
            f.setBold(True)
            painter.setFont(f)
            painter.setPen(QColor("#000000"))
            painter.drawText(QRect(0, ill_y, sw, int(sh * 0.12)),
                             Qt.AlignHCenter | Qt.AlignTop, "イリュージョン")
            ill_bottom = ill_y + int(sh * 0.12)

        # 3) 版权行
        cf = QFont()
        cf.setPointSize(max(9, int(sh * 0.018)))
        painter.setFont(cf)
        painter.setPen(QColor("#4a4a4a"))
        painter.drawText(QRect(0, ill_bottom + int(sh * 0.04), sw, int(sh * 0.08)),
                         Qt.AlignHCenter | Qt.AlignTop, APP_COPYRIGHT)

        # 4) 版本号（很小，底部）
        vf = QFont()
        vf.setPointSize(max(8, int(sh * 0.015)))
        painter.setFont(vf)
        painter.setPen(QColor("#b0b0b0"))
        painter.drawText(canvas.rect().adjusted(0, 0, 0, -int(sh * 0.025)),
                         Qt.AlignBottom | Qt.AlignHCenter, APP_VER)
        painter.end()

        super().__init__(canvas)
        self._closing = False
        self._audio = None
        self._audio_ms = 0
        self.setWindowFlag(Qt.FramelessWindowHint, True)
        self.setWindowFlag(Qt.WindowStaysOnTopHint, True)
        self.setAttribute(Qt.WA_TranslucentBackground, False)
        self.setWindowOpacity(0.0)

    def showEvent(self, ev):
        super().showEvent(ev)
        # QSplashScreen 默认会在 showEvent 里把自己居中到主屏；若调用方显式
        # 指定了几何（覆盖软件窗口区域），则强制应用，避免被自动居中覆盖。
        if self._explicit_geom is not None:
            self.setGeometry(self._explicit_geom)

    def attach_audio(self, player, dur_ms=0):
        """挂启动音 + 其时长（毫秒）；淡入起、放完止，与 logo 同步。"""
        self._audio = player
        self._audio_ms = int(dur_ms)

    def start(self):
        """显示并开始淡入（位置由调用方 `run()` 设定）。"""
        self.show()
        self.raise_()
        QTimer.singleShot(self.MAX_WAIT_MS, self._fade_out)
        self._fade_in()

    def _fade_in(self):
        if self._audio is not None:
            try:
                self._audio.play()
            except Exception:
                pass
        self._anim = QPropertyAnimation(self, b"windowOpacity")
        self._anim.setDuration(self.FADE_MS)
        self._anim.setStartValue(0.0)
        self._anim.setEndValue(1.0)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)
        self._anim.finished.connect(self._after_fade_in)
        self._anim.start()

    def _after_fade_in(self):
        base = max(self.HOLD_MS, self._audio_ms)
        QTimer.singleShot(base + self.AUDIO_TAIL_MS, self._fade_out)

    def _fade_out(self):
        if self._closing:
            return
        self._closing = True
        self._anim2 = QPropertyAnimation(self, b"windowOpacity")
        self._anim2.setDuration(self.FADE_MS)
        self._anim2.setStartValue(self.windowOpacity())
        self._anim2.setEndValue(0.0)
        self._anim2.setEasingCurve(QEasingCurve.InCubic)
        if self._audio is not None:
            try:
                self._audio.stop()
            except Exception:
                pass
        self._anim2.finished.connect(self.close)
        self._anim2.start()

    def finish_with(self, main_window):
        """主窗口就绪后调用：兜底确保动画结束后一定淡出。"""
        QTimer.singleShot(self.MAX_WAIT_MS, self._fade_out)


def _wav_duration_ms(path):
    """从 WAV 文件头解析真实时长（毫秒）。

    QSoundEffect 不直接暴露时长，这里手动解析 fmt / data 块：
    时长 = data 字节数 / (采样率 × 声道数 × 位深/8) × 1000。
    解析失败（非标准 PCM、缺块等）时退回用文件大小粗估，保证不报错。
    """
    try:
        with open(path, "rb") as fh:
            hdr = fh.read(12)
            if len(hdr) < 12 or hdr[0:4] != b"RIFF" or hdr[8:12] != b"WAVE":
                return 0
            sr = ch = bits = 0
            data_size = 0
            while True:
                chunk = fh.read(8)
                if len(chunk) < 8:
                    break
                cid = chunk[0:4]
                csize = int.from_bytes(chunk[4:8], "little")
                body = fh.read(csize)
                if len(body) < csize:
                    break
                if cid == b"fmt " and len(body) >= 16:
                    fmt = int.from_bytes(body[0:2], "little")
                    ch = int.from_bytes(body[2:4], "little")
                    sr = int.from_bytes(body[4:8], "little")
                    bits = int.from_bytes(body[14:16], "little")
                elif cid == b"data":
                    data_size = csize
        if sr and ch and bits and data_size:
            return int(data_size * 1000.0 / (sr * ch * bits / 8))
        # 退回：按文件大小粗估（假设 48k 立体声 16bit）
        return int(os.path.getsize(path) * 1000.0 / (48000 * 2 * 2))
    except Exception:
        return 0


def make_splash_audio():
    """随机挑一段启动音，返回 (QSoundEffect, dur_ms)。无音频时返回 (None, 0)。

    音频放在打包内的 `_splash_audio/` 目录，文件为 WAV（PCM16）。
    该目录从一个 `manifest.json` 读取白名单（键 `files` 为相对文件名列表）；
    没有 manifest 时取目录下全部 .wav。游戏原版有「三种启动音随机选一」的逻辑，
    这里保留同样的行为：每次启动随机取一条。返回的 dur_ms 用于让 logo
    淡入淡出与音频时长同步（音频更长时，淡出延后到音频播完之后）。
    """
    base = res_path("_splash_audio")
    if not base or not os.path.isdir(base):
        return (None, 0)
    files = []
    man = os.path.join(base, "manifest.json")
    if os.path.exists(man):
        try:
            import json
            lst = json.load(open(man, encoding="utf-8")).get("files", [])
            files = [f for f in lst if os.path.exists(os.path.join(base, f))]
        except Exception:
            files = []
    if not files:
        files = [f for f in os.listdir(base)
                 if f.lower().endswith(".wav")
                 and os.path.isfile(os.path.join(base, f))]
    if not files:
        return (None, 0)
    pick = files[QRandomGenerator.global_().bounded(len(files))]
    picked_path = os.path.join(base, pick)
    fx = QSoundEffect()
    fx.setSource(QUrl.fromLocalFile(picked_path))
    fx.setVolume(0.6)
    fx.setLoopCount(1)
    dur_ms = _wav_duration_ms(picked_path)
    return (fx, dur_ms)


def run():
    app = QApplication(sys.argv)
    # 统一暗色调色板：避免系统浅灰底板从圆角 / 原生控件处透出
    app.setStyle("Fusion")
    pal = app.palette()
    pal.setColor(QPalette.Window, QColor("#1e1e2e"))
    pal.setColor(QPalette.WindowText, QColor("#cdd6f4"))
    pal.setColor(QPalette.Base, QColor("#181825"))
    pal.setColor(QPalette.AlternateBase, QColor("#1e1e2e"))
    pal.setColor(QPalette.Text, QColor("#cdd6f4"))
    pal.setColor(QPalette.Button, QColor("#313244"))
    pal.setColor(QPalette.ButtonText, QColor("#cdd6f4"))
    pal.setColor(QPalette.ToolTipBase, QColor("#181825"))
    pal.setColor(QPalette.ToolTipText, QColor("#cdd6f4"))
    pal.setColor(QPalette.Highlight, QColor("#89b4fa"))
    pal.setColor(QPalette.HighlightedText, QColor("#1e1e2e"))
    pal.setColor(QPalette.PlaceholderText, QColor("#6c7086"))
    app.setPalette(pal)
    app.setStyleSheet("QWidget{background:#1e1e2e;color:#cdd6f4;}"
                      "QToolTip{background:#181825;color:#cdd6f4;"
                      "border:1px solid #45475a;padding:3px;}")
    # 启动动画（白底、只覆盖软件窗口区域的 logo + イリュージョン + 版权；
    # 淡入淡出与随机启动音时长同步）。splash 尺寸与主窗口一致，并居中到主屏，
    # 使其视觉上恰好盖住软件界面。
    splash_geom = None
    scr = app.primaryScreen()
    if scr is not None:
        sg = scr.geometry()
        splash_geom = QRect(
            sg.x() + (sg.width() - APP_WIN_W) // 2,
            sg.y() + (sg.height() - APP_WIN_H) // 2,
            APP_WIN_W, APP_WIN_H,
        )
    splash = SplashScreen((APP_WIN_W, APP_WIN_H), geometry=splash_geom)
    fx, dur_ms = make_splash_audio()
    if fx is not None:
        splash.attach_audio(fx, dur_ms)
    splash.start()
    w = MainWindow()
    w.show()
    splash.finish_with(w)
    sys.exit(app.exec())


if __name__ == "__main__":
    run()
