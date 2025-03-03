import time
import os
import pyautogui
import numpy as np

from tools.utils import encode_image, log_output, extract_python_code
from tools.serving.api_providers import anthropic_completion, openai_completion, gemini_completion

def worker_tetris(
    thread_id,
    offset,
    system_prompt,
    api_provider,
    model_name,
    plan_seconds,
):
    """
    A single Tetris worker that plans moves for 'plan_seconds'.
    1) Sleeps 'offset' seconds before starting (to stagger starts).
    2) Continuously:
        - Captures a screenshot
        - Calls the LLM with a Tetris prompt that includes 'plan_seconds'
        - Extracts the Python code from the LLM output
        - Executes the code with `exec()`
    """
    all_response_time = []

    time.sleep(offset)
    print(f"[Thread {thread_id}] Starting after {offset}s delay... (Plan: {plan_seconds} seconds)")

    tetris_prompt = f"""
Analyze the current Tetris board state and generate PyAutoGUI code to control Tetris 
for the next {plan_seconds} second(s). You can move left/right, rotate pieces. Focus on clearing lines and avoiding 
stacking that would cause a top-out.

At the time the code is executed, 3~5 seconds have elapsed. The game might have moved on to the next block if the stack is high.

However, in your code, consider only the current block or the next block.

The speed it drops is at around ~0.75s/grid bock.

### General Tetris Controls (example keybinds):
- left: move piece left
- right: move piece right
- up: rotate piece clockwise
- down: accelerated drop （if necessary)

### Strategies and Caveats:
1. If the stack is high, most likely you are controlling the "next" block due to latency.
2. Prioritize keeping the stack flat. Balance the two sides.
3. Consider shapes ahead of time. DO NOT rotate and quickly move the block again once it's position is decided.
4. Avoid creating holes.
5. If you see a chance to clear lines, rotate and move the block to correct positions.
6. Plan for your next piece as well, but do not top out.
7. The entire sequence of key presses should be feasible within {plan_seconds} second(s).

### Output Format:
- Output ONLY the Python code for PyAutoGUI commands, e.g. `pyautogui.press("left")`.
- Include brief comments for each action.
- Do not print anything else besides these Python commands.
    """

    try:
        while True:
            # Capture the screen
            screen_width, screen_height = pyautogui.size()
            # 调整截图区域以更好地捕捉游戏窗口
            window_width = 800   # 游戏窗口宽度
            window_height = 750  # 游戏窗口高度
            x = (screen_width - window_width) // 2
            y = (screen_height - window_height) // 2
            region = (x, y, window_width, window_height)
            screenshot = pyautogui.screenshot(region=region)

            # Create a unique folder for this thread's cache
            thread_folder = f"cache/tetris/thread_{thread_id}"
            os.makedirs(thread_folder, exist_ok=True)

            screenshot_path = os.path.join(thread_folder, "screenshot.png")
            screenshot.save(screenshot_path)

            # Encode the screenshot
            base64_image = encode_image(screenshot_path)

            start_time = time.time()
            if api_provider == "anthropic":
                generated_code_str = anthropic_completion(system_prompt, model_name, base64_image, tetris_prompt)
            elif api_provider == "openai":
                generated_code_str = openai_completion(system_prompt, model_name, base64_image, tetris_prompt)
            elif api_provider == "gemini":
                generated_code_str = gemini_completion(system_prompt, model_name, base64_image, tetris_prompt)
            else:
                raise NotImplementedError(f"API provider: {api_provider} is not supported.")

            end_time = time.time()
            latency = end_time - start_time
            all_response_time.append(latency)

            print(f"[Thread {thread_id}] Request latency: {latency:.2f}s")
            avg_latency = np.mean(all_response_time)
            print(f"[Thread {thread_id}] Latencies: {all_response_time}")
            print(f"[Thread {thread_id}] Average latency: {avg_latency:.2f}s\n")

            print(f"[Thread {thread_id}] --- API output ---\n{generated_code_str}\n")

            # Extract Python code for execution
            clean_code = extract_python_code(generated_code_str)
            log_output(thread_id, f"[Thread {thread_id}] Python code to be executed:\n{clean_code}\n")
            print(f"[Thread {thread_id}] Python code to be executed:\n{clean_code}\n")

            try:
                exec(clean_code)
            except Exception as e:
                print(f"[Thread {thread_id}] Error executing code: {e}")

    except KeyboardInterrupt:
        print(f"[Thread {thread_id}] Interrupted by user. Exiting...")
