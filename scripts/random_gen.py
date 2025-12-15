import modules.scripts as scripts
import gradio as gr
from modules import script_callbacks, shared
import json
import random
import os
import traceback
import html
import glob

# --- JavaScript Logic ---
# LoRAクリック時の処理と、SendToボタンの処理
JS_SCRIPT = """
async (x) => {
    // ------------------------------------------------
    // 1. Text Injection Helper
    // ------------------------------------------------
    function insertText(text) {
        var ta = gradioApp().querySelector('#random_gen_result_box textarea');
        if (!ta) return;
        
        // 既にテキストがある場合はカンマを追加
        var sep = ta.value.trim().length > 0 ? ", " : "";
        ta.value = ta.value + sep + text;
        
        // React/Gradioに通知
        ta.dispatchEvent(new Event('input', { bubbles: true }));
    }

    // ------------------------------------------------
    // 2. Global Function for LoRA Click (called from HTML)
    // ------------------------------------------------
    window.addLoraToGen = function(name, trigger) {
        var text = "<lora:" + name + ":1>";
        if (trigger && trigger !== "None" && trigger !== "") {
            text += ", " + trigger;
        }
        insertText(text);
    }

    // ------------------------------------------------
    // 3. Send To Buttons Logic
    // ------------------------------------------------
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

# --- CSS for LoRA Grid ---
CSS = """
.lora-container {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(100px, 1fr));
    gap: 8px;
    max-height: 400px;
    overflow-y: auto;
    padding: 8px;
    background: var(--background-fill-primary);
    border: 1px solid var(--border-color-primary);
    border-radius: 8px;
}
.lora-card {
    position: relative;
    cursor: pointer;
    border-radius: 6px;
    overflow: visible; /* Popupのためにvisible */
    background: var(--neutral-800);
    transition: transform 0.1s;
}
.lora-card:hover {
    z-index: 100; /* ホバー時は一番上に */
}
.lora-thumb {
    width: 100%;
    height: 100px;
    object-fit: cover;
    border-radius: 6px;
    display: block;
}
.lora-no-thumb {
    width: 100%;
    height: 100px;
    background: linear-gradient(45deg, #333, #555);
    display: flex;
    align-items: center;
    justify-content: center;
    color: #aaa;
    font-size: 10px;
    border-radius: 6px;
}
/* --- Hover Popup Info --- */
.lora-info-popup {
    display: none;
    position: absolute;
    top: -10px;
    left: 50%;
    transform: translate(-50%, -100%);
    width: 200px;
    background: rgba(0, 0, 0, 0.9);
    border: 1px solid var(--primary-500);
    color: white;
    padding: 8px;
    border-radius: 8px;
    box-shadow: 0 4px 12px rgba(0,0,0,0.5);
    pointer-events: none;
    z-index: 999;
}
.lora-card:hover .lora-info-popup {
    display: block;
}
.popup-img {
    width: 100%;
    height: auto;
    border-radius: 4px;
    margin-bottom: 4px;
}
.popup-name {
    font-weight: bold;
    font-size: 12px;
    color: var(--primary-400);
    margin-bottom: 2px;
    word-break: break-all;
}
.popup-trigger {
    font-size: 10px;
    color: #ddd;
    line-height: 1.2;
}
"""

# --- File Paths & Data Loading ---
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

# --- LoRA Scanning Logic ---
def get_lora_list(search_query=""):
    lora_dir = shared.cmd_opts.lora_dir
    if not lora_dir:
        return []

    loras = []
    # 再帰的に検索
    for root, dirs, files in os.walk(lora_dir):
        for file in files:
            if file.endswith(".safetensors"):
                name = os.path.splitext(file)[0]
                full_path = os.path.join(root, file)
                
                # 検索フィルタ
                if search_query and search_query.lower() not in name.lower():
                    continue

                # プレビュー画像の検索 (同名.png, .preview.png, .jpg等)
                base_name = os.path.splitext(full_path)[0]
                preview_path = None
                for ext in [".png", ".preview.png", ".jpg", ".jpeg", ".webp"]:
                    if os.path.exists(base_name + ext):
                        preview_path = base_name + ext
                        break
                
                # トリガーワードの検索 (.civitai.info or .json)
                triggers = ""
                json_path = base_name + ".civitai.info"
                if not os.path.exists(json_path):
                    json_path = base_name + ".json"
                
                if os.path.exists(json_path):
                    try:
                        with open(json_path, "r", encoding="utf-8") as f:
                            meta = json.load(f)
                            # Civitai形式の場合
                            if "trainedWords" in meta and meta["trainedWords"]:
                                triggers = ", ".join(meta["trainedWords"])
                            # 単純なJSONの場合 (optional)
                            elif "activation text" in meta:
                                triggers = meta["activation text"]
                    except: pass

                # 画像パスをGradio用に変換 (/file=path)
                img_url = f"/file={preview_path}" if preview_path else None
                
                loras.append({
                    "name": name,
                    "image": img_url,
                    "triggers": triggers
                })
    
    return sorted(loras, key=lambda x: x["name"])

def make_lora_html(search_text=""):
    loras = get_lora_list(search_text)
    
    if not loras:
        return "<div style='padding:10px;'>No LoRAs found. Check your folder or search query.</div>"

    html_content = "<div class='lora-container'>"
    
    for lora in loras:
        name = html.escape(lora["name"])
        trigger_raw = lora["triggers"]
        trigger_safe = html.escape(trigger_raw).replace("'", "\\'") # JS用にエスケープ
        
        img_tag = ""
        if lora["image"]:
            img_tag = f"<img src='{lora['image']}' class='lora-thumb' loading='lazy'>"
            popup_img = f"<img src='{lora['image']}' class='popup-img'>"
        else:
            img_tag = f"<div class='lora-no-thumb'>{name[:10]}..</div>"
            popup_img = ""

        # ポップアップ情報の構築
        popup_info = f"""
        <div class='lora-info-popup'>
            {popup_img}
            <div class='popup-name'>{name}</div>
            <div class='popup-trigger'>Run: &lt;lora:{name}:1&gt;<br>Trigger: {trigger_safe[:100]}{'...' if len(trigger_safe)>100 else ''}</div>
        </div>
        """

        # カード本体
        card = f"""
        <div class='lora-card' onclick="addLoraToGen('{name}', '{trigger_safe}')">
            {img_tag}
            {popup_info}
        </div>
        """
        html_content += card

    html_content += "</div>"
    return html_content

# --- Generation Logic (Same as before) ---
def generate_prompt_logic(gen_mode, clothing_mode, is_nsfw, is_extreme, use_quality):
    try:
        data = load_data("tags")
        if not data: return "Error: Could not load data."
        prompts = []
        
        if "appearance" in data:
            app = data["appearance"]
            if "hair_texture" in app: prompts.append(random.choice(app["hair_texture"]))
            if "hair" in app: prompts.append(random.choice(app["hair"]))
            if "eyes" in app: prompts.append(random.choice(app["eyes"]))
            if "body" in app: prompts.append(random.choice(app["body"]))
            if "expressions" in app:
                expr_list = list(app["expressions"]["sfw"])
                if is_nsfw: expr_list += app["expressions"]["nsfw"]
                if is_extreme: expr_list += app["expressions"]["extreme"]
                prompts.append(random.choice(expr_list))
            if clothing_mode == "Full Set (全身セット)":
                clothes_list = list(app["clothes_sets"]["sfw"])
                if is_nsfw: clothes_list += app["clothes_sets"]["nsfw"]
                if is_extreme: clothes_list += app["clothes_sets"]["extreme"]
                prompts.append(random.choice(clothes_list))
            else:
                separates = app["separates"]
                for part in ["tops", "bottoms", "underwear"]:
                    part_list = list(separates[part]["sfw"])
                    if is_nsfw: part_list += separates[part]["nsfw"]
                    if is_extreme: part_list += separates[part]["extreme"]
                    prompts.append(random.choice(part_list))
            if "accessories" in app: prompts.append(random.choice(app["accessories"]))

        allowed_levels = ["sfw"]
        if is_nsfw: allowed_levels.append("nsfw")
        if is_extreme: allowed_levels.append("extreme")
        valid_situations = [s for s in data["situations"] if s.get("nsfw_level", "sfw") in allowed_levels]
        situation = random.choice(valid_situations) if valid_situations else {"tags": "", "poses": ["standing"]}
        prompts.append(situation["tags"])

        if gen_mode == "Context-Aware (状況に合わせる)":
            prompts.append(random.choice(situation["poses"]))
        else:
            prompts.append(random.choice(data["random_poses"]))

        final_prompt = ", ".join(list(set(prompts)))
        if use_quality: final_prompt = data["quality_tags"] + ", " + final_prompt
        return final_prompt
    except Exception as e: return f"Error: {str(e)}"

# --- Save/Load Logic ---
def save_prompt_action(name, prompt):
    if not name or not prompt: return gr.update(), "Name/Prompt empty"
    saved_data = load_data("saved")
    saved_data[name] = prompt
    with open(get_paths()["saved"], "w", encoding="utf-8") as f:
        json.dump(saved_data, f, indent=2, ensure_ascii=False)
    return gr.update(choices=list(saved_data.keys())), f"Saved: {name}"

def load_prompt_action(selected_name):
    saved_data = load_data("saved")
    return saved_data.get(selected_name, "")

# --- UI ---
def on_ui_tabs():
    data = load_data("tags")
    quality_default = data["quality_tags"] if data else ""
    saved_data = load_data("saved")
    saved_choices = list(saved_data.keys()) if saved_data else []

    with gr.Blocks(analytics_enabled=False, css=CSS) as ui_component:
        with gr.Row():
            # Left Column
            with gr.Column(scale=1, min_width=300):
                gr.Markdown("### 🎲 Random Gen v1.7")
                with gr.Group():
                    gen_mode_radio = gr.Radio(["Context-Aware (状況に合わせる)", "Random Chaos (完全ランダム)"], label="Mode", value="Context-Aware (状況に合わせる)")
                    clothing_mode_radio = gr.Radio(["Full Set (全身セット)", "Mix & Match (パーツ別ランダム)"], label="Outfit", value="Full Set (全身セット)")
                    with gr.Row():
                        nsfw_checkbox = gr.Checkbox(label="🔞 NSFW", value=False)
                        extreme_checkbox = gr.Checkbox(label="🔥 Extreme", value=False)
                    quality_checkbox = gr.Checkbox(label="Quality Tags", value=True)
                btn_gen = gr.Button("🎲 GENERATE", variant="primary", size="lg")
                
                gr.Markdown("---")
                with gr.Group():
                    saved_dropdown = gr.Dropdown(label="Load Prompt", choices=saved_choices)
                    save_name = gr.Textbox(label="Save Name", placeholder="Name...")
                    btn_save = gr.Button("Save")
                    save_msg = gr.Markdown("")

            # Right Column
            with gr.Column(scale=2):
                output_box = gr.Textbox(label="Prompt", lines=4, interactive=True, show_copy_button=True, elem_id="random_gen_result_box")
                
                with gr.Row():
                    # JS arguments: dummy input
                    btn_send_txt = gr.Button("👉 txt2img")
                    btn_send_img = gr.Button("👉 img2img")

                # --- LoRA Browser Section ---
                gr.Markdown("### 🧬 LoRA Quick Select")
                with gr.Group():
                    with gr.Row():
                        lora_search = gr.Textbox(label="Search LoRA", placeholder="Filter by name...", scale=4)
                        btn_refresh_lora = gr.Button("🔄 Scan/Refresh", scale=1)
                    
                    # HTML Container for LoRAs
                    lora_html_area = gr.HTML(value="Click Refresh to load LoRAs...")

        # --- Events ---
        btn_gen.click(
            fn=generate_prompt_logic,
            inputs=[gen_mode_radio, clothing_mode_radio, nsfw_checkbox, extreme_checkbox, quality_checkbox],
            outputs=[output_box]
        )

        # Send buttons (JS only)
        btn_send_txt.click(fn=None, inputs=[], outputs=[], _js='() => ' + JS_SCRIPT.replace("JS_ACTION", "send_txt").replace("return \"\";", "return window.JS_SCRIPT_FUNC(\"send_txt\");").replace('async (x) =>', 'async () => { return window.addLoraToGen ? window.JS_SCRIPT_FUNC("send_txt") : ""; }'))
        # ※GradioのJS呼び出しは癖があるため、シンプルに埋め込み関数を定義して呼び出す方式にします
        # 下記のダミー要素を使ってJSを注入・実行します
        
        dummy_js = gr.HTML(visible=False, value=f"<script>{JS_SCRIPT.replace('async (x)', 'window.JS_SCRIPT_FUNC = async function(x)')}</script>")
        
        btn_send_txt.click(fn=None, _js='() => window.JS_SCRIPT_FUNC("send_txt")')
        btn_send_img.click(fn=None, _js='() => window.JS_SCRIPT_FUNC("send_img")')

        # Save/Load
        btn_save.click(fn=save_prompt_action, inputs=[save_name, output_box], outputs=[saved_dropdown, save_msg])
        saved_dropdown.change(fn=load_prompt_action, inputs=[saved_dropdown], outputs=[output_box])

        # LoRA Events
        btn_refresh_lora.click(fn=make_lora_html, inputs=[lora_search], outputs=[lora_html_area])
        lora_search.change(fn=make_lora_html, inputs=[lora_search], outputs=[lora_html_area])

    return [(ui_component, "Random Gen", "random_gen_tab")]

script_callbacks.on_ui_tabs(on_ui_tabs)
