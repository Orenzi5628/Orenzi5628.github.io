"""Gemini TTS でネコ先生のナレーションを作る（VOICEVOX 版の代わり）。

使い方（環境変数 GEMINI_API_KEY が必要）:
  python3 gemini_narration.py --design --yes   声を説明文から作り、試し聞き用 out/voice_preview.wav を保存
  python3 gemini_narration.py --yes            4本のセリフを生成（作った声がなければ先に作る）
  python3 gemini_narration.py --voice Sadaltager --yes   作った声の代わりに既成の声を使う

出力（out/）: narration_32s.wav（4クリップ分の通し）、clip1〜4.wav、subtitles.srt
並べ方は ../voice/（VOICEVOX 版）と同じ：各セリフはクリップの頭から 0.4 秒後に始まり、8 秒に収める。
セリフの原稿は ../voice/lines.tsv を使う（「読み上げ用の文<TAB>字幕用の文」）。
"""
import argparse, base64, io, json, os, subprocess, sys, tempfile, wave
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")
LINES = os.path.join(HERE, "..", "voice", "lines.tsv")
VOICE_ID_FILE = os.path.join(OUT, "voice_id.txt")
MODEL = "gemini-3.8-flash-tts"
CLIP, LEAD, SR = 8.0, 0.4, 44100
MAX_SPEEDUP = 1.12        # 8秒に収まらないとき、ここまでは速めて収める

VOICE_DESIGN = (
    "A gentle, warm and intelligent Japanese man in his early forties: a kind university professor. "
    "Soft, calm, slightly low voice with a quiet smile in it. Relaxed, unhurried pace. "
    "Clear standard Japanese with a natural Tokyo accent. Reassuring and friendly, never theatrical or announcer-like."
)
BASE_STYLE = (
    "Persona: Neko-sensei, a kind and wise cat professor gently explaining money to university students in a short video. "
    "Speak natural, conversational standard Japanese, warm and soft, at a relaxed pace with natural pauses. "
    "Sound like a real person talking to one student, not like an announcer or a machine."
)
LINE_STYLE = [
    "Begin with a playful, gentle question (light, curious, softly rising at the end), pause briefly, then reveal the answer warmly.",
    "Explain clearly and kindly, slightly emphasizing the key fraction and the word 全額.",
    "Kind and reassuring; slightly emphasize 半額 so it sticks.",
    "A little sympathetic at first, then warm encouragement at the end.",
]


def client():
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        sys.exit("GEMINI_API_KEY が設定されていません。環境の設定（Network secrets / 環境変数）に登録してから実行してください。")
    from google import genai
    return genai.Client(api_key=key)


def audio_bytes(obj):
    """API の返す音声（base64 文字列 / bytes / data 属性つき）を WAV/PCM の bytes にする。"""
    data = getattr(obj, "data", obj)
    if isinstance(data, str):
        data = base64.b64decode(data)
    return data


def to_wav_float(raw):
    """RIFF ならそのまま、生 PCM なら 24kHz として読み、44.1kHz の float 配列にする。"""
    with tempfile.TemporaryDirectory() as d:
        src, dst = os.path.join(d, "in.wav"), os.path.join(d, "out.wav")
        if raw[:4] == b"RIFF":
            open(src, "wb").write(raw)
        else:
            with wave.open(src, "wb") as w:
                w.setnchannels(1); w.setsampwidth(2); w.setframerate(24000); w.writeframes(raw)
        # 前後の無音を切り、44.1kHz モノラルに
        trim = ("silenceremove=start_periods=1:start_threshold=-50dB:start_silence=0.02,"
                "areverse,silenceremove=start_periods=1:start_threshold=-50dB:start_silence=0.05,areverse")
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", src, "-af", trim, "-ar", str(SR), "-ac", "1", dst], check=True)
        return read(dst)


def speedup(x, factor):
    with tempfile.TemporaryDirectory() as d:
        src, dst = os.path.join(d, "in.wav"), os.path.join(d, "out.wav")
        write(src, x)
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", src, "-af", f"atempo={factor:.4f}", dst], check=True)
        return read(dst)


def read(path):
    with wave.open(path) as w:
        return np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768


