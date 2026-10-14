# ユイとフクロウ先生 〜お金と72の法則〜（約42秒）

`money-72.mp4` … 2Dアニメ（1280×720 / 24fps / 日本語音声・字幕つき）

## 内容
貯金箱に入れたお年玉を例に、次のことを会話で学ぶストーリーです。
- **インフレ**：物価が年2%上がると、72÷2＝約36年でお金の価値は半分
- **複利**：年5%で運用できれば、72÷5＝約14年でお金は2倍
- **投資の注意**：元本割れのリスクがある → 少しずつ・長く・分散して
- **NISA**：運用益が非課税（年間360万円・生涯1,800万円まで）

※ 72の法則は概算です。

## 作り方（すべて無料ツール）
- 音声：Open JTalk（`open-jtalk`、`hts-voice-nitech-jp-atr503-m001`）。ユイは声の高さを上げて別の声にしています
- 絵：Python + Pillow で1コマずつ描画。口パクは音声の大きさに合わせて動きます
- 動画：ffmpeg

```sh
sudo apt-get install open-jtalk open-jtalk-mecab-naist-jdic hts-voice-nitech-jp-atr503-m001 fonts-noto-cjk ffmpeg
cd src && python3 render.py   # ../money-72.mp4 を出力（line*.wav は lines.tsv から Open JTalk で生成）
```
