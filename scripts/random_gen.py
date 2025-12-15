import modules.scripts as scripts
import gradio as gr
from modules import script_callbacks, shared
import json
import random
import os
import traceback
import html
import urllib.parse

# --- User Setting ---
# ここで指定したフォルダを起点に再帰的に検索します
TARGET_LORA_DIR = r"C:\stableDiffusion\stable-diffusion-webui\models\Lora"

# --- JavaScript Logic ---
JS_SCRIPT = """
<script>
    // 1. Text Injection Helper
    function insertTextToPrompt(text) {
        var ta = gradioApp().querySelector('#random_gen_result_box textarea');
        if (!ta) return;
        
        var currentVal = ta.value;
        var sep = currentVal.trim().length > 0 ? ", " : "";
        
        // Reactのstate更新をトリガーするために setter を呼ぶ
        var nativeInputValueSetter = Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, "value").set;
        nativeInputValueSetter.call(ta, currentVal + sep + text);
        
        ta.dispatchEvent(new Event('input', { bubbles: true }));
    }

    // 2. Global Function for LoRA Click
    window.addLoraToGen = function(element) {
        var name = element.getAttribute('data-name');
        var trigger = element.getAttribute('data-trigger');
        
        var text = "<lora:" + name + ":1>";
        if (trigger && trigger !== "None" && trigger !== "") {
            text += ", " + trigger;
        }
        insertTextToPrompt(text);
    }

    // 3. Send Function
    window.sendPromptTo = function(tabName) {
        var src = gradioApp().querySelector('#random_gen_result_box textarea');
        if (!src) return;
        
        var targetId = (tabName === 'txt2img') ? '#txt2img_prompt textarea' : '#img2img_prompt textarea';
        var dest = gradioApp().querySelector(targetId);
        
        if (dest) {
            var nativeInputValueSetter = Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, "value").set;
            nativeInputValueSetter.call(dest, src.value);
            dest.dispatchEvent(new Event('input', { bubbles: true }));
            
            // Tab切り替え
            var tabIndex = (tabName === 'txt2img') ? 1 : 2; 
            var tab = gradioApp().querySelector('#tabs button:nth-child(' + tabIndex + ')'); 
            if (tab) tab.click();
        }
    }
</script>
"""

# --- CSS (Prompt-all-in-one 風スタイル) ---
CSS = """
.lora-tab-container {
    height: 550px;
    overflow-y: auto;
    padding: 10px;
    background: var(--background-fill-secondary);
    border-radius: 8px;
}
.lora-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
    gap: 12px;
}
.lora-card {
    position: relative;
    cursor: pointer;
    border-radius: 8px;
    background: var(--neutral-800);
    border: 1px solid var(--border-color-primary);
    box-shadow: 0 2px 4px rgba(0,0,0,0.2);
    transition: transform 0.1s, border-color 0.1s;
    overflow: visible; /* Popup表示のため */
}
.lora-card:hover {
    transform: translateY(-2px);
    border-color: var(--primary-500);
    z-index: 100;
}
.lora-thumb-wrapper {
    width: 100%;
    aspect-ratio: 2/3;
    overflow: hidden;
    border-radius: 8px 8px 0 0;
    background: #222;
}
.lora-thumb {
    width: 100%;
    height: 100%;
    object-fit: cover;
}
.lora-no-thumb {
    width: 100%;
    height: 100%;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    color: #666;
    text-align: center;
    font-size: 24px;
}
.lora-title {
    padding: 6px;
    font-size: 11px;
    font-weight: bold;
    text-align: center;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    background: var(--neutral-900);
    color: var(--body-text-color);
    border-radius: 0 0 8px 8px;
}

/* --- Hover Popup (PAIO Style) --- */
.lora-popup {
    display: none;
    position: absolute;
    bottom: 100%;
    left: 50%;
    transform: translate(-50%, -10px);
    width: 260px;
    background: rgba(20, 20, 30, 0.98);
    border: 1px solid var(--primary-500);
    border-radius: 8px;
    padding: 10px;
    box-shadow: 0 10px 30px rgba(0,0,0,0.8);
    pointer-events: none;
    z-index: 9999;
}
.lora-card:hover .lora-popup {
    display: block;
}
.popup-img {
    width: 100%;
    max-height: 350px;
    object-fit: contain;
    border-radius: 4px;
    margin-bottom: 8px;
    background: black;
}
.popup-header {
    font-size: 13px;
    font-weight: bold;
    color: var(--primary-300);
    margin-bottom: 6px;
    word-break: break-all;
    border-bottom: 1px solid #444;
    padding-bottom: 4px;
}
.popup-info {
    font-size: 11px;
    color: #ddd;
    line-height: 1.4;
}
.tag-badge {
    display: inline-block;
    background: #333;
    padding: 2px 6px;
    border-radius: 4px;
    margin: 2px;
    font-family: monospace;
    border: 1px solid #555;
    color: #8f8;
}
"""