def write(path, x):
    with wave.open(path, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes((np.clip(np.asarray(x, dtype=np.float32), -1, 1) * 32767).astype(np.int16).tobytes())


def srt_time(t):
    ms = int(round(t * 1000))
    return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"


def design_voice(c):
    v = c.voices.create(store=True, voice={
        "model": MODEL, "type": "prompted", "display_name": "Neko-sensei",
        "prompted": {"input": VOICE_DESIGN},
    })
    open(VOICE_ID_FILE, "w").write(v.id)
    sample = getattr(v, "sample_audio", None)
    if sample is not None:
        write(os.path.join(OUT, "voice_preview.wav"), to_wav_float(audio_bytes(sample)))
        print("試し聞き用の音声: out/voice_preview.wav")
    print(f"声を作成しました: {v.id}（有効期限 {getattr(v, 'expire_time', '7日間')}）")
    return v.id


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--design", action="store_true", help="声を作り直す（試し聞き音声だけ作って終わる）")
    ap.add_argument("--voice", help="既成の声の名前（例: Sadaltager, Charon, Iapetus）。指定すると作った声は使わない")
    ap.add_argument("--yes", action="store_true", help="API を呼んで生成する（料金がかかる場合があります）")
    a = ap.parse_args()
    rows = [r.split("\t") for r in open(LINES, encoding="utf-8").read().strip().split("\n")]
    if not a.yes:
        print(f"確認だけ（--yes なしでは API を呼びません）。モデル {MODEL}、セリフ {len(rows)} 本:")
        for i, (speech, cap) in enumerate(rows):
            print(f"  clip{i + 1}: {speech}")
        return
    os.makedirs(OUT, exist_ok=True)
    c = client()
    if a.design:
        design_voice(c)
        return
    voice = a.voice or (open(VOICE_ID_FILE).read().strip() if os.path.exists(VOICE_ID_FILE) else design_voice(c))

    full = np.zeros(int(CLIP * len(rows) * SR), dtype=np.float32)
    srt = []
    for i, (speech, caption) in enumerate(rows):
        it = c.interactions.create(
            model=MODEL,
            input=[{"type": "text", "text": speech,
                    "annotations": [{"type": "speech_metadata", "style": BASE_STYLE + " " + LINE_STYLE[i]}]}],
            response_format={"type": "audio"},
            generation_config={"speech_config": [{"voice": voice}]},
        )
        x = to_wav_float(audio_bytes(it.output_audio))
        room = CLIP - LEAD - 0.1
        dur = len(x) / SR
        if dur > room:
            f = dur / room
            if f > MAX_SPEEDUP:
                sys.exit(f"clip{i + 1} が長すぎます（{dur:.2f}秒）。セリフを短くするか、もう一度生成してください。")
            x = speedup(x, f)
            dur = len(x) / SR
        x *= 10 ** (-3 / 20) / max(1e-6, np.abs(x).max())
        clip = np.zeros(int(CLIP * SR), dtype=np.float32)
        clip[int(LEAD * SR):int(LEAD * SR) + len(x)] = x
        write(os.path.join(OUT, f"clip{i + 1}.wav"), clip)
        full[int(i * CLIP * SR):int((i + 1) * CLIP * SR)] = clip
        t0 = i * CLIP + LEAD
        cut = min((caption.find(ch) for ch in "。？" if 0 < caption.find(ch) < len(caption) - 1), default=-1)
        shown = caption[:cut + 1] + "\n" + caption[cut + 1:] if cut > 0 else caption
        srt.append(f"{i + 1}\n{srt_time(t0)} --> {srt_time(t0 + dur)}\n{shown}\n")
        print(f"clip{i + 1}: {dur:.2f}秒  {caption}")
    write(os.path.join(OUT, "narration_32s.wav"), full)
    open(os.path.join(OUT, "subtitles.srt"), "w", encoding="utf-8").write("\n".join(srt))
    json.dump({"model": MODEL, "voice": voice}, open(os.path.join(OUT, "narration_info.json"), "w"), ensure_ascii=False)
    print("できました: out/narration_32s.wav, out/clip1〜4.wav, out/subtitles.srt")


if __name__ == "__main__":
    main()
