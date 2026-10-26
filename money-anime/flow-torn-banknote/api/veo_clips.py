"""Veo（Gemini API）で、ネコ先生の縦型クリップ（8秒 × 4本）を作る。

使い方（環境変数 GEMINI_API_KEY が必要。Veo は有料です）:
  python3 veo_clips.py                  確認だけ（API は呼ばない。プロンプトと本数を表示）
  python3 veo_clips.py --yes            4本すべて生成
  python3 veo_clips.py --clips 2,4 --yes   2本目と4本目だけ作り直す（前のものは take 番号を増やして残す）
  python3 veo_clips.py --fast --yes     速くて安い veo-3.1-fast で生成

ネコ先生は neko_sensei.jpg（提供画像）を参考画像として渡す。
1) まず「参考画像モード」（Flow の Ingredients と同じ）で 9:16 を試す。
2) API が縦向きの参考画像モードを受け付けない場合は、Gemini の画像モデルで
   「その場面にいるネコ先生」の縦長の最初のコマを作り、そこから動かす（画像から動画）。
出力: out/clip{N}_take{K}.mp4（最初のコマを作った場合は out/frames/clip{N}.png も）
"""
import argparse, glob, io, json, os, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")
REF = os.path.join(HERE, "neko_sensei.jpg")
IMAGE_MODELS = ["gemini-3.1-flash-image", "gemini-2.5-flash-image"]

COMMON = """Vertical 9:16 video, 8 seconds. 2D Japanese anime style with clean line art and soft cel shading, warm cream-colored tones, soft daylight, the feel of a friendly educational TV short.

Main character: "Neko-sensei", the gray cat from the reference image. An anthropomorphic gray cat standing upright, green eyes, thin round gold-rimmed glasses, white long-sleeved shirt, navy blue knit vest, mustard-yellow bow tie, a small magnifying glass in the vest's chest pocket, dark gray trousers, brown leather shoes, long gray tail. Keep his face, outfit and colors exactly the same as the reference image.

Important: Neko-sensei does NOT speak. His mouth stays closed the whole time; he communicates only with gestures and facial expressions (a voice-over will be added later). No dialogue, no voices, no narration.

Props: banknotes are simplified cartoon banknotes (pale greenish-beige paper with a simple border and an oval watermark area, no real currency details, no readable text or numbers).

No subtitles, no captions, no on-screen text, no background music. Only soft, subtle sound effects."""

CLIPS = [
    """Scene: a cozy study with a bookshelf and a wooden desk, softly blurred in the background.
Shot: medium close-up, slow push-in toward Neko-sensei.
Action: Neko-sensei holds up the left half of a banknote that is torn cleanly down the middle, showing it to the camera with one paw, tilting his head with a curious, playful look (mouth closed). Then he takes the small magnifying glass out of his vest's chest pocket, examines the torn banknote, looks back at the camera and gives a confident nod.
Sound: a soft paper rustle, a light tap when he picks up the magnifying glass.""",
    """Scene: Neko-sensei stands next to a large blank whiteboard with nothing written on it, in the same cozy study. Leave some empty space on the left side of the frame.
Shot: medium shot, static camera.
Action: he holds up a banknote that is almost complete, with only one small corner torn off. He smiles warmly with his mouth closed and nods approvingly, and a few small cartoon sparkles appear around the banknote.
Sound: a bright, short sparkle chime.""",
    """Scene: next to the same blank whiteboard in the cozy study. Leave some empty space on the left side of the frame.
Shot: medium close-up, gentle push-in.
Action: he holds up exactly one half of a banknote torn cleanly down the middle, then points at it with his other paw like a kind teacher, nodding slowly with his mouth closed.
Sound: a soft paper rustle.""",
    """Scene: the same cozy study, near a bright window.
Shot: close-up on his raised paw, then tilt up to a medium shot of Neko-sensei.
Action: a tiny scrap of a banknote rests on his paw pad. A gentle breeze lifts the scrap and it flutters away out of frame; his ears droop slightly in disappointment. Then he picks up a small envelope holding torn banknote pieces, looks at the camera with a gentle closed-mouth smile, and gives a small polite bow.
Sound: a light whoosh of wind, a soft paper sound.""",
]
NEGATIVE = ("talking, speaking, open mouth, lip movement, dialogue, voice, narration, music, "
            "text, letters, numbers, captions, subtitles, watermark, logo, realistic currency, "
            "photorealistic, 3D render, extra limbs, deformed paws, different character design")


def client():
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        sys.exit("GEMINI_API_KEY が設定されていません。環境の設定（Network secrets / 環境変数）に登録してから実行してください。")
    from google import genai
    return genai.Client(api_key=key)


def ref_image(types):
    return types.Image(image_bytes=open(REF, "rb").read(), mime_type="image/jpeg")


