# AI Studio 用プロンプト（無料で動画を作る）

AI Studio の動画生成の画面に、下のプロンプトを**1クリップずつそのまま貼り付けて**生成します（共通部分も入れてあります）。

1. 画面の向きを **9:16（縦）**、長さを **8秒** にする（選べる場合）
2. 画像を添付できる場合は、`neko_sensei.jpg`（このフォルダにあるネコ先生の画像）を添付する
3. 下のクリップ1〜4のプロンプトをそれぞれ貼って生成し、mp4 をダウンロードする
4. ダウンロードした4本を GitHub のこのブランチの `money-anime/flow-torn-banknote/api/out/` にアップロードし、どれが何番か Claude に伝える（名前を付け直して仕上げます）

1日に作れる本数が限られている（5本くらい）ので、4本作って、残りの1回は一番気に入らないクリップの作り直しに使うのがおすすめです。

## クリップ1（0〜8秒：つかみ）

```
Vertical 9:16 video, 8 seconds. 2D Japanese anime style with clean line art and soft cel shading, warm cream-colored tones, soft daylight, the feel of a friendly educational TV short.

Main character: "Neko-sensei", the gray cat from the reference image. An anthropomorphic gray cat standing upright, green eyes, thin round gold-rimmed glasses, white long-sleeved shirt, navy blue knit vest, mustard-yellow bow tie, a small magnifying glass in the vest's chest pocket, dark gray trousers, brown leather shoes, long gray tail. Keep his face, outfit and colors exactly the same as the reference image.

Important: Neko-sensei does NOT speak. His mouth stays closed the whole time; he communicates only with gestures and facial expressions (a voice-over will be added later). No dialogue, no voices, no narration.

Props: banknotes are simplified cartoon banknotes (pale greenish-beige paper with a simple border and an oval watermark area, no real currency details, no readable text or numbers).

No subtitles, no captions, no on-screen text, no background music. Only soft, subtle sound effects.

Scene: a cozy study with a bookshelf and a wooden desk, softly blurred in the background.
Shot: medium close-up, slow push-in toward Neko-sensei.
Action: Neko-sensei holds up the left half of a banknote that is torn cleanly down the middle, showing it to the camera with one paw, tilting his head with a curious, playful look (mouth closed). Then he takes the small magnifying glass out of his vest's chest pocket, examines the torn banknote, looks back at the camera and gives a confident nod.
Sound: a soft paper rustle, a light tap when he picks up the magnifying glass.

Avoid: talking, speaking, open mouth, lip movement, dialogue, voice, narration, music, text, letters, numbers, captions, subtitles, watermark, logo, realistic currency, photorealistic, 3D render, extra limbs, deformed paws, different character design.
```

## クリップ2（8〜16秒：3分の2以上 → 全額）

```
Vertical 9:16 video, 8 seconds. 2D Japanese anime style with clean line art and soft cel shading, warm cream-colored tones, soft daylight, the feel of a friendly educational TV short.

Main character: "Neko-sensei", the gray cat from the reference image. An anthropomorphic gray cat standing upright, green eyes, thin round gold-rimmed glasses, white long-sleeved shirt, navy blue knit vest, mustard-yellow bow tie, a small magnifying glass in the vest's chest pocket, dark gray trousers, brown leather shoes, long gray tail. Keep his face, outfit and colors exactly the same as the reference image.

Important: Neko-sensei does NOT speak. His mouth stays closed the whole time; he communicates only with gestures and facial expressions (a voice-over will be added later). No dialogue, no voices, no narration.

Props: banknotes are simplified cartoon banknotes (pale greenish-beige paper with a simple border and an oval watermark area, no real currency details, no readable text or numbers).

No subtitles, no captions, no on-screen text, no background music. Only soft, subtle sound effects.

Scene: Neko-sensei stands next to a large blank whiteboard with nothing written on it, in the same cozy study. Leave some empty space on the left side of the frame.
Shot: medium shot, static camera.
Action: he holds up a banknote that is almost complete, with only one small corner torn off. He smiles warmly with his mouth closed and nods approvingly, and a few small cartoon sparkles appear around the banknote.
Sound: a bright, short sparkle chime.

Avoid: talking, speaking, open mouth, lip movement, dialogue, voice, narration, music, text, letters, numbers, captions, subtitles, watermark, logo, realistic currency, photorealistic, 3D render, extra limbs, deformed paws, different character design.
```

