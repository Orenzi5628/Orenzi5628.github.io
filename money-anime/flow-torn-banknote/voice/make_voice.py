"""VOICEVOX（雀松朱司）でナレーションを作る。

lines.tsv: 1行1クリップ。「読み上げ用の文<TAB>字幕用の文」。
出力: clip1.wav〜clip4.wav（各クリップ用）、narration_32s.wav（4クリップ分を並べた全体）、subtitles.srt
各セリフは、そのクリップの頭から 0.4 秒後に始まる。

機械っぽさを減らすために、VOICEVOX の初期設定に次の調整を加えている。
- 「？」で付く、語尾をしゃくり上げる上昇をやめ、「〜かね」の「ね」を軽く上げるだけにする
- 読点・句点の間（ま）を、人が話すときの長さに近づける（文の終わりは長めに）
- 文の終わりは少しゆっくり、少し下げて言い切る
- 大事な言葉（全額・半額・日本銀行 など）を少しだけ強く・ゆっくり
- 一音ごとの長さにごくわずかな揺らぎを入れる（同じリズムの連続を避ける）
- 仕上げに、こもりを取るEQ・軽いコンプレッサー・ごく短い部屋の響き・小さな部屋の環境音を足す
"""
import io, json, os, subprocess, tempfile, urllib.parse, urllib.request, wave
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
SPEAKER, SPEED, INTONATION = 52, 1.03, 1.15      # 52 = 雀松朱司（ノーマル）
CLIP, LEAD, SR = 8.0, 0.4, 44100
PAUSE = {"、": 0.30, "。": 0.55, "？": 0.60, "！": 0.55}
EMPHASIS = ["ゼンガク", "ハンガク", "ニッポンギンコオ", "サンブンノニ", "ゴブンノニ", "ハンブン", "マドグチ"]


def post(path, q, body=None):
    url = f"http://localhost:50021/{path}?" + urllib.parse.urlencode(q)
    req = urllib.request.Request(url, data=body, method="POST", headers={"Content-Type": "application/json"})
    return urllib.request.urlopen(req).read()


def humanize(q, text, seed):
    """audio_query の抑揚と間を、人の話し方に近づける。"""
    rng = np.random.default_rng(seed)
    phrases = q["accent_phrases"]
    marks = [c for c in text if c in PAUSE]               # 文中の句読点（pause_mora と同じ順に並ぶ）
    k = 0
    for i, p in enumerate(phrases):
        moras = p["moras"]
        kana = "".join(m["text"] for m in moras)
        # 1) 疑問の語尾：機械的なしゃくり上げをやめ、最後の音を少しだけ上げて伸ばす
        if p.get("is_interrogative"):
            p["is_interrogative"] = False
            last, prev = moras[-1], moras[-2] if len(moras) > 1 else moras[-1]
            last["pitch"] = (prev["pitch"] or last["pitch"]) + 0.10
            last["vowel_length"] *= 1.35
        # 2) 大事な言葉を少し強調
        if any(w in kana for w in EMPHASIS):
            for m in moras:
                if m["pitch"] > 0:
                    m["pitch"] += 0.07
                m["vowel_length"] *= 1.08
        # 3) わずかなリズムの揺らぎ
        for m in moras:
            m["vowel_length"] *= 1 + rng.uniform(-0.04, 0.04)
        # 4) 句読点の間と、文末の言い切り
        if p.get("pause_mora") is not None and k < len(marks):
            mark = marks[k]
            k += 1
            p["pause_mora"]["vowel_length"] = PAUSE[mark] + rng.uniform(-0.03, 0.03)
            if mark in "。！":
                fall(moras)
    fall(phrases[-1]["moras"])                              # 最後の文の言い切り
    return q


def fall(moras):
    """文の終わり：最後の2音を少し下げて、少しゆっくりにする。"""
    voiced = [m for m in moras if m["pitch"] > 0]
    for j, m in enumerate(voiced[-2:]):
        m["pitch"] -= 0.05 * (j + 1)
        m["vowel_length"] *= 1.12


