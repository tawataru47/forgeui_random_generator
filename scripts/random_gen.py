import modules.scripts as scripts
import gradio as gr
from modules import script_callbacks, shared
import json
import random
import os
import traceback
import html

# --- User Setting ---
TARGET_LORA_DIR = r"C:\stableDiffusion\stable-diffusion-webui\models\Lora"

# --- JavaScript Logic ---
JS_SCRIPT = """
<script>
    function insertTextToPrompt(text) {
        var ta = gradioApp().querySelector('#random_gen_result_box textarea');
        if (!ta) return;
        var currentVal = ta.value;
        var sep = currentVal.trim().length > 0 ? ", " : "";
        var nativeInputValueSetter = Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, "value").set;
        nativeInputValueSetter.call(ta, currentVal + sep + text);
        ta.dispatchEvent(new Event('input', { bubbles: true }));
    }

    window.addLoraToGen = function(element) {
        var name = element.getAttribute('data-name');
        var trigger = element.getAttribute('data-trigger');
        var text = "<lora:" + name + ":1>";
        if (trigger && trigger !== "None" && trigger !== "" && trigger !== "null") {
            text += ", " + trigger;
        }
        insertTextToPrompt(text);
    }

    window.sendPromptTo = function(tabName) {
        var src = gradioApp().querySelector('#random_gen_result_box textarea');
        if (!src) return;
        var targetId = (tabName === 'txt2img') ? '#txt2img_prompt textarea' : '#img2img_prompt textarea';
        var dest = gradioApp().querySelector(targetId);
        if (dest) {
            var nativeInputValueSetter = Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, "value").set;
            nativeInputValueSetter.call(dest, src.value);
            dest.dispatchEvent(new Event('input', { bubbles: true }));
            var tabIndex = (tabName === 'txt2img') ? 1 : 2; 
            var tab = gradioApp().querySelector('#tabs button:nth-child(' + tabIndex + ')'); 
            if (tab) tab.click();
        }
    }
</script>
"""