## クリップ3（16〜24秒：5分の2以上 → 半額）

```
Vertical 9:16 video, 8 seconds. 2D Japanese anime style with clean line art and soft cel shading, warm cream-colored tones, soft daylight, the feel of a friendly educational TV short.

Main character: "Neko-sensei", the gray cat from the reference image. An anthropomorphic gray cat standing upright, green eyes, thin round gold-rimmed glasses, white long-sleeved shirt, navy blue knit vest, mustard-yellow bow tie, a small magnifying glass in the vest's chest pocket, dark gray trousers, brown leather shoes, long gray tail. Keep his face, outfit and colors exactly the same as the reference image.

Important: Neko-sensei does NOT speak. His mouth stays closed the whole time; he communicates only with gestures and facial expressions (a voice-over will be added later). No dialogue, no voices, no narration.

Props: banknotes are simplified cartoon banknotes (pale greenish-beige paper with a simple border and an oval watermark area, no real currency details, no readable text or numbers).

No subtitles, no captions, no on-screen text, no background music. Only soft, subtle sound effects.

Scene: next to the same blank whiteboard in the cozy study. Leave some empty space on the left side of the frame.
Shot: medium close-up, gentle push-in.
Action: he holds up exactly one half of a banknote torn cleanly down the middle, then points at it with his other paw like a kind teacher, nodding slowly with his mouth closed.
Sound: a soft paper rustle.

Avoid: talking, speaking, open mouth, lip movement, dialogue, voice, narration, music, text, letters, numbers, captions, subtitles, watermark, logo, realistic currency, photorealistic, 3D render, extra limbs, deformed paws, different character design.
```

## クリップ4（24〜32秒：5分の2未満 → 交換できない）

```
Vertical 9:16 video, 8 seconds. 2D Japanese anime style with clean line art and soft cel shading, warm cream-colored tones, soft daylight, the feel of a friendly educational TV short.

Main character: "Neko-sensei", the gray cat from the reference image. An anthropomorphic gray cat standing upright, green eyes, thin round gold-rimmed glasses, white long-sleeved shirt, navy blue knit vest, mustard-yellow bow tie, a small magnifying glass in the vest's chest pocket, dark gray trousers, brown leather shoes, long gray tail. Keep his face, outfit and colors exactly the same as the reference image.

Important: Neko-sensei does NOT speak. His mouth stays closed the whole time; he communicates only with gestures and facial expressions (a voice-over will be added later). No dialogue, no voices, no narration.

Props: banknotes are simplified cartoon banknotes (pale greenish-beige paper with a simple border and an oval watermark area, no real currency details, no readable text or numbers).

No subtitles, no captions, no on-screen text, no background music. Only soft, subtle sound effects.

Scene: the same cozy study, near a bright window.
Shot: close-up on his raised paw, then tilt up to a medium shot of Neko-sensei.
Action: a tiny scrap of a banknote rests on his paw pad. A gentle breeze lifts the scrap and it flutters away out of frame; his ears droop slightly in disappointment. Then he picks up a small envelope holding torn banknote pieces, looks at the camera with a gentle closed-mouth smile, and gives a small polite bow.
Sound: a light whoosh of wind, a soft paper sound.

Avoid: talking, speaking, open mouth, lip movement, dialogue, voice, narration, music, text, letters, numbers, captions, subtitles, watermark, logo, realistic currency, photorealistic, 3D render, extra limbs, deformed paws, different character design.
```
