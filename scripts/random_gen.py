import modules.scripts as scripts
import gradio as gr
from modules import script_callbacks, shared
import json
import random
import os
import traceback
import html
import urllib.parse # URLエンコード用に追加

# --- User Setting: LoRA Folder Path ---
TARGET_LORA_DIR = r"C:\stableDiffusion\stable-diffusion-webui\models\Lora"

# --- JavaScript Logic ---
# Python側で定義した変数をJSで確実に受け取るためのスクリプト
JS_SCRIPT = """
<script>
    // 1. Text Injection Helper
    function insertTextToPrompt(text) {
        // Forge/WebUIの構造に合わせて対象を探す
        var ta = gradioApp().querySelector('#random_gen_result_box textarea');
        if (!ta) return;
        
        var currentVal = ta.value;
        var sep = currentVal.trim().length > 0 ? ", " : "";
        
        // Reactのstate更新をトリガーするために setter を呼ぶ必要がある場合がある
        var nativeInputValueSetter = Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, "value").set;
        nativeInputValueSetter.call(ta, currentVal + sep + text);
        
        ta.dispatchEvent(new Event('input', { bubbles: true }));
    }

    // 2. Global Function for LoRA Click (Elementからデータ取得)
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

# --- CSS ---
CSS = """
.lora-tab-container {
    height: 600px;
    overflow-y: auto;
    padding-right: 5px;
}
.lora-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(120px, 1fr));
    gap: 10px;
    padding: 8px;
}
.lora-card {
    position: relative;
    cursor: pointer;
    border-radius: 8px;
    background: var(--neutral-800);
    border: 1px solid var(--border-color-primary);
    overflow: visible;
    transition: transform 0.15s, box-shadow 0.15s;
    user-select: none;
}
.lora-card:hover {
    transform: translateY(-2px);
    z-index: 50;
    border-color: var(--primary-500);
    box-shadow: 0 4px 8px rgba(0,0,0,0.3);
}
.lora-thumb-container {
    width: 100%;
    aspect-ratio: 2/3;
    overflow: hidden;
    border-radius: 8px 8px 0 0;
    background: #222;
    position: relative;
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
    font-size: 12px;
    text-align: center;
    padding: 4px;
}
.lora-name-bar {
    padding: 6px;
    font-size: 11px;
    line-height: 1.2;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    background: rgba(30, 30, 30, 0.9);
    color: #eee;
    text-align: center;
    border-radius: 0 0 8px 8px;
}

/* Hover Popup */
.lora-info-popup {
    display: none;
    position: absolute;
    bottom: 100%;
    left: 50%;
    transform: translate(-50%, -10px);
    width: 240px;
    background: rgba(10, 10, 10, 0.95);
    border: 1px solid var(--primary-500);
    color: white;
    padding: 10px;
    border-radius: 8px;
    box-shadow: 0 8px 24px rgba(0,0,0,0.8);
    pointer-events: none;
    z-index: 100;
}
.lora-card:hover .lora-info-popup {
    display: block;
}
.popup-img-large {
    width: 100%;
    max-height: 300px;
    object-fit: contain;
    border-radius: 4px;
    margin-bottom: 8px;
    background: black;
}
.popup-title {
    font-weight: bold;
    font-size: 13px;
    color: var(--primary-400);
    margin-bottom: 4px;
    word-wrap: break-word;
}
.popup-meta {
    font-size: 11px;
    color: #ccc;
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

# --- LoRA Scanning ---
def get_lora_structure():
    root_path = TARGET_LORA_DIR
    if not os.path.exists(root_path):
        # Fallback to relative
        root_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "models", "Lora"))
        if not os.path.exists(root_path): return None

    structure = {}
    
    for root, dirs, files in os.walk(root_path):
        rel_path = os.path.relpath(root, root_path)
        folder_name = "Root" if rel_path == "." else rel_path
        
        lora_list = []
        for file in files:
            if file.endswith(".safetensors"):
                name = os.path.splitext(file)[0]
                full_path = os.path.join(root, file)
                base_name = os.path.splitext(full_path)[0]
                
                # Image Preview Check
                preview_path = None
                for ext in [".preview.png", ".png", ".jpg", ".jpeg", ".webp"]:
                    if os.path.exists(base_name + ext):
                        preview_path = base_name + ext
                        break
                
                # URL Encode for Browser (/file=C:/Path/To/Image.png)
                img_url = None
                if preview_path:
                    # Windows paths need forward slashes and URL encoding
                    clean_path = preview_path.replace("\\", "/")
                    encoded_path = urllib.parse.quote(clean_path, safe="/:")
                    img_url = f"/file={encoded_path}"
                
                # Triggers from Civitai Helper
                triggers = []
                # Try .civitai.info first
                meta_path = base_name + ".civitai.info"
                if not os.path.exists(meta_path):
                    meta_path = base_name + ".json"
                
                if os.path.exists(meta_path):
                    try:
                        with open(meta_path, "r", encoding="utf-8") as f:
                            meta = json.load(f)
                            if "trainedWords" in meta and meta["trainedWords"]:
                                triggers = meta["trainedWords"]
                            elif "activation text" in meta:
                                triggers = [meta["activation text"]]
                    except: pass
                
                trigger_text = ", ".join(triggers) if triggers else ""

                lora_list.append({
                    "name": name,
                    "image": img_url,
                    "trigger": trigger_text
                })
        
        if lora_list:
            lora_list.sort(key=lambda x: x["name"])
            structure[folder_name] = lora_list
            
    # Sort folders
    sorted_s = {}
    if "Root" in structure: sorted_s["Root"] = structure.pop("Root")
    for k in sorted(structure.keys()): sorted_s[k] = structure[k]
        
    return sorted_s

