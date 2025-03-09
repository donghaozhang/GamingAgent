# Using Qwen VL with ModelScope

Based on our testing, it appears that there might be limitations with using Qwen VL models through OpenRouter, especially for image analysis tasks. As mentioned in the Qwen documentation, using ModelScope directly is recommended for users in mainland China.

## Installation Guide

For the best experience with Qwen VL through ModelScope, follow these detailed installation steps:

### Method 1: Quick Install (All Dependencies)

```bash
# Install all required packages
pip install modelscope transformers accelerate pillow torch torchvision opencv-python protobuf sentencepiece
```

### Method 2: Using Requirements File

We've provided a requirements file with all necessary dependencies.

```bash
# Clone this repository if you haven't already
git clone https://github.com/donghaozhang/GamingAgent.git
cd GamingAgent

# Install from requirements file
pip install -r qwen_requirements.txt
```

### Method 3: Install ModelScope From Source (if you encounter issues)

If you encounter import errors with the standard installation, try installing from source:

```bash
pip install git+https://github.com/modelscope/modelscope.git
pip install transformers accelerate pillow torch torchvision
```

## Using Qwen VL with ModelScope

Once you have installed all dependencies, you can use our script:

```bash
python qwen_modelscope.py --image path/to/your/image.jpg --prompt "What is shown in this image?"
```

Or use the following Python code to interact with Qwen VL directly:

```python
from modelscope import snapshot_download
from modelscope.utils.constant import Tasks
from modelscope.pipelines import pipeline
import torch

# Download the model (happens once)
model_dir = snapshot_download('qwen/Qwen-VL-Chat', revision='v1.0.0')

# Create the pipeline
pipe = pipeline(
    task=Tasks.visual_question_answering,
    model=model_dir,
    device='cuda' if torch.cuda.is_available() else 'cpu'
)

# VQA example
image_path = 'path/to/your/image.jpg'
question = 'What is shown in this image?'
result = pipe({
    'image': image_path,
    'text': question
})
print(result['response'])
```

## Troubleshooting

If you encounter issues with ModelScope or Qwen:

1. **Import Errors**:
   - Make sure all dependencies are installed
   - Try installing from source (Method 3 above)
   - Check for version conflicts between packages

2. **CUDA Errors**:
   - Ensure your PyTorch version matches your CUDA version
   - Try running on CPU by setting `device='cpu'`

3. **Download Issues**:
   - Check your internet connection
   - Use a VPN if needed for access to model repositories
   - Try downloading the model manually from ModelScope website

4. **Memory Issues**:
   - Reduce batch size or use a smaller model
   - Free up GPU memory by closing other applications
   - Consider using CPU if your GPU has limited memory

## Format for Sending Images

For ModelScope, you can directly pass the path to your image in the pipeline. For other APIs, the following formats are supported:

```python
# Local file path
messages = [
    {
        "role": "user",
        "content": [
            {"type": "image", "image": "file:///path/to/your/image.jpg"},
            {"type": "text", "text": "Describe this image."},
        ],
    }
]

# Image URL
messages = [
    {
        "role": "user",
        "content": [
            {"type": "image", "image": "http://path/to/your/image.jpg"},
            {"type": "text", "text": "Describe this image."},
        ],
    }
]

# Base64 encoded image
messages = [
    {
        "role": "user",
        "content": [
            {"type": "image", "image": "data:image;base64,/9j/..."},
            {"type": "text", "text": "Describe this image."},
        ],
    }
]
```

## Resources

- [Qwen VL Documentation](https://github.com/QwenLM/Qwen-VL)
- [ModelScope Documentation](https://modelscope.cn/models/qwen/Qwen-VL-Chat/summary)
- [ModelScope GitHub](https://github.com/modelscope/modelscope) 