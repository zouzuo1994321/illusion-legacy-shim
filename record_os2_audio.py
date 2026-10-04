# -*- coding: utf-8 -*-
"""
record_os2_audio.py —— 用「启动游戏 + 录音」的方式抓取《波动少女2》启动音

为什么需要它
------------
OS2 的启动电影包 os_00m/n/s.pp 用的是 Illusion 私有容器，ffmpeg 无法直接解封装，
从文件里抽「标题画面那三种随机启动 BGM」要做私有解码器逆向。
退一步：直接把游戏跑起来、录下系统播放出来的声音，反而最还原、零逆向。

原理
----
1. 用 ffmpeg 从「回环(loopback)音频设备」录一段系统声音：
   - 最省事：开启 Windows 的 **Stereo Mix（立体声混音）**，它把系统播放的声音当输入。
   - 或装 **VB-Audio Virtual Cable**：把游戏输出设到 Cable，再录 Cable 的回环，
     这样只录游戏、不录麦克风/其它。
2. 拉起 OS2cn.exe，等启动画面出现、随机启动音播完，ffmpeg 录一小段。
3. 用 ffmpeg 的 silenceremove 把前后静音裁掉，得到干净的一段启动音 WAV
   （44100Hz mono 16-bit，和工具里 QSoundEffect 播放的格式一致）。
4. 启动音每次随机，所以**录 3 次**（每次重开游戏）就拿到 3 种变体，
   脚本 `--batch 3` 会自动重开游戏、各录一段、写进 _splash_audio 并更新 manifest.json。

⚠️ 必须在「能正常玩 OS2」的真机 Windows 上跑（需要显示器 + 声卡 + 回环设备）。
   本脚本只负责「拉起游戏 + 录音 + 裁剪 + 落盘」，游戏本身要先能被修复工具正常启动。

用法
----
  # 抓一条（手动控制游戏启动时机也行，--no-launch 时不拉游戏）
  python record_os2_audio.py --out _splash_audio/os2_startup_1.wav --launch "E:/Illusion/OS2/OS2cn.exe"

  # 一次性抓 3 条随机变体（每次自动重开游戏）
  python record_os2_audio.py --batch 3

  # 指定回环设备（不指定的话会自动挑 Stereo Mix / CABLE / VB-Audio 等）
  python record_os2_audio.py --batch 3 --device "立体声混音 (Realtek(R) Audio)"

录完把 _splash_audio/ 里的 3 个 wav + manifest.json 重新打进 exe 即可（见底部说明）。
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(HERE, "_splash_audio")

# 回环/播放捕获设备的常见名字关键字（命中其一即视为可用回环源）
LOOPBACK_KEYWORDS = [
    "stereo mix", "立体声混音", "wave out", "what u hear", "what you hear",
    "cable", "vb-audio", "virtual cable", "loopback", "扬声器", "扬声器 (",
]


def find_ffmpeg(explicit=None):
    if explicit:
        return explicit
    cand = [
        "ffmpeg",
        shutil.which("ffmpeg"),
        r"C:/Users/zouzu/AppData/Roaming/bilibili/ffmpeg/ffmpeg.exe",
        r"C:/Users/zouzu/AppData/Local/JianyingPro/Apps/11.5.0.14471/ffmpeg.exe",
        r"C:/Users/zouzu/AppData/Roaming/PotPlayerMini64/Engine/Faster-Whisper-XXL/ffmpeg.exe",
    ]
    for c in cand:
        if not c:
            continue
        p = shutil.which(c) or c
        if p and os.path.exists(p):
            return p
    return None


def list_dshow_audio_devices(ff):
    """返回 dshow 音频输入设备名列表。"""
    out = subprocess.run([ff, "-list_devices", "true", "-f", "dshow", "-i",
                          "dummy"], stderr=subprocess.PIPE, stdout=subprocess.PIPE)
    txt = (out.stderr or b"").decode("utf-8", "ignore")
    devs = []
    in_audio = False
    for line in txt.splitlines():
        if "DirectShow audio devices" in line:
            in_audio = True
            continue
        if "DirectShow video devices" in line:
            in_audio = False
            continue
        if in_audio and '"' in line:
            # 形如 [dshow @ ...]  "设备名"
            name = line.split('"')[1] if line.count('"') >= 2 else ""
            if name:
                devs.append(name)
    return devs


def pick_loopback(devs, explicit=None):
    if explicit:
        if explicit in devs:
            return explicit
        # 允许部分匹配
        for d in devs:
            if explicit.lower() in d.lower():
                return d
        print("⚠️ 指定设备 %r 不在 dshow 列表里，可用设备：" % explicit)
        for d in devs:
            print("   -", d)
        return None
    for d in devs:
        low = d.lower()
        if any(k in low for k in LOOPBACK_KEYWORDS):
            return d
    return None


def launch_game(exe):
    if not exe or not os.path.exists(exe):
        print("⚠️ 未指定/找不到游戏 exe：%r（用 --no-launch 仅录音）" % exe)
        return None
    # 尽量用 ShellExecuteW(runas) 提权，避免游戏因需管理员而启动失败
    try:
        import ctypes
        from ctypes import wintypes
        SW_SHOWNORMAL = 1
        hinst = ctypes.windll.shell32.ShellExecuteW(
            None, "runas", exe, None, os.path.dirname(exe) or None, SW_SHOWNORMAL)
        return hinst
    except Exception:
        return subprocess.Popen([exe])


def record_clip(ff, device, raw_wav, duration, sr=44100):
    """从 dshow 设备录 duration 秒到 raw_wav（PCM16 mono）。"""
    cmd = [
        ff, "-y", "-hide_banner", "-loglevel", "error",
        "-f", "dshow", "-i", "audio=%s" % device,
        "-t", str(duration),
        "-ac", "1", "-ar", str(sr),
        "-c:a", "pcm_s16le",
        raw_wav,
    ]
    print("  录音中（%.0f 秒）…" % duration)
    r = subprocess.run(cmd)
    return r.returncode == 0 and os.path.exists(raw_wav)


def trim_silence(ff, raw_wav, out_wav):
    """用 silenceremove 裁掉前后静音，输出干净启动音。"""
    cmd = [
        ff, "-y", "-hide_banner", "-loglevel", "error",
        "-i", raw_wav,
        "-af", "silenceremove=start_periods=1:start_duration=0.15:start_threshold=-35dB:"
               "stop_periods=1:stop_duration=0.4:stop_threshold=-35dB",
        "-ar", "44100", "-ac", "1", "-c:a", "pcm_s16le",
        out_wav,
    ]
    r = subprocess.run(cmd)
    return r.returncode == 0 and os.path.exists(out_wav)


def clip_duration(wav):
    try:
        import wave
        with wave.open(wav, "rb") as w:
            return w.getnframes() / w.getframerate()
    except Exception:
        return 0.0


def write_manifest(files):
    man = {
        "note": "启动音白名单（相对本目录的文件名）。优先使用「启动游戏+录音」抓到的真实标题启动音"
                "（os2_startup_*.wav）；来源见 record_os2_audio.py。游戏原版「启动画面三种音频随机选一」，"
                "这里保留同样行为：每次启动随机取一条。音频为 44100Hz mono 16-bit WAV。",
        "sample_rate": 44100,
        "channels": 1,
        "files": files,
    }
    with open(os.path.join(OUT_DIR, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(man, f, ensure_ascii=False, indent=2)
    print("manifest.json 已更新：", files)


def main():
    ap = argparse.ArgumentParser(description="启动 OS2 并录制启动音")
    ap.add_argument("--ffmpeg", default=None, help="ffmpeg 路径（默认自动查找）")
    ap.add_argument("--launch", default="E:/Illusion/OS2/OS2cn.exe",
                    help="要启动的游戏 exe（默认 OS2cn.exe）；--no-launch 则不启动")
    ap.add_argument("--no-launch", action="store_true", help="只录音，不拉起游戏")
    ap.add_argument("--device", default=None, help="回环音频设备名（默认自动挑）")
    ap.add_argument("--out", default=None, help="单条输出 wav（不指定则按批次命名）")
    ap.add_argument("--batch", type=int, default=0, help="抓几条（每次重开游戏）")
    ap.add_argument("--preroll", type=float, default=6.0,
                    help="拉起游戏后等多久开始录（秒）")
    ap.add_argument("--duration", type=float, default=22.0,
                    help="每次录音时长（秒，建议 > 启动音长度）")
    args = ap.parse_args()

    ff = find_ffmpeg(args.ffmpeg)
    if not ff:
        print("✘ 找不到 ffmpeg。请安装或用 --ffmpeg 指定路径。")
        sys.exit(1)
    print("ffmpeg:", ff)

    devs = list_dshow_audio_devices(ff)
    print("可用 dshow 音频设备：", devs)
    device = pick_loopback(devs, args.device)
    if not device:
        print("\n✘ 没找到回环(loopback)音频设备。请先二选一开启：")
        print("  ① 控制面板 → 声音 → 录制 → 右键启用「立体声混音(Stereo Mix)」")
        print("  ② 或装 VB-Audio Virtual Cable，把游戏输出设到 Cable，再录 Cable 回环")
        print("然后在支持的设备名里挑一个（Stereo Mix / CABLE / VB-Audio 等）用 --device 指定。")
        sys.exit(2)
    print("使用回环设备：", device)

    n = args.batch if args.batch > 0 else 1
    produced = []
    for i in range(1, n + 1):
        out_wav = args.out if (n == 1 and args.out) else \
            os.path.join(OUT_DIR, "os2_startup_%d.wav" % i)
        raw_wav = out_wav + ".raw.tmp.wav"
        print("\n--- 第 %d/%d 条 ---" % (i, n))
        proc = None
        if not args.no_launch:
            proc = launch_game(None if args.no_launch else args.launch)
            print("  已拉起游戏，等待 %.0f 秒让启动画面出现…" % args.preroll)
            time.sleep(args.preroll)
        elif args.launch and not args.no_launch:
            proc = launch_game(args.launch)
            time.sleep(args.preroll)
        ok = record_clip(ff, device, raw_wav, args.duration)
        if not ok:
            print("  ✘ 录音失败（设备可能没声音，或游戏没出声）")
            if raw_wav and os.path.exists(raw_wav):
                os.remove(raw_wav)
            continue
        if trim_silence(ff, raw_wav, out_wav):
            dur = clip_duration(out_wav)
            print("  ✔ 已保存 %s（净长 %.2f 秒）" % (out_wav, dur))
            produced.append(os.path.basename(out_wav))
        else:
            print("  ✘ 裁剪失败")
        if os.path.exists(raw_wav):
            os.remove(raw_wav)
        # 关闭上一局游戏，下一轮重开（拿随机的另一种）
        if proc is not None:
            try:
                if isinstance(proc, subprocess.Popen):
                    proc.terminate()
            except Exception:
                pass
            time.sleep(2)

    if produced:
        write_manifest(produced)
        print("\n✔ 共抓到 %d 条启动音，已写入 _splash_audio 并更新 manifest.json" % len(produced))
        print("   重新打包 exe 即可生效（pyinstaller \"Illusion老游戏修复工具.spec\" --noconfirm）。")
    else:
        print("\n✘ 本次没有产出可用音频，请检查回环设备与游戏是否能正常出声。")


if __name__ == "__main__":
    main()
