# ユイとネコ先生 〜大学生のためのお金と72の法則〜（約46秒）

`money-72-shorts.mp4` … ショート動画用の縦型2Dアニメ（1080×1920 / 30fps / 日本語音声・字幕・BGM・効果音つき）

## 内容
大学生のユイが、バイト代10万円を銀行に預けようとしたところから、ネコ先生と次のことを会話で学ぶストーリーです。
- **インフレ**：物価が年2%上がると、72÷2＝約36年でお金の価値は半分
- **複利**：年利5%で運用できれば、72÷5＝約14年でお金は2倍
- **投資の注意**：元本割れのリスクがある → 生活費は残して、少額から・長く・分散
- **新NISA**：運用益が非課税（年間360万円・生涯1,800万円まで）

※ 72の法則は概算です。

## クレジット
- 音声：VOICEVOX:春日部つむぎ（ユイ） / VOICEVOX:青山龍星（ネコ先生）
- ネコ先生：提供されたキャラクター画像（`src/cat_cutout.png`）を切り抜き、頭・胴体・しっぽに分けて動かしています
- ユイ・背景・BGM・効果音：すべてプログラムで自作

## 作り方（すべて無料ツール）
| 役割 | ツール |
|---|---|
| 音声 | [VOICEVOX ENGINE](https://github.com/VOICEVOX/voicevox_engine)（Docker版）。母音のタイミングを口パクに使用 |
| 絵 | Python + Pillow で1コマずつ描画（カメラのズーム・カット、表情、効果背景）。ネコ先生は `src/cat.py` で口パク（元の「ω」の下で口がなめらかに開く）・まばたき・うなずき・しっぽ |
| BGM・効果音 | numpy で合成（`src/sound.py`） |
| 動画 | ffmpeg |

```sh
docker run -d -p 50021:50021 voicevox/voicevox_engine:cpu-latest
cd src
python3 tts.py      # lines.tsv → line*.wav と visemes.json
python3 render.py   # ../money-72-shorts.mp4 を出力（python3 render.py 12.5 で1コマだけ確認）
```
