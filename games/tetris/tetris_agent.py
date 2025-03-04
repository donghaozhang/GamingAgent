import time
import numpy as np
import concurrent.futures
import argparse
import threading
import keyboard  # Add keyboard library for key detection

from games.tetris.workers import worker_tetris

system_prompt = (
    "You are an expert AI agent specialized in playing Tetris gameplay, search for and execute optimal moves given each game state. Prioritize line clearing over speed."
)

def main():
    """
    Spawns a number of short-term and/or long-term Tetris workers based on user-defined parameters.
    Each worker will analyze the Tetris board and choose moves accordingly.
    """
    parser = argparse.ArgumentParser(
        description="Tetris gameplay agent with configurable concurrent workers."
    )
    parser.add_argument("--api_provider", type=str, default="anthropic",
                        help="API provider to use.")
    parser.add_argument("--model_name", type=str, default="claude-3-7-sonnet-20250219",
                        help="Model name.")
    parser.add_argument("--concurrency_interval", type=float, default=1,
                        help="Interval in seconds between workers.")
    parser.add_argument("--api_response_latency_estimate", type=float, default=5,
                        help="Estimated API response latency in seconds.")
    parser.add_argument("-control_time", type=float, default=4,
                        help=" orker control time.")
    parser.add_argument("--policy", type=str, default="fixed", 
                        choices=["fixed"],
                        help="Worker policy")

    args = parser.parse_args()

    worker_span = args.control_time + args.concurrency_interval
    num_threads = int(args.api_response_latency_estimate // worker_span)
    
    if args.api_response_latency_estimate % worker_span != 0:
        num_threads += 1
    
    # Create an offset list
    offsets = [i * (args.control_time + args.concurrency_interval) for i in range(num_threads)]

    print(f"Starting with {num_threads} threads using policy '{args.policy}'...")
    print(f"API Provider: {args.api_provider}, Model Name: {args.model_name}")
    print(f"Press 'q' to terminate all threads and exit.")

    # Create an event to signal threads to stop
    stop_event = threading.Event()
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as executor:
        # Submit all worker threads with the stop_event
        futures = []
        for i in range(num_threads):
            if args.policy == "fixed":
                future = executor.submit(
                    worker_tetris, i, offsets[i], system_prompt,
                    args.api_provider, args.model_name, args.control_time, stop_event
                )
                futures.append(future)
            else:
                raise NotImplementedError(f"policy: {args.policy} not implemented.")

        try:
            # Monitor for 'q' key press
            while not stop_event.is_set():
                if keyboard.is_pressed('q'):
                    print("\nQ key pressed. Stopping all threads...")
                    stop_event.set()
                    break
                time.sleep(0.1)  # Short sleep to prevent high CPU usage
                
        except KeyboardInterrupt:
            print("\nMain thread interrupted. Exiting all threads...")
            stop_event.set()
        
        # Wait for all threads to complete
        for future in futures:
            try:
                future.result(timeout=5)  # Give threads up to 5 seconds to finish
            except concurrent.futures.TimeoutError:
                print("Some threads did not terminate gracefully in the timeout period.")
        
        print("All threads terminated. Exiting program.")

if __name__ == "__main__":
    main()