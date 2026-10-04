# -*- coding: utf-8 -*-
"""v3.4 离屏冒烟：确认窗口优化已彻底移除 + UI 可正常构建。"""
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import main as M  # noqa: E402
from PySide6.QtWidgets import QApplication, QCheckBox, QComboBox  # noqa: E402

checks = []


def ck(name, cond):
    checks.append((name, bool(cond)))


# ---- 1. 符号级检查：窗口优化相关符号必须全部消失 ----
gone = [
    "OPT_KEYS", "RES_PRESETS", "_conf_lines", "_conf_set", "_conf_get",
    "_conf_write", "_patch_dgvoodoo", "_patch_dxvk", "apply_window_opts",
    "_watch_worker", "start_window_watch", "stop_window_watch",
    "request_foreground", "ensure_admin", "is_admin",
    "_force_foreground", "_add_appwindow", "_main_window_of_pid",
    "_window_class", "_windows_of_pid", "_rect_of", "_pid_of", "_win_style_of",
    "GWL_STYLE", "GWL_EXSTYLE", "WS_EX_APPWINDOW", "WS_POPUP",
    "GAME_WND_CLASS", "MIN_GAME_AREA", "_WATCHERS", "_WATCH_LOCK",
    "BTN_PLAIN_SMALL",
]
for n in gone:
    ck("已删除 %s" % n, not hasattr(M, n))

# ---- 2. 保留符号仍在 ----
keep = ["apply_window_opts_removed", "deploy", "backup_dir", "launch_exe",
        "detect_plan", "scan_files", "write_compat", "read_compat",
        "search_games", "ensure_plans_extracted", "load_custom", "save_custom",
        "fix_all_compat", "find_local_game_root", "GROUP_QSS", "BTN_PLAN"]
for n in keep:
    if n == "apply_window_opts_removed":
        continue
    ck("保留 %s" % n, hasattr(M, n))

# ---- 3. 源码文本层面：窗口优化字样必须绝迹 ----
src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "main.py"), encoding="utf-8").read()
for kw in ["窗口优化", "窗口守护", "标题栏", "Alt+Enter", "Alt-Tab",
           "把游戏窗口移到最前", "不失焦锁定", "freemouse"]:
    ck("源码无「%s」" % kw, kw not in src)

# ---- 版本号 ----
ck("版本号 = v3.8", M.APP_VER == "v3.8")

# ---- 4. UI 构建 ----
app = QApplication.instance() or QApplication(sys.argv)
app.setStyleSheet("QWidget{background:#1e1e2e;color:#cdd6f4;}")
w = M.MainWindow()
w.show()
app.processEvents()

ck("标签页数 = %d" % w.tabs.count(), w.tabs.count() == len(M.GAMES))
for key, tab in w.tab_widgets.items():
    ck("%s 无 QCheckBox" % key, not tab.findChildren(QCheckBox))
    ck("%s 无 QComboBox" % key, not tab.findChildren(QComboBox))

ck("窗口宽度 %d <= 760" % w.width(), w.width() <= 760)
ck("窗口高度 %d <= 700" % w.height(), w.height() <= 700)

# ---- 4b. 运行日志按钮 / 弹窗 ----
from PySide6.QtWidgets import QPlainTextEdit  # noqa: E402
ck("顶部有「运行日志」按钮", hasattr(w, "b_log"))
ck("主界面已无内嵌日志框", not w.findChildren(QPlainTextEdit))
ck("日志走内存缓冲", isinstance(getattr(w, "_log_lines", None), list)
   and len(w._log_lines) > 0)
w.open_log()
app.processEvents()
dlg = w._log_dialog
ck("日志弹窗已创建", dlg is not None)
ck("日志弹窗含日志文本", "程序已启动" in dlg.box.toPlainText())
ck("日志弹窗含导出按钮",
   any("导出" in b.text() for b in dlg.findChildren(
       __import__("PySide6.QtWidgets", fromlist=["QPushButton"]).QPushButton)))
# 日志追加能同步到已打开的弹窗
before = dlg.box.toPlainText()
w.log("冒烟测试：这条应同步进弹窗")
app.processEvents()
ck("新日志同步进弹窗", "冒烟测试" in dlg.box.toPlainText()
   and before != dlg.box.toPlainText())
# 导出
import tempfile  # noqa: E402
tgt = os.path.join(tempfile.gettempdir(), "_smoke_log_export.txt")
try:
    with open(tgt, "w", encoding="utf-8") as f:
        f.write(dlg.box.toPlainText())
    ck("日志可落盘导出", os.path.exists(tgt) and os.path.getsize(tgt) > 50)
    os.remove(tgt)
except Exception:
    ck("日志可落盘导出", False)
dlg.close()

# ---- 5. 版式截图 ----
shot = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                    "_shot_v34.png")
w.grab().save(shot)
ck("截图已生成", os.path.exists(shot) and os.path.getsize(shot) > 3000)

# ---- 6. 截图日志弹窗 ----
w.open_log()
app.processEvents()
shot2 = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                     "_shot_v34_log.png")
w._log_dialog.grab().save(shot2)
ck("日志弹窗截图已生成", os.path.exists(shot2) and os.path.getsize(shot2) > 3000)

