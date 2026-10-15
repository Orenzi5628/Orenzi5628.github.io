# 会話ログ：お金の2Dアニメ制作（ユイとネコ先生）

このファイルは、Claude Code との会話（2026年10月14日〜15日、時刻は日本時間）の記録です。依頼の文と Claude の返答を時間順に載せています。作業中に実行したコマンドとその出力は省いています（作ったものはリポジトリのコミット履歴に残っています）。

## 成果物のまとめ

| 項目 | 内容 |
|---|---|
| 最終の動画 | `money-anime/money-72-shorts.mp4`（縦 1080×1920・30fps・約46秒） |
| タイトル | ユイとネコ先生 〜大学生のためのお金と72の法則〜 |
| 声 | VOICEVOX:春日部つむぎ（ユイ） / VOICEVOX:青山龍星・しっとり（ネコ先生） |
| 絵 | Python + Pillow で描画。ネコ先生は提供画像を切り抜いて動かしている |
| BGM・効果音 | numpy で合成（自作） |
| 費用 | 0円（すべて無料ツール） |
| ブランチ | `claude/money-2d-animation-jp-lmjix7` |

### 最終版の台本

| # | 話す人 | セリフ |
|---|---|---|
| 1 | ユイ | バイト代の十万円、銀行に預けておけば、ずっと安心だよね！ |
| 2 | ネコ先生 | 預金の金利は、とても低いんだ。もし物価が毎年２パーセント上がると、七十二割る二で、約三十六年後。お金の価値は、半分になってしまう。 |
| 3 | ユイ | えっ！預けてるだけじゃ、減っちゃうの！？ |
| 4 | ネコ先生 | そこで、複利だ。年利５パーセントで運用できれば、七十二割る五で、約十四年で二倍。利息にも、利息がつくんだよ。 |
| 5 | ユイ | じゃあ、全部つぎ込んじゃおう！ |
| 6 | ネコ先生 | 待ちたまえ。投資には、元本割れもある。生活費は残して、少額から、長く、分散。新ニーサなら、利益に税金がかからない。 |
| 7 | ユイ | 時間を味方に、コツコツだね！ |

### 調べたお金の知識と出典

