# Stable Diffusion Forge Random Prompt Generator 🎲

[English](#english) | [日本語](#japanese)

---

<a name="english"></a>
## 🇬🇧 English

A simple yet powerful extension for **Stable Diffusion Forge** that generates infinite prompt variations with a single click. It allows you to randomize situations, poses, outfits, and physical traits while maintaining context logic.

### ✨ Features

- **Context-Aware Mode**: Automatically selects poses that fit the generated situation (e.g., "Sitting at desk" for a classroom setting).
- **Random Chaos Mode**: Ignores context logic for unexpected and creative combinations.
- **Clothing Modes**:
  - **Full Set**: Picks a coordinated outfit (e.g., School Uniform, Suit).
  - **Mix & Match**: Randomly combines Tops, Bottoms, and Underwear separately. Great for creating unique or mismatched styles.
- **SFW / NSFW Toggle**: 
  - Switching to NSFW enables risky outfits and situations.
  - In "Mix & Match" mode, it enables options like **Topless, Bottomless, or No Panties**.
- **Quality Tags**: Automatically adds high-quality tags (e.g., `masterpiece, best quality`) to the prompt.
- **Customizable**: You can easily add your own favorite tags and situations by editing a JSON file.

### 📥 Installation

1. Open **Stable Diffusion Forge**.
2. Go to the **Extensions** tab -> **Install from URL**.
3. Paste the URL of this repository.
4. Click **Install**.
5. Go to the **Installed** tab and click **Apply and restart UI**.

### 🛠 Customization (How to add tags)

You can add your own favorite hairstyles, clothes, or situations without coding.

1. Open the extension folder:  
   `stable-diffusion-webui-forge/extensions/sd-forge-random-generator/data/`
2. Open **`tags.json`** with a text editor (Notepad, VS Code, etc.).
3. Add your tags to the lists.
   - **Note**: Ensure strictly valid JSON format. Don't forget the comma `,` between items!

---

<a name="japanese"></a>
## 🇯🇵 日本語

**Stable Diffusion Forge** 用のランダムプロンプト生成拡張機能です。
シチュエーション、服装、表情、ポーズなどをワンクリックで組み合わせ、無限のバリエーションを作成します。

### ✨ 主な機能

- **Context-Aware (状況に合わせる) モード**: シチュエーションに矛盾しないポーズを自動選択します（例：教室なら「机に座る」、ビーチなら「寝そべる」など）。
- **Random Chaos (完全ランダム) モード**: 文脈を無視してポーズを選ぶため、意外性のある構図が生まれます。
- **服装モード**:
  - **Full Set (全身セット)**: 制服やスーツなど、決まったセットアップから選択します。
  - **Mix & Match (パーツ別ランダム)**: **トップス・ボトムス・下着**を個別に抽選して組み合わせます。ちぐはぐな服装や着崩し表現に最適です。
- **SFW / NSFW 切り替え**:
  - NSFWを有効にすると、きわどいシチュエーションや服装が抽選リストに含まれます。
  - 「Mix & Match」モード時に有効にすると、**トップレス、ボトムレス、ノーパン**などが抽選されるようになります。
- **Quality Tags**: `masterpiece, best quality` などの定番高品質タグを自動付与します。
- **カスタマイズ可能**: データはJSONファイルで管理されているため、自分の好きなタグやシチュエーションを自由に追加できます。

### 📥 インストール方法

1. **Stable Diffusion Forge** を起動します。
2. **Extensions** タブを開き、**Install from URL** を選択します。
3. このリポジトリのURLを貼り付けます。
4. **Install** ボタンを押します。
5. **Installed** タブに移動し、**Apply and restart UI** をクリックして再起動します。

### 🛠 カスタマイズ方法（タグの追加）

自分の好きな髪型、服装、シチュエーションを追加したい場合は、以下のファイルを編集してください。

1. 以下のフォルダを開きます：
   `stable-diffusion-webui-forge/extensions/sd-forge-random-generator/data/`
2. **`tags.json`** をテキストエディタ（メモ帳など）で開きます。
3. リストの中に好きなタグを追加してください。
   - **注意**: カンマ `,` の付け忘れなど、JSONの記法ミスにご注意ください。

## License
MIT License
