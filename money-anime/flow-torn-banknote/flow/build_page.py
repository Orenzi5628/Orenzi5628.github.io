"""Flow 用の素材ページ（flow_kit.html）を作る。画像はページの中に埋め込む。"""
import base64
import html
import os

HERE = os.path.dirname(os.path.abspath(__file__))
LINES = os.path.join(HERE, "..", "voice", "lines.tsv")


def data_uri(name):
    mime = "image/jpeg" if name.endswith(".jpg") else "image/png"
    return f"data:{mime};base64," + base64.b64encode(open(os.path.join(HERE, name), "rb").read()).decode()


IMAGES = {
    "ref_neko_sensei.jpg": ("ネコ先生", "キャラクターの参考画像。4本すべてにつける"),
    "prop_half.png": ("半分に破れたお札", "クリップ1・3につける"),
    "prop_corner.png": ("角が欠けたお札", "クリップ2につける"),
    "prop_scrap.png": ("小さな切れはし", "クリップ4につける"),
}
CLIPS = [
    (1, "0〜8秒", "つかみ", ["ref_neko_sensei.jpg", "prop_half.png"]),
    (2, "8〜16秒", "3分の2以上 → 全額", ["ref_neko_sensei.jpg", "prop_corner.png"]),
    (3, "16〜24秒", "5分の2以上 → 半額", ["ref_neko_sensei.jpg", "prop_half.png"]),
    (4, "24〜32秒", "5分の2未満 → 交換できない", ["ref_neko_sensei.jpg", "prop_scrap.png"]),
]
narr = [r.split("\t")[1] for r in open(LINES, encoding="utf-8").read().strip().split("\n")]
uris = {k: data_uri(k) for k in IMAGES}

cards = []
for n, t, topic, imgs in CLIPS:
    prompt = open(os.path.join(HERE, f"prompt_clip{n}.txt"), encoding="utf-8").read().strip()
    chips = "".join(
        f'<figure class="chip"><img src="{uris[k]}" alt="{IMAGES[k][0]}"><figcaption>{IMAGES[k][0]}</figcaption></figure>'
        for k in imgs)
    cards.append(f"""
<section class="clip" id="clip-{n}">
  <header class="clip-head">
    <span class="num">{n}</span>
    <div><h2>クリップ{n}　{html.escape(topic)}</h2><p class="time">{t}</p></div>
  </header>
  <p class="narr"><span>ナレーション（後から重ねる声）</span>{html.escape(narr[n - 1])}</p>
  <div class="attach"><p class="label">つける画像（Ingredients）</p><div class="chips">{chips}</div></div>
  <div class="prompt">
    <div class="prompt-bar"><p class="label">プロンプト</p>
      <button type="button" class="copy" data-target="p{n}" id="copy-{n}">プロンプトをコピー</button></div>
    <textarea id="p{n}" readonly rows="9" aria-label="クリップ{n}のプロンプト">{html.escape(prompt)}</textarea>
  </div>
</section>""")

gallery = "".join(
    f'<figure class="big"><img src="{uris[k]}" alt="{v[0]}"><figcaption><b>{v[0]}</b><br>{v[1]}</figcaption></figure>'
    for k, v in IMAGES.items())

