import modules.scripts as scripts
import gradio as gr
from modules import script_callbacks
import json
import random
import os
import traceback

def load_data():
    try:
        # このスクリプトの位置から2つ上の階層の data/tags.json を探す
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        json_path = os.path.join(base_dir, "data", "tags.json")
        
        if not os.path.exists(json_path):
            print(f"[RandomGen Error] JSON file not found at: {json_path}")
            return None
            
        with open(json_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"[RandomGen Error] Failed to load data: {e}")
        return None

def generate_prompt_logic(gen_mode, clothing_mode, is_nsfw, is_extreme, use_quality):
    try:
        data = load_data()
        if not data:
            return "Error: Could not load data/tags.json. Check console for details."

        prompts = []

        # --- 1. Basic Appearance ---
        # データ内にキーがあるかチェックしてから取得
        if "appearance" in data:
            if "hair_texture" in data["appearance"]:
                prompts.append(random.choice(data["appearance"]["hair_texture"]))
            if "hair" in data["appearance"]:
                prompts.append(random.choice(data["appearance"]["hair"]))
            if "eyes" in data["appearance"]:
                prompts.append(random.choice(data["appearance"]["eyes"]))
            if "body" in data["appearance"]:
                prompts.append(random.choice(data["appearance"]["body"]))
            
            # --- 1.5 Expressions ---
            if "expressions" in data["appearance"]:
                expr_list = list(data["appearance"]["expressions"]["sfw"])
                if is_nsfw: expr_list += data["appearance"]["expressions"]["nsfw"]
                if is_extreme: expr_list += data["appearance"]["expressions"]["extreme"]
                prompts.append(random.choice(expr_list))
            
            # --- 2. Clothing ---
            if clothing_mode == "Full Set (全身セット)":
                clothes_list = list(data["appearance"]["clothes_sets"]["sfw"])
                if is_nsfw: clothes_list += data["appearance"]["clothes_sets"]["nsfw"]
                if is_extreme: clothes_list += data["appearance"]["clothes_sets"]["extreme"]
                prompts.append(random.choice(clothes_list))
            else: # Mix & Match
                separates = data["appearance"]["separates"]
                
                tops_list = list(separates["tops"]["sfw"])
                if is_nsfw: tops_list += separates["tops"]["nsfw"]
                if is_extreme: tops_list += separates["tops"]["extreme"]
                prompts.append(random.choice(tops_list))
                
                bottoms_list = list(separates["bottoms"]["sfw"])
                if is_nsfw: bottoms_list += separates["bottoms"]["nsfw"]
                if is_extreme: bottoms_list += separates["bottoms"]["extreme"]
                prompts.append(random.choice(bottoms_list))
                
                undie_list = list(separates["underwear"]["sfw"])
                if is_nsfw: undie_list += separates["underwear"]["nsfw"]
                if is_extreme: undie_list += separates["underwear"]["extreme"]
                prompts.append(random.choice(undie_list))

            if "accessories" in data["appearance"]:
                prompts.append(random.choice(data["appearance"]["accessories"]))

        # --- 3. Situation & Pose ---
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

        # --- 4. Finalize ---
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
        return f"Error during generation: {str(e)}"

def on_ui_tabs():
    try:
        with gr.Blocks(analytics_enabled=False) as ui_component:
            with gr.Row():
                with gr.Column(scale=1, min_width=300):
                    gr.Markdown("### 🎲 Random Prompt Generator v1.6")
                    with gr.Group():
                        gen_mode_radio = gr.Radio(["Context-Aware (状況に合わせる)", "Random Chaos (完全ランダム)"], label="Pose Mode", value="Context-Aware (状況に合わせる)")
                        clothing_mode_radio = gr.Radio(["Full Set (全身セット)", "Mix & Match (パーツ別ランダム)"], label="Clothing Mode", value="Full Set (全身セット)")
                        with gr.Row():
                            nsfw_checkbox = gr.Checkbox(label="🔞 Allow NSFW", value=False)
                            extreme_checkbox = gr.Checkbox(label="🔥 Extreme", value=False)
                        quality_checkbox = gr.Checkbox(label="Add Quality Tags", value=True)
                    btn_gen = gr.Button("Generate Prompt", variant="primary", size="lg")
                    gr.Markdown("---")
                    btn_add_quality = gr.Button("Add Quality Tags manually")
                with gr.Column(scale=2):
                    output_box = gr.Textbox(label="Result Prompt", lines=6, interactive=True, show_copy_button=True)
                    with gr.Accordion("Tags Breakdown", open=False):
                        tag_analysis = gr.JSON(label="Tags Analysis")
                        btn_analyze = gr.Button("Analyze")

            btn_gen.click(
                fn=generate_prompt_logic,
                inputs=[gen_mode_radio, clothing_mode_radio, nsfw_checkbox, extreme_checkbox, quality_checkbox],
                outputs=[output_box]
            )
            
            def add_quality_tags(current_text):
                data = load_data()
                quality = data["quality_tags"] if data else ""
                return quality + ", " + current_text
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