def first_frame(c, types, n):
    """参考画像から、その場面にいるネコ先生の縦長の最初のコマを作る。"""
    from PIL import Image
    path = os.path.join(OUT, "frames", f"clip{n}.png")
    if os.path.exists(path):
        return types.Image(image_bytes=open(path, "rb").read(), mime_type="image/png")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    prompt = ("Create the FIRST FRAME (a single still image) of this vertical 9:16 anime shot. "
              "Use the gray cat character from the attached image exactly as designed.\n\n" + COMMON + "\n\n" + CLIPS[n - 1])
    last = None
    for model in IMAGE_MODELS:
        try:
            r = c.models.generate_content(
                model=model, contents=[prompt, Image.open(REF)],
                config=types.GenerateContentConfig(response_modalities=["IMAGE"],
                                                   image_config=types.ImageConfig(aspect_ratio="9:16")))
            for part in r.parts:
                if part.inline_data:
                    part.as_image().save(path)
                    print(f"  最初のコマを作成: out/frames/clip{n}.png（{model}）")
                    return types.Image(image_bytes=open(path, "rb").read(), mime_type="image/png")
            last = "画像が返ってきませんでした"
        except Exception as e:  # 次のモデルを試す
            last = e
    raise RuntimeError(f"最初のコマを作れませんでした: {last}")


def run(c, types, model, n, mode):
    """1本生成して保存。mode='reference' または 'frame'。"""
    cfg = dict(aspect_ratio="9:16", duration_seconds=8, negative_prompt=NEGATIVE, generate_audio=False)
    kw = {}
    if mode == "reference":
        cfg.update(resolution="720p",
                   reference_images=[types.VideoGenerationReferenceImage(image=ref_image(types), reference_type="asset")])
    else:
        cfg.update(resolution="1080p")
        kw["image"] = first_frame(c, types, n)
    prompt = COMMON + "\n\n" + CLIPS[n - 1]
    for attempt in range(2):
        try:
            op = c.models.generate_videos(model=model, prompt=prompt, config=types.GenerateVideosConfig(**cfg), **kw)
            break
        except Exception as e:
            if "generate_audio" in str(e) and "generate_audio" in cfg:   # 音なし指定に未対応なら外す（音は編集で消す）
                cfg.pop("generate_audio")
                continue
            raise
    while not op.done:
        time.sleep(15)
        op = c.operations.get(op)
    if getattr(op, "error", None):
        raise RuntimeError(op.error)
    vids = op.result.generated_videos if op.result else []
    if not vids:
        raise RuntimeError(f"動画が返ってきませんでした（安全フィルタで止まった可能性があります）: {op}")
    take = len(glob.glob(os.path.join(OUT, f"clip{n}_take*.mp4"))) + 1
    path = os.path.join(OUT, f"clip{n}_take{take}.mp4")
    c.files.download(file=vids[0].video)
    vids[0].video.save(path)
    return path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--clips", default="1,2,3,4", help="作るクリップ番号（例: 2,4）")
    ap.add_argument("--fast", action="store_true", help="veo-3.1-fast-generate-preview を使う（速く安い）")
    ap.add_argument("--mode", choices=["auto", "reference", "frame"], default="auto")
    ap.add_argument("--yes", action="store_true", help="API を呼んで生成する（料金がかかります）")
    a = ap.parse_args()
    nums = [int(x) for x in a.clips.split(",")]
    model = "veo-3.1-fast-generate-preview" if a.fast else "veo-3.1-generate-preview"
    if not a.yes:
        print(f"確認だけ（--yes なしでは API を呼びません）。モデル {model}、9:16・8秒 × {len(nums)}本 = {8 * len(nums)}秒分")
        for n in nums:
            print(f"\n--- clip{n} ---\n{CLIPS[n - 1]}")
        return
    from google.genai import types
    os.makedirs(OUT, exist_ok=True)
    c = client()
    log_path = os.path.join(OUT, "veo_log.json")
    log = json.load(open(log_path)) if os.path.exists(log_path) else []
    mode = a.mode
    for n in nums:
        print(f"clip{n} を生成中…（数分かかります）")
        try:
            used = "reference" if mode in ("auto", "reference") else "frame"
            try:
                path = run(c, types, model, n, used)
            except Exception as e:
                if mode != "auto":
                    raise
                print(f"  参考画像モードで縦向きが使えませんでした（{str(e)[:160]}）→ 最初のコマから作る方法に切り替えます")
                mode = used = "frame"
                path = run(c, types, model, n, used)
            print(f"  保存: {os.path.relpath(path, HERE)}（{used}）")
            log.append({"clip": n, "file": os.path.basename(path), "model": model, "mode": used, "time": time.strftime("%Y-%m-%d %H:%M")})
        except Exception as e:
            print(f"  clip{n} は失敗しました: {e}")
            log.append({"clip": n, "error": str(e)[:500], "model": model, "time": time.strftime("%Y-%m-%d %H:%M")})
        json.dump(log, open(log_path, "w"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
