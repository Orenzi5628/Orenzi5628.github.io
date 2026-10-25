"""VOICEVOX（雀松朱司）でナレーションを作る。

lines.tsv: 1行1クリップ。「読み上げ用の文<TAB>字幕用の文」。
出力: clip1.wav〜clip4.wav（各クリップ用）、narration_32s.wav（4クリップ分を並べた全体）、subtitles.srt
各セリフは、そのクリップの頭から 0.4 秒後に始まる。
"""
import io, json, os, urllib.parse, urllib.request, wave
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
SPEAKER, SPEED, CLIP, LEAD, SR = 52, 1.05, 8.0, 0.4, 44100  # 52 = 雀松朱司（ノーマル）


def post(path, q, body=None):
    url = f"http://localhost:50021/{path}?" + urllib.parse.urlencode(q)
    req = urllib.request.Request(url, data=body, method="POST", headers={"Content-Type": "application/json"})
    return urllib.request.urlopen(req).read()


def srt_time(t):
    ms = int(round(t * 1000))
    return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"


rows = [r.split("\t") for r in open(os.path.join(HERE, "lines.tsv"), encoding="utf-8").read().strip().split("\n")]
full = np.zeros(int(CLIP * len(rows) * SR), dtype=np.int16)
srt = []
for i, (speech, caption) in enumerate(rows):
    q = json.loads(post("audio_query", {"text": speech, "speaker": SPEAKER}))
    q.update(speedScale=SPEED, intonationScale=1.1, prePhonemeLength=0.0, postPhonemeLength=0.2,
             outputSamplingRate=SR, outputStereo=False)
    data = post("synthesis", {"speaker": SPEAKER}, json.dumps(q).encode())
    with wave.open(io.BytesIO(data)) as w:
        pcm = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16)
    dur = len(pcm) / SR
    assert LEAD + dur <= CLIP, f"clip{i + 1} が {CLIP} 秒に収まりません（{dur:.2f}秒）"
    clip = np.zeros(int(CLIP * SR), dtype=np.int16)
    clip[int(LEAD * SR):int(LEAD * SR) + len(pcm)] = pcm
    for path, arr in ((f"clip{i + 1}.wav", clip),):
        with wave.open(os.path.join(HERE, path), "wb") as w:
            w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes(arr.tobytes())
    s = int(i * CLIP * SR)
    full[s:s + len(clip)] = clip
    t0 = i * CLIP + LEAD
    cut = min((caption.find(ch) for ch in "。？" if 0 < caption.find(ch) < len(caption) - 1), default=-1)
    shown = caption[:cut + 1] + "\n" + caption[cut + 1:] if cut > 0 else caption  # 縦画面用に文の切れ目で2行に
    srt.append(f"{i + 1}\n{srt_time(t0)} --> {srt_time(t0 + dur)}\n{shown}\n")
    print(f"clip{i + 1}: {dur:.2f}秒  {caption}")
with wave.open(os.path.join(HERE, "narration_32s.wav"), "wb") as w:
    w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes(full.tobytes())
open(os.path.join(HERE, "subtitles.srt"), "w", encoding="utf-8").write("\n".join(srt))
