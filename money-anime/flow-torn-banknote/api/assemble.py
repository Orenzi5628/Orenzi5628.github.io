"""4本のクリップ・ナレーション・字幕をまとめて、縦型ショート動画にする（API は使わない）。

使い方:
  python3 assemble.py                     各クリップの最新の take を使う
  python3 assemble.py --takes 1,3,2,1     clip1 は take1、clip2 は take3 … のように選ぶ
  python3 assemble.py --voice voicevox    ナレーションを VOICEVOX 版（../voice/）にする（既定は Gemini 版 out/ があればそれ）

出力: ../torn_banknote_short.mp4（1080x1920 / 30fps / 32秒、字幕焼き込み）
"""
import argparse, glob, os, re, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")
FINAL = os.path.join(HERE, "..", "torn_banknote_short.mp4")
FONT = "Noto Sans CJK JP"


def latest(n):
    files = sorted(glob.glob(os.path.join(OUT, f"clip{n}_take*.mp4")), key=lambda p: int(re.search(r"take(\d+)", p).group(1)))
    if not files:
        sys.exit(f"out/clip{n}_take*.mp4 がありません。先に veo_clips.py でクリップを作ってください。")
    return files[-1]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--takes", help="各クリップの take 番号（例: 1,3,2,1）")
    ap.add_argument("--voice", choices=["auto", "gemini", "voicevox"], default="auto")
    ap.add_argument("--clip-volume", type=float, default=0.15, help="クリップ側の効果音の音量（0で無音）")
    a = ap.parse_args()
    clips = ([os.path.join(OUT, f"clip{i + 1}_take{t}.mp4") for i, t in enumerate(a.takes.split(","))]
             if a.takes else [latest(n) for n in range(1, 5)])
    gem = os.path.join(OUT, "narration_32s.wav")
    vdir = OUT if (a.voice == "gemini" or (a.voice == "auto" and os.path.exists(gem))) else os.path.join(HERE, "..", "voice")
    narration, srt = os.path.join(vdir, "narration_32s.wav"), os.path.join(vdir, "subtitles.srt")
    for p in clips + [narration, srt]:
        if not os.path.exists(p):
            sys.exit(f"見つかりません: {p}")

    # 各クリップを 1080x1920・30fps・8秒・音ありにそろえる（音がないクリップには無音を足す）
    parts = []
    with tempfile.TemporaryDirectory() as d:
        for i, p in enumerate(clips):
            q = os.path.join(d, f"p{i}.mp4")
            has_audio = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a", "-show_entries", "stream=index",
                                        "-of", "csv=p=0", p], capture_output=True, text=True).stdout.strip() != ""
            inputs = ["-i", p] + ([] if has_audio else ["-f", "lavfi", "-t", "8", "-i", "anullsrc=r=44100:cl=mono"])
            amap = "0:a" if has_audio else "1:a"
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *inputs,
                            "-vf", "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,fps=30,setsar=1",
                            "-map", "0:v", "-map", amap, "-t", "8", "-af", "apad", "-ar", "44100", "-ac", "1",
                            "-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p", "-c:a", "aac", q], check=True)
            parts.append(q)
        lst = os.path.join(d, "list.txt")
        open(lst, "w").write("".join(f"file '{q}'\n" for q in parts))
        joined = os.path.join(d, "joined.mp4")
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", joined], check=True)
        style = (f"FontName={FONT},FontSize=7.6,PrimaryColour=&H00FFFFFF,OutlineColour=&H00302A3A,BorderStyle=1,"
                 f"Outline=1.3,Shadow=0,Alignment=2,MarginV=62,Bold=1")
        srt_esc = srt.replace("\\", "/").replace(":", "\\:").replace("'", "\\'")
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", joined, "-i", narration,
                        "-filter_complex",
                        f"[0:v]subtitles='{srt_esc}':force_style='{style}'[v];"
                        f"[0:a]volume={a.clip_volume}[fx];[1:a]volume=1.0[vo];[fx][vo]amix=inputs=2:duration=first:normalize=0[a]",
                        "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-crf", "20", "-pix_fmt", "yuv420p",
                        "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", FINAL], check=True)
    print(f"できました: {os.path.relpath(FINAL, HERE)}  （ナレーション: {os.path.relpath(narration, HERE)}）")


if __name__ == "__main__":
    main()