# --- Paths & Data ---
def get_paths():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return {
        "tags": os.path.join(base_dir, "data", "tags.json"),
        "saved": os.path.join(base_dir, "data", "saved_prompts.json")
    }

def load_data(file_type="tags"):
    paths = get_paths()
    path = paths[file_type]
    if not os.path.exists(path): return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except: return {}

# --- LoRA Scanning & Civitai Helper Logic ---
def get_lora_library():
    root_path = TARGET_LORA_DIR
    if not os.path.exists(root_path):
        # パスが見つからない場合は相対パスを試す
        root_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "models", "Lora"))
        if not os.path.exists(root_path): return None

    # Structure: { "FolderName": [Items...] }
    library = {}

    for root, dirs, files in os.walk(root_path):
        # フォルダ名の決定
        rel_path = os.path.relpath(root, root_path)
        folder_name = "Root" if rel_path == "." else rel_path
        
        lora_list = []
        for file in files:
            if file.endswith(".safetensors"):
                name = os.path.splitext(file)[0]
                full_path = os.path.join(root, file)
                base_name_path = os.path.splitext(full_path)[0] # 拡張子なしのフルパス
                
                # --- 1. Image Preview ---
                # Civitai Helper等は .preview.png, .png, .jpg などを保存する
                preview_file = None
                for ext in [".preview.png", ".png", ".jpg", ".jpeg", ".webp"]:
                    test_path = base_name_path + ext
                    if os.path.exists(test_path):
                        preview_file = test_path
                        break
                
                # Gradio/WebUI用にパスをエンコード (/file=C:/...)
                img_url = None
                if preview_file:
                    # Windowsのバックスラッシュを置換し、URLエンコード
                    safe_path = urllib.parse.quote(preview_file.replace("\\", "/"))
                    # ドライブレターのコロン(:)などは quote でエンコードされるが、
                    # /file= エンドポイントはそれをデコードして読む
                    img_url = f"/file={preview_file}" 

                # --- 2. Civitai Info Parsing ---
                # .civitai.info を優先、なければ .json
                triggers = []
                info_path = base_name_path + ".civitai.info"
                if not os.path.exists(info_path):
                    info_path = base_name_path + ".json"
                
                if os.path.exists(info_path):
                    try:
                        with open(info_path, "r", encoding="utf-8") as f:
                            meta = json.load(f)
                            # Civitai Helper形式 (trainedWords)
                            if "trainedWords" in meta and meta["trainedWords"]:
                                triggers = meta["trainedWords"]
                            # WebUI metadata editor形式 (activation text)
                            elif "activation text" in meta:
                                t = meta["activation text"]
                                if t: triggers = [t]
                            # Prompt-all-in-one形式
                            elif "trigger" in meta:
                                triggers = [meta["trigger"]]
                    except: pass
                
                trigger_text = ", ".join(triggers) if triggers else ""

                lora_list.append({
                    "name": name,
                    "image": img_url,
                    "triggers": triggers,
                    "trigger_text": trigger_text
                })
        
        if lora_list:
            lora_list.sort(key=lambda x: x["name"].lower())
            library[folder_name] = lora_list
            
    # ソートしてRootを先頭に
    sorted_lib = {}
    if "Root" in library: sorted_lib["Root"] = library.pop("Root")
    for k in sorted(library.keys()): sorted_lib[k] = library[k]
        
    return sorted_lib