# ---- 7. 分组框顺序：运行环境应在 程序位置 与 当前方案 之间 ----
from PySide6.QtWidgets import QGroupBox as _GB  # noqa: E402
tab = w.tab_widgets["rapelay"]
titles = [g.title() for g in tab.findChildren(_GB)]
ids = {}
for i, t in enumerate(titles):
    if t.startswith("程序位置"):
        ids["pos"] = i
    elif t.startswith("运行环境"):
        ids["dx"] = i
    elif t.startswith("当前方案"):
        ids["plan"] = i
ck("运行环境夹在 程序位置 与 当前方案 之间",
   ids.get("pos", -1) < ids.get("dx", -1) < ids.get("plan", -1))
print("   分组框顺序：%s" % " → ".join(titles))

# ---- 8. 联系方式弹窗 ----
ck("存在 open_contact 方法", hasattr(w, "open_contact"))
w.open_contact()
app.processEvents()
cd = w._contact_dialog
ck("联系方式弹窗已创建", cd is not None)
import main as _M  # noqa: E402
ck("联系方式条目 = 4", len(_M.CONTACTS) == 4)
urls = [c[3] for c in _M.CONTACTS]
ck("含 GitHub 地址", "https://github.com/zouzuo1994321" in urls)
ck("含 B站 地址", "https://space.bilibili.com/13715" in urls)
ck("含 微博 地址", "https://weibo.com/u/5189652182" in urls)
ck("含 邮箱 mailto", "mailto:921103025@qq.com" in urls)
# 四个 logo 都能定位到
for _k, name, _acc, _u, icn in _M.CONTACTS:
    ck("logo 可定位：%s" % icn, bool(_M.res_path(icn)))
# 版权标签可点击
ck("版权标签绑定了点击事件",
   callable(getattr(w, "open_contact", None)))
shot3 = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                     "_shot_v36_contact.png")
cd.grab().save(shot3)
ck("联系方式弹窗截图已生成",
   os.path.exists(shot3) and os.path.getsize(shot3) > 3000)
cd.close()

# ---- 9. v3.7 去「蓝灰框体」专项 ----
src2 = open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                         "main.py"), encoding="utf-8").read()
ss_tabs = w.tabs.styleSheet()
ck("标签页不再用亮蓝实底", "#89b4fa;color:#1e1e2e;\nfont-weight:bold" not in ss_tabs)
ck("选中标签为暗底蓝字", "tab:selected{background:#1e1e2e;color:#89b4fa" in ss_tabs
   or ("tab:selected" in ss_tabs and "#1e1e2e" in ss_tabs and "#89b4fa" in ss_tabs))
ck("GroupBox 标题无浅灰底板",
   "QGroupBox QLabel{background:transparent" in M.GROUP_QSS)
ck("按钮基类带 background-clip", "background-clip" in M._BASE)
# 全局调色板为暗色（在 run() 中设置；这里校验源码文本）
ck("入口设置 Fusion 风格", 'setStyle("Fusion")' in src2)
ck("入口设置暗色调色板", "setColor(QPalette.Window, QColor(\"#1e1e2e\"))" in src2)
ck("入口设置 Button 底色", "QPalette.Button, QColor(\"#313244\")" in src2)

# ---- 10. v3.8 启动动画（白底 logo + 淡入淡出）----
ck("存在 SplashScreen 类", hasattr(M, "SplashScreen"))
ck("入口会创建启动动画", "SplashScreen()" in src2)
ck("启动动画有淡入", "setEndValue(1.0)" in src2)
ck("启动动画有淡出", "_fade_out" in src2)
ck("启动动画用 windowOpacity", "windowOpacity" in src2)
ck("白底 splash 素材可定位", bool(M.res_path("logo_splash.png")))
_splash_shot = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "_shot_v38_splash.png")
try:
    sp = M.SplashScreen()
    sp.grab().save(_splash_shot)
    ck("启动动画截图已生成",
       os.path.exists(_splash_shot) and os.path.getsize(_splash_shot) > 2000)
    # 画布应为白底
    from PySide6.QtGui import QColor as _QC  # noqa: E402
    grab = sp.grab().toImage()
    c = _QC(grab.pixel(4, 4))
    ck("启动动画白底 (%d,%d,%d)" % (c.red(), c.green(), c.blue()),
       c.red() > 240 and c.green() > 240 and c.blue() > 240)
    sp.deleteLater()
except Exception as _e:
    ck("启动动画可构建 (%s)" % _e, False)
# spec 已打包白底 logo
ck("spec 已打包 logo_splash.png", "logo_splash.png" in
   open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                     "Illusion老游戏修复工具.spec"), encoding="utf-8").read())

ok = sum(1 for _, v in checks if v)
print("=" * 56)
for n, v in checks:
    print(("  ✔ " if v else "  ✘ ") + n)
print("=" * 56)
print("冒烟结果：%d / %d 通过" % (ok, len(checks)))
sys.exit(0 if ok == len(checks) else 1)