def make_html_for_loras(lora_list):
    if not lora_list: return "<div style='color:white; padding:10px'>No LoRAs found in this folder.</div>"
    
    html_content = "<div class='lora-grid'>"
    for lora in lora_list:
        name = html.escape(lora["name"])
        trigger_raw = lora["trigger"]
        # HTML属性用にエスケープ
        trigger_attr = html.escape(trigger_raw)
        
        img_tag = ""
        popup_img = ""
        
        if lora["image"]:
            img_tag = f"<img src='{lora['image']}' class='lora-thumb' loading='lazy'>"
            popup_img = f"<img src='{lora['image']}' class='popup-img-large'>"
        else:
            img_tag = f"<div class='lora-no-thumb'><span>NO IMAGE</span><br>{name[:10]}...</div>"
        
        # マウスホバー時のポップアップ
        popup = f"""
        <div class='lora-info-popup'>
            {popup_img}
            <div class='popup-title'>{name}</div>
            <div class='popup-meta'>
                {f'<b>Triggers:</b> {trigger_attr}' if trigger_attr else 'No triggers detected'}
            </div>
        </div>
        """
        
        # カード本体 (data属性に情報を埋め込む)
        card = f"""
        <div class='lora-card' 
             onclick="addLoraToGen(this)" 
             data-name="{name}" 
             data-trigger="{trigger_attr}">
            <div class='lora-thumb-container'>{img_tag}</div>
            <div class='lora-name-bar'>{name}</div>
            {popup}
        </div>
        """
        html_content += card
        
    html_content += "</div>"
    return html_content

# --- Logic (Generator & Save) ---
def generate_prompt_logic(gen_mode, clothing_mode, is_nsfw, is_extreme, use_quality):
    try:
        data = load_data("tags")
        if not data: return "Error: Data load failed."
        prompts = []
        
        if "appearance" in data:
            app = data["appearance"]
            if "hair_texture" in app: prompts.append(random.choice(app["hair_texture"]))
            if "hair" in app: prompts.append(random.choice(app["hair"]))
            if "eyes" in app: prompts.append(random.choice(app["eyes"]))
            if "body" in app: prompts.append(random.choice(app["body"]))
            
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

# --- UI Construction ---
def on_ui_tabs():
    saved_data = load_data("saved")
    saved_choices = list(saved_data.keys()) if saved_data else []
    lora_structure = get_lora_structure()

    with gr.Blocks(analytics_enabled=False, css=CSS) as ui:
        # JS Injection
        gr.HTML(visible=False, value=JS_SCRIPT)

        with gr.Row():
            # --- LEFT ---
            with gr.Column(scale=1, min_width=300):
                gr.Markdown("### 🎲 Random Gen v1.9")
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

            # --- RIGHT ---
            with gr.Column(scale=2):
                output_box = gr.Textbox(label="Prompt", lines=4, interactive=True, elem_id="random_gen_result_box", show_copy_button=True)
                
                with gr.Row():
                    btn_txt = gr.Button("👉 Send to txt2img")
                    btn_img = gr.Button("👉 Send to img2img")

                # --- LoRA Section ---
                gr.Markdown("### 🧬 LoRA Library")
                
                if lora_structure:
                    with gr.Tabs():
                        for folder_name, items in lora_structure.items():
                            with gr.TabItem(label=f"{folder_name} ({len(items)})"):
                                with gr.Column(elem_classes=["lora-tab-container"]):
                                    gr.HTML(make_html_for_loras(items))
                else:
                    gr.Markdown(f"**Error:** LoRA folder not found at `{TARGET_LORA_DIR}`. Check settings.")

        # Events
        btn_gen.click(fn=generate_prompt_logic, inputs=[gen_mode, cloth_mode, nsfw, extreme, quality], outputs=[output_box])
        btn_save.click(fn=save_prompt_action, inputs=[save_name, output_box], outputs=[saved_dd, save_msg])
        saved_dd.change(fn=load_prompt_action, inputs=[saved_dd], outputs=[output_box])
        
        # JS Events
        btn_txt.click(fn=None, _js='() => window.sendPromptTo("txt2img")')
        btn_img.click(fn=None, _js='() => window.sendPromptTo("img2img")')

    return [(ui, "Random Gen", "random_gen_tab")]

script_callbacks.on_ui_tabs(on_ui_tabs)
