import os
import json
import base64
import argparse

from openai import OpenAI
from typing import List, Dict, Any, Tuple, Optional

from playwright.sync_api import Page, sync_playwright
# from xvfbwrapper import Xvfb

class QwenVLClient:
    """
    Handles communication with the Qwen-VL model and executes browser actions.
    This class acts as the 'worker' in the Orchestrator-Worker pattern.
    """
    
    def __init__(self, model: str, endpoint: str, api_key: str):
        """Initializes the client to communicate with the Qwen model."""
        self.model = model
        self.client = OpenAI(api_key=api_key, base_url=endpoint)
    
    def get_response(self, screenshot_base64: str, task: str, url: str, trajectory: List, failure_info: Optional[str] = None) -> str:
        """
        Constructs a prompt and gets a response from the Qwen-VL model.
        This version includes a comprehensive guide for solving various CAPTCHA types.
        """

        system_prompt = """
        You are an expert web agent designed to navigate the web and overcome human verification challenges (CAPTCHAs).
        Analyze the user's goal, the current screenshot, and the action history to determine the next best action.

        ## CAPTCHA Solving Guide
        If you encounter a page that seems to be a CAPTCHA, follow these strategies:

        1.  **Image Selection ("Select all images with...")**:
            -   **Strategy**: First, in your <think> tag, clearly identify the target object (e.g., "bicycles", "traffic lights"). Then, execute a series of `click` actions, one for each image square that contains the target object. Do not try to click all images in a single action.
            -   **Example Thought**: <think>This is an image selection CAPTCHA. The target is 'bicycles'. I will click on the three squares containing bicycles one by one.</think>
            -   **Example Action**: {"action": "click", "parameters": {"x": 150, "y": 250, "comment": "Clicking the first bicycle image"}}

        2.  **Slider Puzzle / Drag and Drop**:
            -   **Strategy**: Identify the starting coordinates of the puzzle piece and the coordinates of the target location where it should be dropped. Use the `drag_and_drop` action.
            -   **Example Thought**: <think>This is a slider puzzle. I need to drag the piece from (200, 450) to the empty spot at (550, 450).</think>
            -   **Example Action**: {"action": "drag_and_drop", "parameters": {"source_x": 200, "source_y": 450, "target_x": 550, "target_y": 450, "comment": "Solving the slider puzzle"}}

        3.  **"I'm not a robot" Checkbox**:
            -   **Strategy**: This is the simplest form. Just use a single `click` action on the checkbox.
            -   **Example Action**: {"action": "click", "parameters": {"x": 250, "y": 400, "comment": "Clicking the 'I'm not a robot' checkbox"}}

        4.  **Distorted Text Input**:
            -   **Strategy**: Carefully read the distorted characters in the image. Use the `type` action to enter the text into the input field.
            -   **Example Thought**: <think>The distorted text appears to be 'k3m7p'. I will type this into the text box.</think>
            -   **Example Action**: {"action": "type", "parameters": {"text": "k3m7p", "comment": "Entering the text from the CAPTCHA image"}}

        ## Action Space
        You MUST choose one of the following actions. Pay close attention to the required parameters.

        1.  `click` (For buttons, links, and image selections)
            - `parameters`: `x` (int, required), `y` (int, required), `comment` (str, optional)
        2.  `type` (For text input fields)
            - `parameters`: `text` (str, required), `comment` (str, optional)
        3.  `scroll` (For scrolling the page)
            - `parameters`: `direction` (str, required, "up" or "down"), `comment` (str, optional)
        4.  `drag_and_drop` (For slider puzzles)
            - `parameters`: `source_x` (int, required), `source_y` (int, required), `target_x` (int, required), `target_y` (int, required), `comment` (str, optional)
        5.  `finish` (When the final goal is achieved)
            - `parameters`: `comment` (str, required)

        ## Response Format
        First, provide your reasoning in a `<think>` tag. Then, output a single, clean JSON object for your chosen action.
        """

        history_str = "\n".join(f"{i}: Executed {item['action']}" for i, item in enumerate(trajectory))
        
        user_prompt_content = f"""
        User Task: "{task}"
        Current URL: {url}
        Previous Actions:
        {history_str if history_str else "None"}
        """
        
        if failure_info:
            user_prompt_content += f"\nIMPORTANT: Your last action failed with the error: '{failure_info}'. This might be because you are facing a CAPTCHA. Re-examine the screenshot, consult the CAPTCHA Solving Guide, and devise a new plan."

        messages = [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": user_prompt_content},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{screenshot_base64}"}}
                ]
            }
        ]
        
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            max_tokens=1024,
            temperature=0.0,
        )
        return response.choices[0].message.content
    
    def parse_response(self, response_text: str) -> [Tuple, str]:
        """
        Parses the model's response to extract the <think> content and the action JSON.
        """
        if not response_text:
            return None, ""

        think_content = ""
        if "<think>" in response_text and "</think>" in response_text:
            start = response_text.find("<think>") + len("<think>")
            end = response_text.find("</think>")
            think_content = response_text[start:end].strip()

        json_part = response_text
        if "{" in response_text:
            json_start = response_text.find("{")
            json_end = response_text.rfind("}") + 1
            json_part = response_text[json_start:json_end]
        
        try:
            action_json = json.loads(json_part)
            return action_json, think_content
        except json.JSONDecodeError:
            print(f"Failed to decode JSON from model response: {json_part}")
            return None, think_content
    
    def execute_action(self, action_data: Dict, page: Page) -> str:
        """
        Executes the action determined by the model, now including a 'drag_and_drop' action.
        """
        if not action_data:
            raise ValueError("Action data is None.")

        action_name = action_data.get("action")
        params = action_data.get("parameters", {})

        print(f"Executing action '{action_name}' with params {params}")

        if action_name == "click":
            if 'x' not in params or 'y' not in params:
                raise ValueError("Action 'click' is missing required parameters: 'x' or 'y'.")
            page.mouse.click(params['x'], params['y'])

        elif action_name == "type":
            if 'text' not in params:
                raise ValueError("Action 'type' is missing required parameter: 'text'.")
            page.keyboard.type(params['text'], delay=100)
            page.keyboard.press('Enter')

        elif action_name == "scroll":
            if 'direction' not in params:
                raise ValueError("Action 'scroll' is missing required parameter: 'direction'.")
            direction = params['direction']
            if direction not in ['up', 'down']:
                raise ValueError(f"Invalid scroll direction: '{direction}'. Must be 'up' or 'down'.")
            delta_y = 500 if direction == 'down' else -500
            page.mouse.wheel(0, delta_y)

        elif action_name == "drag_and_drop":
            if not all(k in params for k in ['source_x', 'source_y', 'target_x', 'target_y']):
                raise ValueError("Action 'drag_and_drop' is missing required coordinate parameters.")
            
            # Simulate a drag-and-drop action
            page.mouse.move(params['source_x'], params['source_y'])
            page.mouse.down()
            # Move to the target with a few steps to appear more human-like
            page.mouse.move(params['target_x'], params['target_y'], steps=5) 
            page.mouse.up()
            
        elif action_name == "finish":
            return "finish"
            
        else:
            raise ValueError(f"Unknown or improperly formatted action: {action_name}")
        
        # Action succeeded, wait for the page to stabilize.
        page.wait_for_timeout(3000) # Increased timeout for CAPTCHA verification
        return "continue"

