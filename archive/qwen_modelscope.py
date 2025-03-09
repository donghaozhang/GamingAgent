#!/usr/bin/env python
"""
Qwen VL Using ModelScope

This script demonstrates how to use Qwen VL directly through ModelScope,
which is recommended for users in mainland China.

Usage:
    python qwen_modelscope.py --image <path_to_image> --prompt "Your question about the image"

Requirements:
    pip install modelscope transformers accelerate pillow torch torchvision
"""

import os
import sys
import argparse
from PIL import Image
import importlib
import subprocess

def check_dependencies():
    """Check and install dependencies if needed"""
    required_packages = ['modelscope', 'transformers', 'torch', 'pillow', 'accelerate']
    missing_packages = []
    
    for package in required_packages:
        try:
            importlib.import_module(package)
            print(f"✓ {package} is installed")
        except ImportError:
            missing_packages.append(package)
    
    if missing_packages:
        print(f"The following packages are missing: {', '.join(missing_packages)}")
        print("\nInstall missing packages? (y/n)")
        choice = input().lower()
        if choice == 'y':
            for package in missing_packages:
                print(f"Installing {package}...")
                try:
                    subprocess.check_call([sys.executable, "-m", "pip", "install", package])
                    print(f"✓ {package} installed successfully")
                except subprocess.CalledProcessError:
                    print(f"Failed to install {package}. Please install it manually.")
                    print(f"pip install {package}")
                    return False
            
            # Retry imports after installation
            try:
                for package in missing_packages:
                    importlib.import_module(package)
                print("All dependencies now installed.")
                return True
            except ImportError:
                print("Some dependencies failed to import even after installation.")
                print("Please try installing them manually:")
                print("pip install modelscope transformers accelerate pillow torch torchvision")
                return False
        else:
            print("Dependencies required. Please install them manually:")
            print("pip install modelscope transformers accelerate pillow torch torchvision")
            return False
    
    return True

def main():
    """Main function to run Qwen VL with ModelScope"""
    # Parse arguments first so help works without dependencies
    parser = argparse.ArgumentParser(description="Use Qwen VL through ModelScope")
    parser.add_argument("--image", help="Path to the image file")
    parser.add_argument("--prompt", default="What is shown in this image?", 
                      help="Question about the image")
    parser.add_argument("--model", default="qwen/Qwen-VL-Chat", 
                      help="ModelScope model name")
    parser.add_argument("--revision", default="v1.0.0", 
                      help="Model revision/version")
    args = parser.parse_args()
    
    # Check dependencies before proceeding
    if not check_dependencies():
        sys.exit(1)
    
    # Now that dependencies are confirmed, import ModelScope
    try:
        from modelscope import snapshot_download
        from modelscope.utils.constant import Tasks
        from modelscope.pipelines import pipeline
        import torch
    except ImportError as e:
        print(f"Error importing ModelScope packages: {e}")
        print("Please install all required packages with:")
        print("pip install modelscope transformers accelerate pillow torch torchvision")
        sys.exit(1)
    
    # Check if image is provided
    if not args.image:
        print("Error: Image path is required")
        print("Usage: python qwen_modelscope.py --image <path_to_image>")
        sys.exit(1)
    
    # Check if image exists
    if not os.path.exists(args.image):
        print(f"Error: Image file not found: {args.image}")
        sys.exit(1)
    
    # Load image to verify it's valid
    try:
        img = Image.open(args.image)
        print(f"Image loaded successfully: {args.image}")
        print(f"Image size: {img.size}, Mode: {img.mode}")
    except Exception as e:
        print(f"Error loading image: {e}")
        sys.exit(1)
    
    # Check if CUDA is available
    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    print(f"Using device: {device}")
    
    try:
        print(f"Downloading model: {args.model}@{args.revision}")
        print("This may take some time depending on your internet connection...")
        model_dir = snapshot_download(args.model, revision=args.revision)
        print(f"Model downloaded to: {model_dir}")
        
        print("Creating pipeline...")
        pipe = pipeline(
            task=Tasks.visual_question_answering,
            model=model_dir,
            device=device
        )
        
        print(f"Processing image with prompt: {args.prompt}")
        result = pipe({
            'image': args.image,
            'text': args.prompt
        })
        
        print("\n" + "="*60)
        print("Qwen VL Response:")
        print(result['response'])
        print("="*60)
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        print("\nTroubleshooting tips:")
        print("1. Make sure you have the latest versions of all dependencies")
        print("2. Try installing modelscope from source: pip install git+https://github.com/modelscope/modelscope.git")
        print("3. For CUDA errors, ensure your PyTorch version matches your CUDA version")
        print("4. Check your internet connection for model download issues")

if __name__ == "__main__":
    main() 