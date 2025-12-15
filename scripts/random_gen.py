import modules.scripts as scripts
import gradio as gr
from modules import script_callbacks, shared
import json
import random
import os
import traceback
import html
import glob
from pathlib import Path

# --- User Setting: LoRA Folder Path ---
# 指定されたパスを優先し、無ければ相対パスを探します
TARGET_LORA_DIR = r"C:\stableDiffusion\stable-diffusion-webui\models\Lora"

# --- JavaScript Logic ---
JS_SCRIPT = """
async (x) => {
    // 1. Text Injection Helper
    function insertText(text) {
        var ta = gradioApp().querySelector('#random_gen_result_box textarea');
        if (!ta) return;
        
        var sep = ta.value.trim().length > 0 ? ", " : "";
        ta.value = ta.value + sep + text;
        ta.dispatchEvent(new Event('input', { bubbles: true }));
    }

    // 2. Global Function for LoRA Click
    window.addLoraToGen = function(name, trigger) {
        var text = "<lora:" + name + ":1>";
        if (trigger && trigger !== "None" && trigger !== "") {
            text += ", " + trigger;
        }
        insertText(text);
    }

    // 3. Send To Buttons Logic
    if (x === "send_txt") {
        var dest = gradioApp().querySelector('#txt2img_prompt textarea');
        var src = gradioApp().querySelector('#random_gen_result_box textarea');
        if (dest && src) {
            dest.value = src.value;
            dest.dispatchEvent(new Event('input', { bubbles: true }));
            var tab = gradioApp().querySelector('#tabs button:nth-child(1)'); 
            if (tab) tab.click();
        }
    } else if (x === "send_img") {
        var dest = gradioApp().querySelector('#img2img_prompt textarea');
        var src = gradioApp().querySelector('#random_gen_result_box textarea');
        if (dest && src) {
            dest.value = src.value;
            dest.dispatchEvent(new Event('input', { bubbles: true }));
            var tab = gradioApp().querySelector('#tabs button:nth-child(2)'); 
            if (tab) tab.click();
        }
    }
    return "";
}
"""

# --- CSS for Horizontal Grid & Tabs ---
CSS = """
.lora-tab-container {
    height: 500px;
    overflow-y: auto;
    padding-right: 5px;
}
.lora-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(110px, 1fr));
    gap: 8px;
    padding: 4px;
}
.lora-card {
    position: relative;
    cursor: pointer;
    border-radius: 8px;
    background: var(--neutral-800);
    border: 1px solid var(--border-color-primary);
    overflow: visible;
    transition: transform 0.1s, box-shadow 0.1s;
}
.lora-card:hover {
    transform: scale(1.02);
    z-index: 50;
    border-color: var(--primary-500);
}
.lora-thumb-container {
    width: 100%;
    aspect-ratio: 2/3; /* Civitai standard portrait */
    overflow: hidden;
    border-radius: 8px 8px 0 0;
    background: #333;
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
    align-items: center;
    justify-content: center;
    color: #888;
    font-size: 24px;
}
.lora-name-bar {
    padding: 4px 6px;
    font-size: 11px;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    background: rgba(0,0,0,0.2);
    color: var(--body-text-color);
    text-align: center;
}

/* --- Hover Popup Info --- */
.lora-info-popup {
    display: none;
    position: absolute;
    bottom: 100%; /* Show above the card */
    left: 50%;
    transform: translate(-50%, -10px);
    width: 220px;
    background: rgba(20, 20, 20, 0.95);
    border: 1px solid var(--primary-500);
    color: white;
    padding: 10px;
    border-radius: 8px;
    box-shadow: 0 5px 15px rgba(0,0,0,0.5);
    pointer-events: none;
    z-index: 100;
}
.lora-card:hover .lora-info-popup {
    display: block;
}
.popup-img-large {
    width: 100%;
    height: auto;
    border-radius: 4px;
    margin-bottom: 6px;
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
    line-height: 1.3;
}
"""

# --- Data Loading ---
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

# --- LoRA Logic ---
def find_lora_dir():
    # 1. User defined path
    if os.path.exists(TARGET_LORA_DIR):
        return TARGET_LORA_DIR
    
    # 2. Forge standard relative path
    base_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "models", "Lora"))
    if os.path.exists(base_path):
        return base_path
        
    return None

