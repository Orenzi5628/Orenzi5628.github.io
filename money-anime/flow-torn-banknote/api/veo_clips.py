"""Gemini API の動画モデルで、ネコ先生の縦型クリップ（8秒 × 4本）を作る。

Veo 3.1（veo-3.1-generate-preview）は 2026年10月時点で Gemini API から外され、後継の
Gemini Omni Flash（gemini-omni-1.1-flash、Interactions API）を使うように案内されているので、そちらで作る。

使い方（環境変数 GEMINI_API_KEY が必要。動画生成は有料で、無料枠のキーでは動きません）:
  python3 veo_clips.py                  確認だけ（API は呼ばない。プロンプトと本数を表示）
  python3 veo_clips.py --yes            4本すべて生成
  python3 veo_clips.py --clips 2,4 --yes   2本目と4本目だけ作り直す（前のものは take 番号を増やして残す）
  python3 veo_clips.py --model gemini-omni-flash-preview --yes   ほかの動画モデルを使う

ネコ先生は neko_sensei.jpg（提供画像）を参考画像として渡す。
1) まず「参考画像モード」（Flow の Ingredients と同じ。task=reference_to_video）で 9:16 を試す。
2) 参考画像モードが断られた場合は、Gemini の画像モデルで
   「その場面にいるネコ先生」の縦長の最初のコマを作り、そこから動かす（task=image_to_video）。
出力: out/clip{N}_take{K}.mp4（最初のコマを作った場合は out/frames/clip{N}.png も）
"""
import argparse, base64, glob, json, os, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")
REF = os.path.join(HERE, "neko_sensei.jpg")
MODEL = "gemini-omni-1.1-flash"
IMAGE_MODELS = ["gemini-3.1-flash-image", "gemini-3-pro-image"]
RESOLUTION = "1080p"

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


class QuotaError(RuntimeError):
    pass


def client():
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        sys.exit("GEMINI_API_KEY が設定されていません。環境の設定（Network secrets / 環境変数）に登録してから実行してください。")
    from google import genai
    return genai.Client(api_key=key)


def check_quota(e):
    text = str(e)
    if "RESOURCE_EXHAUSTED" in text or "429" in text:
        raise QuotaError("API の利用枠が足りません（無料枠のキーでは動画・画像の生成はできません）。"
                         "Google AI Studio でこのキーのプロジェクトに課金（Billing）を設定してから、もう一度実行してください。"
                         f"\n  詳細: {text[:300]}")


def b64(path):
    return base64.b64encode(open(path, "rb").read()).decode()


def first_frame(c, n):
    """参考画像から、その場面にいるネコ先生の縦長の最初のコマを作る。out/frames/clip{N}.png に保存。"""
    from google.genai import types
    from PIL import Image
    path = os.path.join(OUT, "frames", f"clip{n}.png")
    if os.path.exists(path):
        return path
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
            for part in r.parts or []:
                if part.inline_data:
                    part.as_image().save(path)
                    print(f"  最初のコマを作成: out/frames/clip{n}.png（{model}）")
                    return path
            last = "画像が返ってきませんでした"
        except Exception as e:  # 次のモデルを試す
            check_quota(e)
            last = e
    raise RuntimeError(f"最初のコマを作れませんでした: {last}")


def save_video(c, video, path):
    """返ってきた動画（inline の base64 / bytes、または URI）をファイルに保存する。"""
    data = getattr(video, "data", None)
    if data:
        open(path, "wb").write(base64.b64decode(data) if isinstance(data, str) else data)
        return
    uri = getattr(video, "uri", None)
    if not uri:
        raise RuntimeError(f"動画のデータが見つかりませんでした: {str(video)[:300]}")
    import httpx
    r = httpx.get(uri, headers={"x-goog-api-key": os.environ["GEMINI_API_KEY"]}, follow_redirects=True, timeout=300)
    r.raise_for_status()
    open(path, "wb").write(r.content)


def run(c, model, n, mode):
    """1本生成して保存。mode='reference'（参考画像）または 'frame'（最初のコマから）。"""
    if mode == "reference":
        image, mime, task = b64(REF), "image/jpeg", "reference_to_video"
    else:
        image, mime, task = b64(first_frame(c, n)), "image/png", "image_to_video"
    prompt = COMMON + "\n\n" + CLIPS[n - 1] + "\n\nAvoid: " + NEGATIVE + "."
    try:
        it = c.interactions.create(
            model=model, background=True,
            input=[{"type": "image", "data": image, "mime_type": mime}, {"type": "text", "text": prompt}],
            response_format={"type": "video", "aspect_ratio": "9:16", "duration": "8s", "resolution": RESOLUTION},
            generation_config={"video_config": {"task": task}},
        )
        while it.status in ("in_progress", "queued"):
            time.sleep(15)
            it = c.interactions.get(it.id)
    except Exception as e:
        check_quota(e)
        raise
    if it.status != "completed":
        errors = getattr(it, "errors", None) or it.model_dump(exclude_none=True).get("errors")
        check_quota(errors)
        raise RuntimeError(f"生成できませんでした（{it.status}）: {errors}")
    if it.output_video is None:
        raise RuntimeError("動画が返ってきませんでした（安全フィルタで止まった可能性があります）")
    take = len(glob.glob(os.path.join(OUT, f"clip{n}_take*.mp4"))) + 1
    path = os.path.join(OUT, f"clip{n}_take{take}.mp4")
    save_video(c, it.output_video, path)
    return path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--clips", default="1,2,3,4", help="作るクリップ番号（例: 2,4）")
    ap.add_argument("--model", default=MODEL, help=f"動画モデル（既定 {MODEL}）")
    ap.add_argument("--mode", choices=["auto", "reference", "frame"], default="auto")
    ap.add_argument("--yes", action="store_true", help="API を呼んで生成する（料金がかかります）")
    a = ap.parse_args()
    nums = [int(x) for x in a.clips.split(",")]
    if not a.yes:
        print(f"確認だけ（--yes なしでは API を呼びません）。モデル {a.model}、9:16・8秒 × {len(nums)}本 = {8 * len(nums)}秒分")
        for n in nums:
            print(f"\n--- clip{n} ---\n{CLIPS[n - 1]}")
        return
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
                path = run(c, a.model, n, used)
            except QuotaError:
                raise
            except Exception as e:
                if mode != "auto":
                    raise
                print(f"  参考画像モードで作れませんでした（{str(e)[:160]}）→ 最初のコマから作る方法に切り替えます")
                mode = used = "frame"
                path = run(c, a.model, n, used)
            print(f"  保存: {os.path.relpath(path, HERE)}（{used}）")
            log.append({"clip": n, "file": os.path.basename(path), "model": a.model, "mode": used, "time": time.strftime("%Y-%m-%d %H:%M")})
        except QuotaError as e:
            log.append({"clip": n, "error": str(e)[:500], "model": a.model, "time": time.strftime("%Y-%m-%d %H:%M")})
            json.dump(log, open(log_path, "w"), ensure_ascii=False, indent=1)
            sys.exit(f"  {e}")
        except Exception as e:
            print(f"  clip{n} は失敗しました: {e}")
            log.append({"clip": n, "error": str(e)[:500], "model": a.model, "time": time.strftime("%Y-%m-%d %H:%M")})
        json.dump(log, open(log_path, "w"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