page = f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>破れたお札 Flow素材</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Zen+Maru+Gothic:wght@500;700&family=Noto+Sans+JP:wght@400;500;700&display=swap" rel="stylesheet">
<style>
:root {{
  /* お札の淡い緑を地に、ネコ先生のベストの紺を主役、蝶ネクタイの黄を合図に。縦に読む1カラム */
  --bg: #eef3ea;
  --card: #fbfdf8;
  --ink: #23302a;
  --muted: #5f6d64;
  --line: #cdd9c7;
  --accent: #2f4a7a;
  --signal: #e2a72e;
  --font-display: "Zen Maru Gothic", "Hiragino Maru Gothic ProN", sans-serif;
  --font-body: "Noto Sans JP", "Hiragino Sans", system-ui, sans-serif;
  color-scheme: light;
}}
@media (prefers-color-scheme: dark) {{
  :root:not([data-theme="light"]) {{
    --bg: #161c19; --card: #1f2723; --ink: #e6ede7; --muted: #a3b1a7; --line: #34413a;
    --accent: #9db5e8; --signal: #f0bd52; color-scheme: dark;
  }}
}}
:root[data-theme="dark"] {{
  --bg: #161c19; --card: #1f2723; --ink: #e6ede7; --muted: #a3b1a7; --line: #34413a;
  --accent: #9db5e8; --signal: #f0bd52; color-scheme: dark;
}}
* {{ box-sizing: border-box; }}
html, body {{ margin: 0; }}
body {{ background: var(--bg); color: var(--ink); font: 16px/1.7 var(--font-body); }}
main {{ max-width: 760px; margin: 0 auto; padding: 28px 18px 64px; display: grid; gap: 22px; }}
h1, h2, h3 {{ font-family: var(--font-display); text-wrap: balance; margin: 0; line-height: 1.35; }}
h1 {{ font-size: 1.9rem; }}
h2 {{ font-size: 1.2rem; }}
h3 {{ font-size: 1.1rem; }}
.lead {{ color: var(--muted); margin: 6px 0 0; }}
.box {{ background: var(--card); border: 1px solid var(--line); border-radius: 14px; padding: 18px; display: grid; gap: 10px; }}
.settings {{ display: grid; grid-template-columns: max-content 1fr; gap: 6px 16px; margin: 0; }}
.settings dt {{ color: var(--muted); }}
.settings dd {{ margin: 0; font-weight: 500; }}
.clip {{ background: var(--card); border: 1px solid var(--line); border-left: 5px solid var(--accent); border-radius: 14px; padding: 18px; display: grid; gap: 14px; }}
.clip-head {{ display: flex; gap: 12px; align-items: center; }}
.num {{ flex: none; width: 40px; height: 40px; border-radius: 50%; background: var(--accent); color: var(--card); display: grid; place-items: center; font: 700 1.15rem var(--font-display); }}
.time {{ margin: 0; color: var(--muted); font-size: .9rem; font-variant-numeric: tabular-nums; }}
.narr {{ margin: 0; padding: 10px 14px; border-radius: 10px; background: var(--bg); }}
.narr span, .label {{ display: block; font-size: .8rem; color: var(--muted); margin: 0 0 2px; }}
.chips {{ display: flex; flex-wrap: wrap; gap: 10px; }}
.chip {{ margin: 0; width: 120px; display: grid; gap: 4px; font-size: .8rem; color: var(--muted); }}
.chip img {{ width: 120px; height: 120px; object-fit: contain; background: #fff; border: 1px solid var(--line); border-radius: 10px; }}
.prompt {{ display: grid; gap: 6px; }}
.prompt-bar {{ display: flex; justify-content: space-between; align-items: end; gap: 10px; flex-wrap: wrap; }}
textarea {{ width: 100%; font: 13px/1.55 ui-monospace, "SF Mono", Menlo, monospace; color: var(--ink); background: var(--bg); border: 1px solid var(--line); border-radius: 10px; padding: 10px; resize: vertical; }}
button.copy {{ font: 700 .95rem var(--font-body); color: #fff; background: var(--accent); border: 0; border-radius: 999px; padding: 10px 18px; cursor: pointer; min-height: 44px; }}
:root[data-theme="dark"] button.copy, :root:not([data-theme="light"]) button.copy {{ color: #10151f; }}
button.copy.done {{ background: var(--signal); color: #2a2109; }}
button:focus-visible, textarea:focus-visible {{ outline: 3px solid var(--signal); outline-offset: 2px; }}
ol {{ margin: 0; padding-left: 1.3em; display: grid; gap: 6px; }}
.gallery {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(160px, 1fr)); gap: 14px; }}
.big {{ margin: 0; display: grid; gap: 6px; font-size: .85rem; color: var(--muted); }}
.big b {{ color: var(--ink); }}
.big img {{ width: 100%; max-width: 100%; aspect-ratio: 3 / 4; object-fit: contain; background: #fff; border: 1px solid var(--line); border-radius: 12px; }}
.note {{ font-size: .9rem; color: var(--muted); margin: 0; }}
code {{ font-size: .9em; background: var(--bg); padding: 1px 5px; border-radius: 5px; }}
@media (prefers-reduced-motion: reduce) {{ * {{ transition: none !important; }} }}
</style>
</head>
<body>
<main>
  <header>
    <h1>破れたお札、半分でも使える？<br>Google Flow 素材</h1>
    <p class="lead">ネコ先生の縦型ショート（8秒 × 4本 ＝ 32秒）を Flow で作るための、プロンプトと参考画像です。声は VOICEVOX のナレーションを後から重ねるので、動画ではネコ先生は話しません。</p>
  </header>

  <section class="box" aria-labelledby="set">
    <h3 id="set">Flow の設定（4本とも同じ）</h3>
    <dl class="settings">
      <dt>作り方</dt><dd>Ingredients to Video（材料から動画）</dd>
      <dt>画面</dt><dd>9:16（縦）</dd>
      <dt>モデル</dt><dd>Veo 3.1（試すときは Fast、本番は Quality）</dd>
      <dt>長さ</dt><dd>8秒</dd>
      <dt>画像</dt><dd>ネコ先生 ＋ そのクリップのお札の 2 枚</dd>
    </dl>
    <ol>
      <li>下の画像を長押しして「写真に保存」し、Flow の Ingredients に追加する</li>
      <li>クリップごとに「プロンプトをコピー」を押し、Flow の入力欄に貼って生成する</li>
      <li>1本につき 2〜3 回作り、顔・服・お札の形がいちばん崩れていないものを選ぶ</li>
      <li>ネコ先生の口が動いてしまったものは作り直す（声と口がずれるため）</li>
    </ol>
  </section>

  {''.join(cards)}

  <section class="box" aria-labelledby="img">
    <h3 id="img">参考画像（長押しで保存）</h3>
    <div class="gallery">{gallery}</div>
    <p class="note">お札は本物そっくりにならないよう、文字・数字・肖像のないアニメ風のデザインにしています。金額は字幕やテロップで見せます。</p>
  </section>

  <section class="box" aria-labelledby="fin">
    <h3 id="fin">できた4本の仕上げ</h3>
    <ol>
      <li>CapCut などの編集アプリで、4本を順番に並べる（合計32秒）</li>
      <li>クリップの効果音は小さめに下げる</li>
      <li>ナレーション <code>narration_32s.wav</code> を 0 秒の位置に置く（これだけで各クリップと合う）</li>
      <li>字幕 <code>subtitles.srt</code> を読み込む。クリップ2・3は画面の左側を空けてあるので、面積の図（2/3・1/2）を置く</li>
      <li>最後にまとめ（2/3以上→全額、2/5以上→半額、2/5未満→0円）を入れる。VOICEVOX の声を使う場合は「VOICEVOX:雀松朱司」のクレジットも入れる</li>
    </ol>
    <p class="note">ナレーションは2種類あります。どちらも <code>narration_32s.wav</code> と <code>subtitles.srt</code> の組で、GitHub のブランチ <code>claude/money-2d-animation-jp-lmjix7</code> の <code>money-anime/flow-torn-banknote/</code> の中にあります。</p>
    <ul class="note">
      <li><code>voice/</code>：VOICEVOX（雀松朱司）の声。クレジット「VOICEVOX:雀松朱司」が必要</li>
      <li><code>api/out/</code>：Google の Gemini TTS で作った声。VOICEVOX のクレジットは不要</li>
    </ul>
  </section>
</main>
<script>
document.querySelectorAll("button.copy").forEach(function (btn) {{
  btn.addEventListener("click", function () {{
    var ta = document.getElementById(btn.dataset.target);
    function ok() {{
      btn.textContent = "コピーしました";
      btn.classList.add("done");
      setTimeout(function () {{ btn.textContent = "プロンプトをコピー"; btn.classList.remove("done"); }}, 2200);
    }}
    function fallback() {{
      ta.focus(); ta.select(); ta.setSelectionRange(0, ta.value.length);
      var done = false;
      try {{ done = document.execCommand("copy"); }} catch (e) {{}}
      if (done) ok(); else btn.textContent = "選択しました。長押しでコピーしてください";
    }}
    if (navigator.clipboard && navigator.clipboard.writeText) {{
      navigator.clipboard.writeText(ta.value).then(ok, fallback);
    }} else {{ fallback(); }}
  }});
}});
</script>
</body>
</html>
"""
open(os.path.join(HERE, "flow_kit.html"), "w", encoding="utf-8").write(page)
print("flow_kit.html", len(page) // 1024, "KB")