def get_lora_structure():
    root_path = find_lora_dir()
    if not root_path:
        return None

    # Structure: {'Folder Name': [ {name, image, triggers}, ... ]}
    structure = {}
    
    # Walk through directory
    for root, dirs, files in os.walk(root_path):
        # Get folder name relative to Lora root
        rel_path = os.path.relpath(root, root_path)
        if rel_path == ".":
            folder_name = "Root (Uncategorized)"
        else:
            folder_name = rel_path
            
        lora_list = []
        
        for file in files:
            if file.endswith(".safetensors"):
                name = os.path.splitext(file)[0]
                full_path = os.path.join(root, file)
                base_name = os.path.splitext(full_path)[0]
                
                # --- Find Preview Image ---
                # Search for: .preview.png, .png, .jpg, .jpeg, .webp
                preview_path = None
                for ext in [".preview.png", ".png", ".jpg", ".jpeg", ".webp"]:
                    test_path = base_name + ext
                    if os.path.exists(test_path):
                        preview_path = test_path
                        break
                
                img_url = f"/file={preview_path}" if preview_path else None
                
                # --- Find Metadata (Civitai Helper) ---
                # Search for: .civitai.info, .json
                triggers = []
                
                # 1. Try .civitai.info (Best source)
                meta_path = base_name + ".civitai.info"
                if not os.path.exists(meta_path):
                    meta_path = base_name + ".json"
                
                if os.path.exists(meta_path):
                    try:
                        with open(meta_path, "r", encoding="utf-8") as f:
                            meta = json.load(f)
                            # Civitai format
                            if "trainedWords" in meta and meta["trainedWords"]:
                                triggers = meta["trainedWords"]
                            # Other formats
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
            # Sort by name
            lora_list.sort(key=lambda x: x["name"])
            structure[folder_name] = lora_list
            
    # Sort folders (Root first, then alphabetical)
    sorted_structure = {}
    if "Root (Uncategorized)" in structure:
        sorted_structure["Root (Uncategorized)"] = structure.pop("Root (Uncategorized)")
    
    for k in sorted(structure.keys()):
        sorted_structure[k] = structure[k]
        
    return sorted_structure

def make_html_for_loras(lora_list):
    if not lora_list: return "<div>No LoRAs found.</div>"
    
    html_content = "<div class='lora-grid'>"
    for lora in lora_list:
        name = html.escape(lora["name"])
        trigger_raw = lora["trigger"]
        trigger_safe = html.escape(trigger_raw).replace("'", "\\'")
        
        img_tag = ""
        popup_img = ""
        if lora["image"]:
            img_tag = f"<img src='{lora['image']}' class='lora-thumb' loading='lazy'>"
            popup_img = f"<img src='{lora['image']}' class='popup-img-large'>"
        else:
            img_tag = f"<div class='lora-no-thumb'>💊</div>"
        
        popup = f"""
        <div class='lora-info-popup'>
            {popup_img}
            <div class='popup-title'>{name}</div>
            <div class='popup-meta'>
                <b>Trigger:</b> {trigger_safe if trigger_safe else 'None'}<br>
                <span style='opacity:0.7'>Click to add</span>
            </div>
        </div>
        """
        
        card = f"""
        <div class='lora-card' onclick="addLoraToGen('{name}', '{trigger_safe}')" title='{name}'>
            <div class='lora-thumb-container'>{img_tag}</div>
            <div class='lora-name-bar'>{name}</div>
            {popup}
        </div>
        """
        html_content += card
        
    html_content += "</div>"
    return html_content

# --- Generator Logic (Standard) ---
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

# --- Save/Load Logic ---
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
    
    # Pre-scan LoRAs for Tabs
    lora_structure = get_lora_structure()

    with gr.Blocks(analytics_enabled=False, css=CSS) as ui:
        # Dummy JS injection
        gr.HTML(visible=False, value=f"<script>{JS_SCRIPT.replace('async (x)', 'window.JS_SCRIPT_FUNC = async function(x)')}</script>")

        with gr.Row():
            # --- LEFT ---
            with gr.Column(scale=1, min_width=300):
                gr.Markdown("### 🎲 Random Gen v1.8")
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

                # --- LoRA Tabs Section ---
                gr.Markdown("### 🧬 LoRA Library")
                
                if lora_structure:
                    with gr.Tabs():
                        for folder, items in lora_structure.items():
                            with gr.TabItem(label=f"{folder} ({len(items)})"):
                                with gr.Column(elem_classes=["lora-tab-container"]):
                                    gr.HTML(make_html_for_loras(items))
                else:
                    gr.Markdown(f"**Error:** LoRA folder not found at `{TARGET_LORA_DIR}`. Please check the path in script.")

        # Actions
        btn_gen.click(fn=generate_prompt_logic, inputs=[gen_mode, cloth_mode, nsfw, extreme, quality], outputs=[output_box])
        btn_save.click(fn=save_prompt_action, inputs=[save_name, output_box], outputs=[saved_dd, save_msg])
        saved_dd.change(fn=load_prompt_action, inputs=[saved_dd], outputs=[output_box])
        
        # JS Actions
        btn_txt.click(fn=None, _js='() => window.JS_SCRIPT_FUNC("send_txt")')
        btn_img.click(fn=None, _js='() => window.JS_SCRIPT_FUNC("send_img")')

    return [(ui, "Random Gen", "random_gen_tab")]

script_callbacks.on_ui_tabs(on_ui_tabs)
