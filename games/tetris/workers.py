import time
import os
import pyautogui
import numpy as np
from queue import Queue

from tools.utils import encode_image, log_output, extract_python_code
from tools.serving.api_providers import anthropic_completion, openai_completion, gemini_completion

# 添加全局变量
game_running = True
game_state = Queue()

def worker_tetris(thread_id, offset, system_prompt, api_provider, model_name, plan_seconds):
    print(f"[Worker {thread_id}] 初始化中...")
    global game_running, game_state
    
    time.sleep(offset)
    print(f"[Thread {thread_id}] Starting after {offset}s delay... (Plan: {plan_seconds} seconds)")
    
    all_response_time = []
    last_state = None

    try:
        while game_running:
            # Capture the screen
            screen_width, screen_height = pyautogui.size()
            window_width = 800
            window_height = 750
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
            print(f"[Thread {thread_id}] Average latency: {avg_latency:.2f}s\n")

            # Extract and execute code
            try:
                clean_code = extract_python_code(generated_code_str)
                log_output(thread_id, f"[Thread {thread_id}] Python code to be executed:\n{clean_code}\n")
                print(f"[Thread {thread_id}] Python code to be executed:\n{clean_code}\n")
                exec(clean_code)
            except Exception as e:
                print(f"[Thread {thread_id}] Error executing code: {e}")

            time.sleep(0.1)  # 控制检查频率

    except KeyboardInterrupt:
        print(f"[Thread {thread_id}] Interrupted by user. Exiting...")
