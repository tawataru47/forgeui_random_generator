import modules.scripts as scripts
import gradio as gr
from modules import script_callbacks
import json
import random
import os
import traceback

# --- JavaScript Logic for "Send to" buttons ---
# ブラウザ側でtxt2img/img2imgの入力欄を探してテキストを流し込むスクリプト
JS_SEND_TXT = """
(x) => {
    try {
        var ta = gradioApp().querySelector('#txt2img_prompt textarea');
        if (ta) {
            ta.value = x;
            ta.dispatchEvent(new Event('input', { bubbles: true }));
        }
        // タブ切り替え（環境によってIDが異なる場合があるため、簡易的な実装）
        var tab = gradioApp().querySelector('#tabs button:nth-child(1)'); 
        if (tab) tab.click();
    } catch (e) { console.error(e); }
    return x;
}
"""

JS_SEND_IMG = """
(x) => {
    try {
        var ta = gradioApp().querySelector('#img2img_prompt textarea');
        if (ta) {
            ta.value = x;
            ta.dispatchEvent(new Event('input', { bubbles: true }));
        }
        var tab = gradioApp().querySelector('#tabs button:nth-child(2)'); 
        if (tab) tab.click();
    } catch (e) { console.error(e); }
    return x;
}
"""

# --- File Paths ---
def get_paths():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return {
        "tags": os.path.join(base_dir, "data", "tags.json"),
        "saved": os.path.join(base_dir, "data", "saved_prompts.json")
    }

# --- Data Loading ---
def load_data(file_type="tags"):
    paths = get_paths()
    path = paths[file_type]
    
    if not os.path.exists(path):
        if file_type == "saved": return {} # 保存ファイルがない場合は空の辞書を返す
        print(f"[RandomGen Error] File not found: {path}")
        return None
        
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"[RandomGen Error] Failed to load {file_type}: {e}")
        return {} if file_type == "saved" else None

# --- Generation Logic ---
def generate_prompt_logic(gen_mode, clothing_mode, is_nsfw, is_extreme, use_quality):
    try:
        data = load_data("tags")
        if not data: return "Error: Could not load data/tags.json."

        prompts = []

        # 1. Appearance
        if "appearance" in data:
            app = data["appearance"]
            if "hair_texture" in app: prompts.append(random.choice(app["hair_texture"]))
            if "hair" in app: prompts.append(random.choice(app["hair"]))
            if "eyes" in app: prompts.append(random.choice(app["eyes"]))
            if "body" in app: prompts.append(random.choice(app["body"]))
            
            # Expressions
            if "expressions" in app:
                expr_list = list(app["expressions"]["sfw"])
                if is_nsfw: expr_list += app["expressions"]["nsfw"]
                if is_extreme: expr_list += app["expressions"]["extreme"]
                prompts.append(random.choice(expr_list))
            
            # Clothing
            if clothing_mode == "Full Set (全身セット)":
                clothes_list = list(app["clothes_sets"]["sfw"])
                if is_nsfw: clothes_list += app["clothes_sets"]["nsfw"]
                if is_extreme: clothes_list += app["clothes_sets"]["extreme"]
                prompts.append(random.choice(clothes_list))
            else: # Mix & Match
                separates = app["separates"]
                for part in ["tops", "bottoms", "underwear"]:
                    part_list = list(separates[part]["sfw"])
                    if is_nsfw: part_list += separates[part]["nsfw"]
                    if is_extreme: part_list += separates[part]["extreme"]
                    prompts.append(random.choice(part_list))

            if "accessories" in app: prompts.append(random.choice(app["accessories"]))

        # 2. Situation
        allowed_levels = ["sfw"]
        if is_nsfw: allowed_levels.append("nsfw")
        if is_extreme: allowed_levels.append("extreme")

        valid_situations = [s for s in data["situations"] if s.get("nsfw_level", "sfw") in allowed_levels]
        if not valid_situations:
            situation = {"tags": "simple background", "poses": ["standing"]}
        else:
            situation = random.choice(valid_situations)

        prompts.append(situation["tags"])

        if gen_mode == "Context-Aware (状況に合わせる)":
            prompts.append(random.choice(situation["poses"]))
        else:
            prompts.append(random.choice(data["random_poses"]))

        # 3. Finalize
        unique_prompts = []
        seen = set()
        for p in prompts:
            if p not in seen:
                unique_prompts.append(p)
                seen.add(p)

        final_prompt = ", ".join(unique_prompts)
        if use_quality:
            final_prompt = data["quality_tags"] + ", " + final_prompt

        return final_prompt

    except Exception as e:
        traceback.print_exc()
        return f"Error: {str(e)}"