def make_html_for_loras(lora_list):
    if not lora_list: return "<div style='padding:20px'>No LoRAs found.</div>"
    
    html_out = "<div class='lora-grid'>"
    for lora in lora_list:
        name = html.escape(lora["name"])
        trigger_safe = html.escape(lora["trigger_text"]).replace("'", "\\'")
        
        # Image
        if lora["image"]:
            img_html = f"<img src='{lora['image']}' class='lora-thumb' loading='lazy'>"
            popup_img = f"<img src='{lora['image']}' class='popup-img'>"
        else:
            img_html = f"<div class='lora-no-thumb'>💊</div>"
            popup_img = ""
            
        # Trigger Badges
        trigger_html = ""
        if lora["triggers"]:
            for t in lora["triggers"]:
                trigger_html += f"<span class='tag-badge'>{html.escape(t)}</span>"
        else:
            trigger_html = "<span style='color:#777; font-style:italic;'>No trigger words detected</span>"

        # HTML Assembly
        card = f"""
        <div class='lora-card' onclick="addLoraToGen(this)" data-name="{name}" data-trigger="{trigger_safe}">
            <div class='lora-thumb-wrapper'>
                {img_html}
            </div>
            <div class='lora-title'>{name}</div>
            
            <div class='lora-popup'>
                <div class='popup-header'>{name}</div>
                {popup_img}
                <div class='popup-info'>
                    {trigger_html}
                </div>
            </div>
        </div>
        """
        html_out += card
    
    html_out += "</div>"
    return html_out

# --- Generator Logic ---
def generate_prompt_logic(gen_mode, clothing_mode, is_nsfw, is_extreme, use_quality):
    try:
        data = load_data("tags")
        if not data: return "Error: Data load failed."
        prompts = []
        
        if "appearance" in data:
            app = data["appearance"]
            for k in ["hair_texture", "hair", "eyes", "body"]:
                if k in app: prompts.append(random.choice(app[k]))
            
            if "expressions" in app:
                expr = list(app["expressions"]["sfw"])
                if is_nsfw: expr += app["expressions"]["nsfw"]
                if is_extreme: expr += app["expressions"]["extreme"]
                prompts.append(random.choice(expr))
                
            if clothing_mode == "Full Set (全身セット)":
                clothes = list(app["clothes_sets"]["sfw"])
                if is_nsfw: clothes += app["clothes_sets"]["nsfw"]
                if is_extreme: clothes += app["clothes_sets"]["extreme"]
                prompts.append(random.choice(clothes))
            else:
                seps = app["separates"]
                for p in ["tops", "bottoms", "underwear"]:
                    lst = list(seps[p]["sfw"])
                    if is_nsfw: lst += seps[p]["nsfw"]
                    if is_extreme: lst += seps[p]["extreme"]
                    prompts.append(random.choice(lst))
            if "accessories" in app: prompts.append(random.choice(app["accessories"]))

        allowed = ["sfw"]
        if is_nsfw: allowed.append("nsfw")
        if is_extreme: allowed.append("extreme")
        sits = [s for s in data["situations"] if s.get("nsfw_level", "sfw") in allowed]
        sit = random.choice(sits) if sits else {"tags":"", "poses":["standing"]}
        prompts.append(sit["tags"])
        
        if gen_mode == "Context-Aware (状況に合わせる)":
            prompts.append(random.choice(sit["poses"]))
        else:
            prompts.append(random.choice(data["random_poses"]))
            
        final = ", ".join(list(set(prompts)))
        if use_quality: final = data["quality_tags"] + ", " + final
        return final
    except Exception as e: return str(e)