# --- CSS ---
CSS = """
.rg-lora-container {
    height: 500px;
    overflow-y: auto;
    padding: 10px;
    background-color: var(--background-fill-primary);
    border: 1px solid var(--border-color-primary);
    border-radius: 4px;
}
.rg-lora-grid {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    align-content: flex-start;
}
.rg-lora-card {
    width: 140px; /* 少し横長に */
    position: relative;
    cursor: pointer;
    border-radius: 4px;
    background: var(--neutral-800);
    border: 1px solid var(--border-color-primary);
    display: flex;
    flex-direction: column;
    transition: transform 0.1s;
    padding: 8px;
    align-items: center;
    justify-content: center;
    min-height: 60px;
}
.rg-lora-card:hover {
    transform: scale(1.03);
    border-color: var(--primary-500);
    background: var(--neutral-700);
    z-index: 50;
}
.rg-card-title {
    font-size: 11px;
    font-weight: bold;
    text-align: center;
    word-break: break-all;
    color: var(--body-text-color);
}
.rg-card-triggers {
    font-size: 9px;
    color: #888;
    margin-top: 4px;
    text-align: center;
    overflow: hidden;
    white-space: nowrap;
    text-overflow: ellipsis;
    width: 100%;
}
/* Hover Popup */
.rg-popup {
    display: none;
    position: absolute;
    bottom: 100%;
    left: 50%;
    transform: translate(-50%, -5px);
    width: 200px;
    background: rgba(20, 20, 30, 0.95);
    border: 1px solid var(--primary-500);
    border-radius: 6px;
    padding: 8px;
    pointer-events: none;
    z-index: 1000;
    box-shadow: 0 5px 15px rgba(0,0,0,0.5);
}
.rg-lora-card:hover .rg-popup {
    display: block;
}
.rg-badge {
    display: inline-block;
    background: #444;
    padding: 2px 4px;
    border-radius: 3px;
    margin: 2px;
    font-size: 10px;
    color: #8f8;
    border: 1px solid #666;
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

# --- LoRA Scanning (Metadata Only) ---
def get_lora_library():
    root_path = TARGET_LORA_DIR
    if not os.path.exists(root_path): return None

    library = {}

    for root, dirs, files in os.walk(root_path):
        rel_path = os.path.relpath(root, root_path)
        folder_name = "Root" if rel_path == "." else rel_path
        
        lora_list = []
        for file in files:
            if file.endswith(".safetensors"):
                name = os.path.splitext(file)[0]
                full_path = os.path.join(root, file)
                base_name_path = os.path.splitext(full_path)[0]
                
                # 画像読み込み処理は完全に削除（高速化のため）

                # --- Metadata (JSON) ---
                triggers = []
                json_path = base_name_path + ".json"
                civitai_path = base_name_path + ".civitai.info"
                
                target_meta = None
                if os.path.exists(json_path): target_meta = json_path
                elif os.path.exists(civitai_path): target_meta = civitai_path
                
                if target_meta:
                    try:
                        with open(target_meta, "r", encoding="utf-8") as f:
                            meta = json.load(f)
                            if "activation text" in meta and meta["activation text"]:
                                triggers.append(meta["activation text"])
                            if "trainedWords" in meta and meta["trainedWords"]:
                                for t in meta["trainedWords"]:
                                    if t not in triggers: triggers.append(t)
                    except: pass
                
                trigger_text = ", ".join(triggers) if triggers else ""

                lora_list.append({
                    "name": name,
                    "triggers": triggers,
                    "trigger_text": trigger_text
                })
        
        if lora_list:
            lora_list.sort(key=lambda x: x["name"].lower())
            library[folder_name] = lora_list
            
    sorted_lib = {}
    if "Root" in library: sorted_lib["Root"] = library.pop("Root")
    for k in sorted(library.keys()): sorted_lib[k] = library[k]
    return sorted_lib

def make_html_for_loras(lora_list):
    if not lora_list: return "<div style='padding:20px'>No LoRAs found.</div>"
    
    html_out = "<div class='rg-lora-grid'>"
    for lora in lora_list:
        name = html.escape(lora["name"])
        trigger_safe = html.escape(lora["trigger_text"]).replace("'", "\\'")
        
        # Triggers
        if lora["triggers"]:
            t_html = "".join([f"<span class='rg-badge'>{html.escape(t)}</span>" for t in lora["triggers"]])
            mini_trigger = f"{len(lora['triggers'])} triggers"
        else:
            t_html = "<span style='color:#777; font-style:italic;'>No triggers</span>"
            mini_trigger = ""

        card = f"""
        <div class='rg-lora-card' onclick="addLoraToGen(this)" data-name="{name}" data-trigger="{trigger_safe}" title="{name}">
            <div class='rg-card-title'>💊 {name}</div>
            <div class='rg-card-triggers'>{mini_trigger}</div>
            
            <div class='rg-popup'>
                <div style='font-weight:bold; color:#f88; margin-bottom:4px;'>{name}</div>
                <div style='font-size:11px; color:#eee;'>{t_html}</div>
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
    lora_lib = get_lora_library()

    with gr.Blocks(analytics_enabled=False, css=CSS) as ui:
        gr.HTML(visible=False, value=JS_SCRIPT)

        with gr.Row():
            with gr.Column(scale=1, min_width=300):
                gr.Markdown("### 🎲 Random Gen v2.4")
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

            with gr.Column(scale=2):
                output_box = gr.Textbox(label="Prompt", lines=4, interactive=True, elem_id="random_gen_result_box", show_copy_button=True)
                with gr.Row():
                    btn_txt = gr.Button("👉 Send to txt2img")
                    btn_img = gr.Button("👉 Send to img2img")

                gr.Markdown("### 🧬 LoRA Library (No Images / High Speed)")
                if lora_lib:
                    with gr.Tabs():
                        for folder, items in lora_lib.items():
                            with gr.TabItem(label=f"{folder} ({len(items)})"):
                                with gr.Column(elem_classes=["rg-lora-container"]):
                                    gr.HTML(make_html_for_loras(items))
                else:
                    gr.Markdown(f"**Error:** LoRA folder not found at `{TARGET_LORA_DIR}`.")

        btn_gen.click(fn=generate_prompt_logic, inputs=[gen_mode, cloth_mode, nsfw, extreme, quality], outputs=[output_box])
        btn_save.click(fn=save_prompt_action, inputs=[save_name, output_box], outputs=[saved_dd, save_msg])
        saved_dd.change(fn=load_prompt_action, inputs=[saved_dd], outputs=[output_box])
        btn_txt.click(fn=None, _js='() => window.sendPromptTo("txt2img")')
        btn_img.click(fn=None, _js='() => window.sendPromptTo("img2img")')

    return [(ui, "Random Gen", "random_gen_tab")]

script_callbacks.on_ui_tabs(on_ui_tabs)