- **72の法則**：72 ÷ 金利(%) ≒ お金が2倍になる年数。インフレ率で割ると、お金の価値が半分になる年数の目安になる（概算）
- **新NISA**：つみたて投資枠 年120万円＋成長投資枠 年240万円（合計 年360万円）、生涯の非課税保有限度額 1,800万円
- 出典：[野村證券「72の法則」](https://www.nomura.co.jp/fin-wing/column/rule-of-72/) / [ファイナンシャルフィールド「72の法則って何?」](https://financial-field.com/assets/entry-73018) / [東海東京証券 用語集](https://www.tokaitokyo.co.jp/kantan/term/detail_2176.html) / [時事通信「NISA、年360万円まで 生涯投資枠1800万円」](https://sp.m.jiji.com/english/show/23635)
- 注意：金融庁の公式ページは検索結果に出てこなかったため、上記は民間サイト・報道の情報です

### 版の移り変わり

1. **初版**：Open JTalk の音声、1280×720、ユイとフクロウ先生、お年玉1万円の話（約42秒）
2. **高画質版**：VOICEVOX の声、1920×1080・30fps、カメラワーク・効果・BGM・効果音を追加（約45秒）
3. **ネコ先生版**：提供画像のネコを先生役に、ユイを大学生に、バイト代10万円と銀行預金の話に変更（約46秒）
4. **ショート版（最終）**：縦 1080×1920 に組み直し、ネコ先生の口パクをなめらかに修正（約46秒）

---

## 会話の記録

### 1. 依頼（2026-10-14 21:59）

> お金に関する知識を調べて、その調べた知識で２Dアニメーションを作ってください。
> 長さは４０秒ほどで連続性のあるストーリー、対話、日本語の音声を含めて下さい。
> 必要なツールはインストールして使用してください。ただしお金はかけずに作ってください

<details><summary>作業中のメモ（7件）</summary>

- Install Open JTalk (free Japanese TTS) and research in parallel.
- Research done (72の法則, インフレ, 複利, NISA). Now generating the voice lines.
- Audio is ready (~41s of speech). Now the frame renderer with lip-sync driven by the audio volume.
- Looks good. Fixes: the board overlaps Yui's head, "≒" is missing from the font, and it's ~46s, so I'll speed up the voice slightly to get closer to 40s.
- Good — 41.6s now. One small tweak (move the formula off the curve), then the full render.
- Let me check frames pulled from the final MP4, and the audio levels.
- All looks right. I'll add a short README, then commit and push.

</details>

**Claude の返答**

お金の2Dアニメ「ユイとフクロウ先生 〜お金と72の法則〜」ができました（`money-anime/money-72.mp4`、約42秒、1280×720、日本語の音声と字幕つき）。ブランチ `claude/money-2d-animation-jp-lmjix7` にプッシュ済みです。使ったツールはすべて無料です。

**ストーリー**
お年玉の1万円を貯金箱にしまって安心しているユイに、フクロウ先生が次のことを教えます。

1. **インフレ**：物価が年2%上がると、72÷2＝約36年でお金の価値は半分になる。画面ではお札が縮み、アイスの値段が上がっていきます。
2. ユイ「えっ！お金が、減っちゃうの！？」
3. **複利**：年5%で増やせれば、72÷5＝約14年で2倍になる。1万円が2万円になるまでのグラフを描きます。
4. ユイ「じゃあ、全部投資しちゃおう！」
5. 先生「待った！」：投資には元本割れもあるので、「少しずつ・長く・分散」が大事。NISAなら利益に税金がかからない。
6. 「時間を味方に、コツコツだね！」のあと、朝日とコインの木が出て、まとめ画面で終わります。

**使ったツール**
- **音声**：Open JTalk。声のデータが1種類しかないため、ユイは同じ声の高さを上げて先生と別の声に聞こえるようにしています。
- **絵**：Python と Pillow で1コマずつ描きました。口の動きは音声の大きさに合わせてあり、まばたきもします。
- **動画**：ffmpeg でまとめました。

**確認したこと**
- 最終の動画から主要な場面のコマを取り出して見て、絵・字幕・数字が正しく表示されることを確かめました。
- 音声は音量を測って正しく入っていることを確認しましたが、私は耳で聞けません。読み方やイントネーションが不自然な所がないか、一度聞いてみてください。気になる箇所があれば、セリフの表記を変えて作り直せます。

**数字の出典**
72の法則（72÷金利でお金が2倍になる年数の目安。インフレ率で割ると価値が半分になる年数）と、NISAの枠（年間360万円・生涯1,800万円）を調べました。参考にしたのは民間のサイトや報道で、金融庁の公式ページは今回の検索結果に出てきませんでした。動画の最後に「数値は概算です」「元本割れのリスクがあります」と入れています。
- [野村證券「72の法則」](https://www.nomura.co.jp/fin-wing/column/rule-of-72/)
- [ファイナンシャルフィールド「72の法則って何?」](https://financial-field.com/assets/entry-73018)
- [東海東京証券 用語集](https://www.tokaitokyo.co.jp/kantan/term/detail_2176.html)
- [時事通信「NISA、年360万円まで 生涯投資枠1800万円」](https://sp.m.jiji.com/english/show/23635)

作り直すときは `money-anime/src/lines.tsv` のセリフを変え、`money-anime/README.md` の手順で音声を作り直してから `render.py` を実行します。

### 2. 依頼（2026-10-14 23:18）

> もう少しクオリティをあげることは可能ですか？
> また、声も自然ではないので直してください

<details><summary>作業中のメモ（15件）</summary>

- Let me first check what changed in render.py, and whether VOICEVOX (a free, natural Japanese TTS) can be downloaded.
- GitHub releases and HuggingFace are blocked by this environment's network policy. Let me check which other free TTS sources are reachable.
- Git access to GitHub works (only release downloads are blocked). Let me see whether VOICEVOX model files are in the repo itself.
- Those are only tiny test models. Let me check other VOICEVOX repos and similar projects for the real voice models.
- The `VOICEVOX/voicevox_vvm` repo has the real voice models in its git tree. They need VOICEVOX's runtime to play them, so let me check whether that runtime can be fetched too.
- Docker is installed and Docker Hub is reachable. The official VOICEVOX engine image bundles everything, so I'll use that.
- While the pull runs, I'll write the BGM and sound-effect synthesizer.
- Owl lines run long, so I'll speed them up. Let me also check the readings VOICEVOX chose, so nothing is misread.
- Readings are correct except 「年５パーセント」 (read as トシ), so I'll change it to 「年利５パーセント」.
- Voices are done (~38s of speech). Now the new renderer: 1080p/30fps, camera work, detailed characters, vowel-based lip-sync, effects, BGM and SFX.
- Previews look good. One last framing tweak: in the close-ups, Yui moves left so the captions don't overlap her arms. Then I'll run the full render.
- Rendered (45s, 1080p/30fps). Checking frames from the final file and the audio mix levels.
- The frames look right. The BGM is only ~7.5 dB under the voices, so I'll lower it during dialogue and remux just the audio track.
- Now updating the README (including the VOICEVOX credits) and pushing.
- 改良版ができました。同じブランチ `claude/money-2d-animation-jp-lmjix7` にプッシュ済みです。今回もお金は一切かかっていません。  ## 声 - 声を無料の音声合成ソフト **VOICEVOX** に変えました。前の Open JTalk よりずっと自然な声です。 - ユイは「春日部つむぎ」、フクロウ先生はおじいさん声の「ちび式じい」です。 - 驚く場面とはしゃぐ場面では、抑揚と声の高さを少し強めています。 - 読み方を一行ずつ確認し、「年5パーセント」が「とし」と読まれていたので「年利5パーセント」に直しました。 - この環境では GitHub の配布ページからはダウンロードできなかったので、公式の Docker 版を使いました。  ## 映像 - 解像度を 1280×720・24fps から **1920×1080・30fps** に上げました。 - **カメラワーク**：   - 説明の場面ではボードに寄ります。   - ユイが驚く・はしゃぐ場面と、先生の「待った！」は顔のアップに切り替わり、画面も揺れます。   - 最後はユイを中心に丸く閉じていく演出で、まとめ画面に移ります。 - **キャラクター**：   - ユイはセーラー服で、瞳にハイライト、コインの髪飾り、揺れるアホ毛を付けました。   - フクロウ先生は博士帽とメガネを付け、翼でボードを指したり「待った！」をしたりします。 - **口の動き**：VOICEVOX の音のタイミングを使い、「あいうえお」ごとに口の形が変わります。 - **演出**：   - 「ガーン！」には青い縦線、「ぜんぶ投資！？」には黄色い集中線、「待った！」には赤い衝撃線の背景を付けました。   - 冒頭ではコインが降ります。   - 最後は窓の外で朝日が昇り、ボードではコインの木が育ちます。 - **図解**：   - インフレの場面では、1万円の価値メーターが減り、アイスの値段が上がっていきます。   - 複利の場面では、元本と増えた分を色分けした棒グラフを使いました。   - 投資のコツは3枚のカード（少しずつ・長く・分散）と、NISA の非課税バッジで見せます。  ## 音 - **BGM と効果音**（チャリン、ガーン、キラキラなど）はプログラムで作りました。素材の権利の心配はありません。 - BGM はセリフの間だけ小さくして、声が聞き取りやすいようにしています。  ## 確認したことと注意点 - 完成した動画から場面ごとのコマを取り出し、絵の崩れや文字の重なりがないことを目で確認しました。 - 音量も測って確認しましたが、私は音を耳で聞けません。声の自然さや BGM とのバランスは、実際に聞いて判断してください。 - 長さは約45秒で、前回の約42秒より少し長くなりました。先生の声は聞き取りやすさを優先して、速くしすぎないようにしています。もっと40秒に近づけたい場合は、話す速さかセリフを調整できます。 - VOICEVOX は無料ですが、声の作者を表示する決まりがあるため、動画の最後と README に「VOICEVOX:春日部つむぎ / VOICEVOX:ちび式じい」と入れています。  ファイルは `money-anime/money-72.mp4` です。

</details>

**Claude の返答**

補足です。VOICEVOX の音声モデルを探すために動かしていた古い確認作業が、いま終わりました。その結果はもう使っていないので、動画にも、プッシュ済みの内容にも影響はありません。

### 3. 依頼（2026-10-14 23:41）

> （画像を添付：メガネと蝶ネクタイ、紺のベストを着たネコのキャラクター。切り抜いたものが `src/cat_cutout.png`）
>
> キャラクターをこの写真のキャラクターにできますか？また内容を大学生でも理解できるような簡単な内容にしてください

<details><summary>作業中のメモ（9件）</summary>

- The cutout is clean. Next I'll write the cat's animation: head nods, tail sway, blinking, mouth shapes and a glint on the glasses. I'll test the face overlays up close.
- Close. Just switching the downscale to a box filter to remove the faint halo, and toning down the blink rims.
- The blink still shows doubled glasses rims, because my redrawn rims don't line up exactly with the originals. I'll keep the original rim pixels instead of redrawing them, and soften the patch edge.
- Starting VOICEVOX again and generating the new script.
- Readings are all correct. Generating the audio: 春日部つむぎ for Yui, and 青山龍星 (しっとり style) for the cat, a calm, intellectual voice that suits him.
- Audio is ready (~39s of dialogue). Now updating the renderer.
- Now the board graphics: a bank instead of the piggy bank, ¥100,000 amounts, and the 「生活費は残す」 note.
- These look good: the 「待ちたまえ！」 close-up with the glasses glint works well. Running the full render now.
- Everything checks out. Updating the README and pushing.

</details>

**Claude の返答**

先生役を、写真のネコのキャラクターに替えた新しい版ができました。話も大学生向けに変えています。動画は `money-anime/money-72.mp4`（約46秒）で、ブランチにプッシュ済みです。

## キャラクター
- ネコは先生役にしました。前のフクロウ先生と入れ替えています。ユイは生徒役のまま、服を大学生らしいカーディガンとジーンズに変えました。逆の配役にしたい場合は言ってください。
- ネコ先生は、いただいた画像をそのまま切り抜いて動かしています。描き直していないので、見た目は元の絵と同じです。
- 頭・胴体・しっぽを別々に動かし、次の動きを付けました。
  - 歩いて登場する
  - 話すときにうなずき、説明中はボードの方へ体を傾ける
  - 「あいうえお」に合わせて口が動く
  - まばたき（メガネのフチは元の絵のまま残しています）
  - しっぽがゆらゆら揺れる
  - 「待ちたまえ」の場面で、キリッとした眉になりメガネが光る
- 腕は1枚の絵の一部なので動きません。
- ネコ先生の声は、落ち着いた男性の声（VOICEVOX:青山龍星）にしました。

## 大学生向けの内容
大学生のユイが、バイト代10万円を銀行に預けようとする話にしました。

1. 預金の金利はとても低い。物価が年2%上がると、72÷2で約36年後にはお金の価値が半分になる。
2. 年利5%で運用できれば、72÷5で約14年で2倍になる。利息にも利息がつく（複利）。
3. 「全部つぎ込もう！」と言うユイを、ネコ先生が「待ちたまえ」と止める。
   - 投資には元本割れもある。
   - 生活費は残して、少額から、長く、分散して。
   - 新NISAなら利益に税金がかからない。
4. 「時間を味方に、コツコツだね！」で終わります。

セリフの読み方は全部確認し、誤読はありませんでした。

## 確認したことと注意点
- 完成した動画からいくつかの場面を取り出し、絵の崩れや文字の重なりがないことを確認しました。
- 声の自然さは、私は耳で聞けないので、実際に聞いて確かめてください。気になるところがあれば直します。
- 長さは約46秒で、ご希望の40秒より少し長めです。短くしたい場合は、セリフを削るか話す速さを上げられます。
- 切り抜いたネコの画像（`src/cat_cutout.png`）もリポジトリに入れました。この GitHub Pages のリポジトリが公開設定なら、誰でも見られる状態です。公開したくない場合は言ってください。外す方法を相談しましょう。

### 4. 依頼（2026-10-15 12:40）

> ねこの口の動きがすこし違和感があるのと、ショート動画用に縦にしてください

<details><summary>作業中のメモ（11件）</summary>

- Two changes: smoother cat mouth movement, and a vertical (9:16) re-layout for Shorts. First, the current mouth code:
- First the cat mouth: a continuous mouth-open level computed from the vowel timing, in place of the per-vowel shape switch.
- The mouth now opens smoothly, but the inside pokes up above the ω line and leaves a light fringe. I'll clip it so it only shows below the ω curve.
- Much more natural now. A faint light seam remains along the top edge, so I'll close that gap by one pixel.
- Next the vertical layout. Reading the parts of the renderer that need restructuring:
- Now I'll rewrite the screen-dependent parts for a 1080×1920 vertical frame. Board panels and characters keep their drawing code and are placed with a translation transform.
- The vertical layout works. The characters are a little small for a phone screen, so I'll scale them up (Yui ×1.12, cat a bit taller) and adjust the close-up cameras to match.
- The cat's ears cover the end of the 「72 ÷ 2 ＝ 36年」 label. I'll move the cat a little to the right and the board slightly up.
- The cat no longer covers the formula. Running the full vertical render now (about 5 minutes).
- Rendered (1080×1920, 46s). Checking frames from the final file, including close-ups of the cat mid-sentence:
- My crop missed the mouth. Retrying with the right region:

</details>

**Claude の返答**

ショート動画用の縦型版（1080×1920、約46秒）ができ、ネコ先生の口の動きも直しました。動画は `money-anime/money-72-shorts.mp4` で、ブランチにプッシュ済みです。

## ネコ先生の口の動き
- **前の問題点：** 音ごとに口の形をパッと切り替え、そのたびに元の「ω」の口を消して別の絵に描き替えていました。そのためパクパクと点滅するように見え、絵柄も変わっていました。
- **直した内容：**
  - 元の絵の「ω」の線はそのまま残し、その下だけで口が開くようにしました。
  - 開き具合は、声に合わせてなめらかに大きくなったり小さくなったりします。
  - 「い・え」は横に広く、「お・う」はすぼめた形です。
  - ささやくように弱く発音される音では、口を小さめにしています。
- 完成した動画から話している場面を何コマか取り出して見て、絵から浮かずに口が開いていることを確認しました。

## 縦型レイアウト
- **上：** 「大学生のお金入門｜72の法則」の見出しと説明のボード。
- **下：** ユイとネコ先生。ネコ先生がボードの文字に重ならない位置に置いています。
- **字幕：** 縦画面に合わせて、1行18文字ほどで折り返します。
- **YouTube ショートなどのボタンとの重なり：** 字幕は画面のいちばん下を避けて置き、ネコ先生も右端に寄りすぎないようにしました。
- **場面の演出：** 驚く・はしゃぐ・「待ちたまえ！」のアップ、タイトル、まとめ画面も縦向けに作り直しています。

## 注意点
- 横長版（`money-72.mp4`）は、口の動きが古いままだったのでリポジトリから外し、縦型版に置き換えました。過去の記録には残っています。横長版も必要なら、新しい口の動きで作り直します。
- 長さは約46秒です。今のショート動画の長さ制限には収まります。
- 声の自然さは、私は耳で聞けないので、実際に聞いて確かめてください。

### 5. 依頼（2026-10-15 23:05）

> この会話のデータと内容をファイルにできますか？

**Claude の返答**

The session transcript is saved locally. I'll convert it into a readable Markdown conversation log with only your messages and my replies; tool commands and system messages are left out.