def browse(
    start_url: str, 
    task: str, 
    model: str,
    endpoint: str,
    api_key: str,
    max_steps: int = 30,
) -> List:
    """
    Perform web browsing session. This function is the 'Orchestrator'.
    """
    qwen_client = QwenVLClient(model, endpoint, api_key)
    trajectory = []
    failure_reason = None
    is_finished = False

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False) # Set to True for no GUI
        page = browser.new_page(viewport={'width': 1280, 'height': 800})
        
        try:
            page.goto(start_url, wait_until="domcontentloaded")

            for step in range(1, max_steps + 1):
                if is_finished:
                    break
                
                print(f"\n--- Step {step}/{max_steps} ---")
                
                try:
                    page.wait_for_load_state("domcontentloaded", timeout=10000)
                    screenshot_bytes = page.screenshot(type="jpeg", quality=80)
                    screenshot_base64 = base64.b64encode(screenshot_bytes).decode('utf-8')

                    response_text = qwen_client.get_response(screenshot_base64, task, page.url, trajectory, failure_reason)
                    failure_reason = None # Reset after using it

                    action_json, think_process = qwen_client.parse_response(response_text)
                    if not action_json:
                        raise ValueError("Failed to parse a valid action from the model's response.")

                    action_result_str = json.dumps(action_json)
                    trajectory.append({
                        "step": step,
                        "screenshot": screenshot_base64,
                        "think": think_process,
                        "action": action_result_str
                    })

                    status = qwen_client.execute_action(action_json, page)
                    if status == "finish":
                        print("Task finished successfully.")
                        is_finished = True

                except Exception as e:
                    print(f"An error occurred in step {step}: {e}")
                    failure_reason = str(e) # This implements the Evaluator-Optimizer feedback loop
                    # Log the failure and continue to the next step to allow self-correction
                    if 'screenshot_base64' not in locals():
                        screenshot_bytes = page.screenshot(type="jpeg", quality=80)
                        screenshot_base64 = base64.b64encode(screenshot_bytes).decode('utf-8')
                    
                    trajectory.append({
                        "step": step,
                        "screenshot": screenshot_base64,
                        "think": f"Action failed with error: {e}",
                        "action": f'{{"action": "error", "parameters": {{"message": "{str(e)}"}} }}'
                    })
        
        finally:
            if not is_finished:
                print("Max steps reached. Task may be incomplete.")
            browser.close()
    
    return trajectory