def room_ir(seconds=0.35):
    """ごく短い部屋の響き（インパルス応答）。"""
    rng = np.random.default_rng(1)
    n = int(seconds * SR)
    t = np.arange(n) / SR
    ir = rng.standard_normal(n) * np.exp(-t / 0.055)
    ir = np.convolve(ir, np.ones(12) / 12, mode="same")    # 高域を少し落として柔らかく
    ir[0] = 0
    return ir / np.abs(ir).sum()


IR = room_ir()


def finish(pcm):
    """EQ・コンプレッサー（ffmpeg）→ 部屋の響き → 部屋の環境音。float(-1..1) を返す。"""
    with tempfile.TemporaryDirectory() as d:
        src, dst = os.path.join(d, "in.wav"), os.path.join(d, "out.wav")
        write(src, pcm)
        chain = ("highpass=f=75,"
                 "equalizer=f=180:t=q:w=1.0:g=2.0,"      # 声の温かみ
                 "equalizer=f=3200:t=q:w=1.5:g=-1.5,"    # 合成音声のキンキンした成分を少し抑える
                 "equalizer=f=7500:t=q:w=2.0:g=-2.0,"
                 "acompressor=threshold=-22dB:ratio=2.2:attack=12:release=180:makeup=2")
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", src, "-af", chain, dst], check=True)
        x = read(dst)
    wet = np.convolve(x, IR)[:len(x)]
    y = x * 0.92 + wet * 0.35
    rng = np.random.default_rng(3)
    tone = np.convolve(rng.standard_normal(len(y)), np.ones(40) / 40, mode="same") * 0.0012  # 小さな部屋の環境音
    return y + tone


def read(path):
    with wave.open(path) as w:
        return np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768


def write(path, x):
    x = np.asarray(x, dtype=np.float32)
    with wave.open(path, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes((np.clip(x, -1, 1) * 32767).astype(np.int16).tobytes())


def srt_time(t):
    ms = int(round(t * 1000))
    return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"


rows = [r.split("\t") for r in open(os.path.join(HERE, "lines.tsv"), encoding="utf-8").read().strip().split("\n")]
voices, srt = [], []
for i, (speech, caption) in enumerate(rows):
    q = json.loads(post("audio_query", {"text": speech, "speaker": SPEAKER}))
    q = humanize(q, speech, seed=i)
    q.update(speedScale=SPEED, intonationScale=INTONATION, prePhonemeLength=0.0, postPhonemeLength=0.25,
             outputSamplingRate=SR, outputStereo=False)
    with wave.open(io.BytesIO(post("synthesis", {"speaker": SPEAKER}, json.dumps(q).encode()))) as w:
        pcm = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768
    dur = len(pcm) / SR
    assert LEAD + dur <= CLIP, f"clip{i + 1} が {CLIP} 秒に収まりません（{dur:.2f}秒）"
    voices.append(pcm)
    t0 = i * CLIP + LEAD
    cut = min((caption.find(ch) for ch in "。？" if 0 < caption.find(ch) < len(caption) - 1), default=-1)
    shown = caption[:cut + 1] + "\n" + caption[cut + 1:] if cut > 0 else caption  # 縦画面用に文の切れ目で2行に
    srt.append(f"{i + 1}\n{srt_time(t0)} --> {srt_time(t0 + dur)}\n{shown}\n")
    print(f"clip{i + 1}: {dur:.2f}秒  {caption}")

# 32秒の通しを作ってから仕上げ処理をかけ、クリップごとに切り出す（音のつながりがそろう）
full = np.zeros(int(CLIP * len(rows) * SR), dtype=np.float32)
for i, pcm in enumerate(voices):
    s = int((i * CLIP + LEAD) * SR)
    full[s:s + len(pcm)] = pcm
full = finish(full)
full *= 10 ** (-3 / 20) / max(1e-6, np.abs(full).max())   # ピークを -3dB にそろえる
write(os.path.join(HERE, "narration_32s.wav"), full)
for i in range(len(rows)):
    write(os.path.join(HERE, f"clip{i + 1}.wav"), full[int(i * CLIP * SR):int((i + 1) * CLIP * SR)])
open(os.path.join(HERE, "subtitles.srt"), "w", encoding="utf-8").write("\n".join(srt))
