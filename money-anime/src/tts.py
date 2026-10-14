"""VOICEVOX エンジン（localhost:50021）で lines.tsv を音声にする。口パク用に母音のタイミングも保存。"""
import json, os, urllib.parse, urllib.request
HERE = os.path.dirname(os.path.abspath(__file__))
CAST = {"yui": dict(id=8, speed=1.12, pitch=0.02, inton=1.25),   # 春日部つむぎ
        "owl": dict(id=42, speed=1.3, pitch=0.0, inton=1.15)}   # ちび式じい
# セリフごとの細かい調整（驚き・ハイテンション・ためを入れる）
TWEAK = {2: dict(inton=1.5, pitch=0.05), 4: dict(inton=1.45, pitch=0.04, speed=1.15), 5: dict(speed=1.33)}
def post(path, q, body=None):
    url = f"http://localhost:50021/{path}?" + urllib.parse.urlencode(q)
    req = urllib.request.Request(url, data=body, method="POST", headers={"Content-Type": "application/json"})
    return urllib.request.urlopen(req).read()
timing = []
for i, row in enumerate(open(os.path.join(HERE, "lines.tsv"), encoding="utf-8")):
    who, text = row.rstrip("\n").split("\t")
    c = {**CAST[who], **TWEAK.get(i, {})}
    q = json.loads(post("audio_query", {"text": text, "speaker": c["id"]}))
    q.update(speedScale=c["speed"], pitchScale=c["pitch"], intonationScale=c["inton"],
             prePhonemeLength=0.05, postPhonemeLength=0.1, outputSamplingRate=44100, outputStereo=False)
    open(os.path.join(HERE, f"line{i}.wav"), "wb").write(post("synthesis", {"speaker": c["id"]}, json.dumps(q).encode()))
    # 母音タイムライン（秒）
    t, sp, vow = q["prePhonemeLength"] / c["speed"], c["speed"], []
    for ph in q["accent_phrases"]:
        for m in ph["moras"]:
            t += ((m["consonant_length"] or 0)) / sp
            vow.append([round(t, 3), round(t + m["vowel_length"] / sp, 3), m["vowel"]])
            t += m["vowel_length"] / sp
        if ph.get("pause_mora"):
            t += ph["pause_mora"]["vowel_length"] / sp
    timing.append(vow)
    print(i, who, round(t, 2), text)
json.dump(timing, open(os.path.join(HERE, "visemes.json"), "w"))