# --- Save/Load Logic ---
def save_prompt_action(name, prompt):
    if not name or not prompt:
        return gr.update(), "Error: Name or Prompt is empty."
    
    saved_data = load_data("saved")
    saved_data[name] = prompt
    
    paths = get_paths()
    with open(paths["saved"], "w", encoding="utf-8") as f:
        json.dump(saved_data, f, indent=2, ensure_ascii=False)
    
    # Dropdownのリストを更新して返す
    return gr.update(choices=list(saved_data.keys())), f"Saved: {name}"

def load_prompt_action(selected_name):
    saved_data = load_data("saved")
    if selected_name in saved_data:
        return saved_data[selected_name]
    return ""

def refresh_saved_list():
    saved_data = load_data("saved")
    return gr.update(choices=list(saved_data.keys()))

# --- UI Construction ---
def on_ui_tabs():
    try:
        # Load initial data for quality tags
        data = load_data("tags")
        quality_default = data["quality_tags"] if data else ""
        
        # Load initial saved prompts
        saved_data = load_data("saved")
        saved_choices = list(saved_data.keys()) if saved_data else []

        with gr.Blocks(analytics_enabled=False) as ui_component:
            with gr.Row():
                # --- Left Column: Controls ---
                with gr.Column(scale=1, min_width=300):
                    gr.Markdown("### 🎲 Random Prompt Generator v1.6")
                    
                    with gr.Group():
                        gen_mode_radio = gr.Radio(["Context-Aware (状況に合わせる)", "Random Chaos (完全ランダム)"], label="Pose Mode", value="Context-Aware (状況に合わせる)")
                        clothing_mode_radio = gr.Radio(["Full Set (全身セット)", "Mix & Match (パーツ別ランダム)"], label="Clothing Mode", value="Full Set (全身セット)")
                        with gr.Row():
                            nsfw_checkbox = gr.Checkbox(label="🔞 Allow NSFW", value=False)
                            extreme_checkbox = gr.Checkbox(label="🔥 Extreme", value=False)
                        quality_checkbox = gr.Checkbox(label="Add Quality Tags", value=True)
                    
                    btn_gen = gr.Button("🎲 Generate Prompt", variant="primary", size="lg")
                    
                    gr.Markdown("---")
                    gr.Markdown("#### 💾 Save & Load")
                    with gr.Group():
                        saved_dropdown = gr.Dropdown(label="Load Saved Prompt", choices=saved_choices)
                        save_name = gr.Textbox(label="Save Name", placeholder="Enter name here...")
                        btn_save = gr.Button("Save Current Prompt")
                        save_status = gr.Markdown("")

                # --- Right Column: Output & Tools ---
                with gr.Column(scale=2):
                    output_box = gr.Textbox(label="Result Prompt", lines=6, interactive=True, show_copy_button=True)
                    
                    gr.Markdown("#### 🚀 Quick Send")
                    with gr.Row():
                        btn_send_txt = gr.Button("👉 Send to txt2img")
                        btn_send_img = gr.Button("👉 Send to img2img")
                    
                    with gr.Accordion("🛠 Manual Tools", open=False):
                        btn_add_quality = gr.Button("Add Quality Tags manually")
                        tag_analysis = gr.JSON(label="Tags Analysis")
                        btn_analyze = gr.Button("Analyze Tags")

            # --- Event Handlers ---
            
            # Generate
            btn_gen.click(
                fn=generate_prompt_logic,
                inputs=[gen_mode_radio, clothing_mode_radio, nsfw_checkbox, extreme_checkbox, quality_checkbox],
                outputs=[output_box]
            )

            # Send to buttons (Using JavaScript)
            btn_send_txt.click(fn=None, inputs=[output_box], outputs=None, _js=JS_SEND_TXT)
            btn_send_img.click(fn=None, inputs=[output_box], outputs=None, _js=JS_SEND_IMG)

            # Save
            btn_save.click(
                fn=save_prompt_action,
                inputs=[save_name, output_box],
                outputs=[saved_dropdown, save_status]
            )

            # Load
            saved_dropdown.change(
                fn=load_prompt_action,
                inputs=[saved_dropdown],
                outputs=[output_box]
            )

            # Manual Tools
            def add_quality_tags(current_text):
                return quality_default + ", " + current_text
            btn_add_quality.click(fn=add_quality_tags, inputs=[output_box], outputs=[output_box])

            def analyze_tags(text):
                tags = [t.strip() for t in text.split(",")]
                return {"count": len(tags), "tags": tags}
            btn_analyze.click(fn=analyze_tags, inputs=[output_box], outputs=[tag_analysis])

        return [(ui_component, "Random Gen", "random_gen_tab")]
        
    except Exception as e:
        print(f"[RandomGen Error] UI Creation Failed: {e}")
        traceback.print_exc()
        return []

script_callbacks.on_ui_tabs(on_ui_tabs)