def save_prompt_action(name, prompt):
    if not name: return gr.update(), "Error: No Name"
    d = load_data("saved")
    d[name] = prompt
    with open(get_paths()["saved"], "w", encoding="utf-8") as f:
        json.dump(d, f, indent=2, ensure_ascii=False)
    return gr.update(choices=list(d.keys())), f"Saved: {name}"

def load_prompt_action(name):
    return load_data("saved").get(name, "")

# --- UI Builder ---
def on_ui_tabs():
    saved_data = load_data("saved")
    saved_choices = list(saved_data.keys()) if saved_data else []
    
    # LoRAスキャン
    lora_lib = get_lora_library()

    with gr.Blocks(analytics_enabled=False, css=CSS) as ui:
        gr.HTML(visible=False, value=JS_SCRIPT)

        with gr.Row():
            # LEFT
            with gr.Column(scale=1, min_width=300):
                gr.Markdown("### 🎲 Random Gen v2.0")
                with gr.Group():
                    gen_mode = gr.Radio(["Context-Aware (状況に合わせる)", "Random Chaos (完全ランダム)"], label="Mode", value="Context-Aware (状況に合わせる)")
                    cloth_mode = gr.Radio(["Full Set (全身セット)", "Mix & Match (パーツ別ランダム)"], label="Outfit", value="Full Set (全身セット)")
                    with gr.Row():
                        nsfw = gr.Checkbox(label="🔞 NSFW", value=False)
                        extreme = gr.Checkbox(label="🔥 Extreme", value=False)
                    quality = gr.Checkbox(label="Quality Tags", value=True)
                btn_gen = gr.Button("🎲 GENERATE", variant="primary", size="lg")
                
                gr.Markdown("---")
                with gr.Group():
                    saved_dd = gr.Dropdown(label="Load", choices=saved_choices)
                    save_name = gr.Textbox(label="Name", placeholder="Save name...")
                    btn_save = gr.Button("Save")
                    save_msg = gr.Markdown("")

            # RIGHT
            with gr.Column(scale=2):
                output_box = gr.Textbox(label="Prompt", lines=4, interactive=True, elem_id="random_gen_result_box", show_copy_button=True)
                
                with gr.Row():
                    btn_txt = gr.Button("👉 Send to txt2img")
                    btn_img = gr.Button("👉 Send to img2img")

                # --- LoRA Browser with Tabs ---
                gr.Markdown("### 🧬 LoRA Library (Civitai Helper Integrated)")
                
                if lora_lib:
                    with gr.Tabs():
                        for folder, items in lora_lib.items():
                            with gr.TabItem(label=f"{folder} ({len(items)})"):
                                with gr.Column(elem_classes=["lora-tab-container"]):
                                    # HTML生成
                                    gr.HTML(make_html_for_loras(items))
                else:
                    gr.Markdown(f"**Error:** LoRA folder not found or empty at `{TARGET_LORA_DIR}`.")

        # Events
        btn_gen.click(fn=generate_prompt_logic, inputs=[gen_mode, cloth_mode, nsfw, extreme, quality], outputs=[output_box])
        btn_save.click(fn=save_prompt_action, inputs=[save_name, output_box], outputs=[saved_dd, save_msg])
        saved_dd.change(fn=load_prompt_action, inputs=[saved_dd], outputs=[output_box])
        
        btn_txt.click(fn=None, _js='() => window.sendPromptTo("txt2img")')
        btn_img.click(fn=None, _js='() => window.sendPromptTo("img2img")')

    return [(ui, "Random Gen", "random_gen_tab")]

script_callbacks.on_ui_tabs(on_ui_tabs)