def save_results(url: str, task: str, trajectory: List, output_file: str):
    """Saves the browsing session trajectory to a JSON file."""
    output_data = {
        "url": url,
        "task": task,
        "trajectory": trajectory
    }
    with open(output_file, 'w') as f:
        json.dump(output_data, f, indent=2)
    print(f"Trajectory saved to {output_file}")

def parse_arguments() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description='Web browsing agent using Qwen-VL')
    parser.add_argument('--url', type=str, required=True, help='Starting URL for the browsing session')
    parser.add_argument('--task', type=str, required=True, help='Task description/intent for the agent')
    parser.add_argument('--output', type=str, default='output.json', help='Output file path for results (default: results.json)')
    parser.add_argument('--max-steps', type=int, default=30, help='Maximum number of browsing steps (default: 30)')
    parser.add_argument('--model', type=str, default='Qwen/Qwen2.5-VL-72B-Instruct-AWQ', help='Model to use for the agent')
    parser.add_argument('--endpoint', type=str, required=True, help='API endpoint for model inference')
    
    return parser.parse_args()

def main() -> None:
    """Main entry point."""
    args = parse_arguments()
    api_key = os.getenv("OPENAI_API_KEY", "dummy-key")

    # vdisplay = Xvfb()
    # vdisplay.start()
    
    trajectory = []
    try:
        trajectory = browse(
            start_url=args.url,
            task=args.task,
            model=args.model,
            endpoint=args.endpoint,
            api_key=api_key,
            max_steps=args.max_steps,
        )
    except Exception as e:
        print(f"A critical error occurred during the browsing session: {e}")
    finally:
        save_results(args.url, args.task, trajectory, args.output)
    #     vdisplay.stop()

if __name__ == "__main__":
    main()