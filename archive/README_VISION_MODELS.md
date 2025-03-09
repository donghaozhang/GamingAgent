# Vision Models for Image Analysis

This README provides guidance on vision model options for image analysis in the Gaming Agent project.

## Understanding the Qwen Issue

We've encountered issues with Qwen VL models through OpenRouter:

1. **Error Issues**: Attempts to use Qwen models (`qwen/qwen2.5-vl-72b-instruct` and `qwen/qwen-vl-max`) resulted in errors:
   - Either a `'NoneType' object is not subscriptable` error
   - Or a response saying the model can't see any images

2. **Possible Causes**:
   - OpenRouter may have limitations with how it handles images for Qwen models
   - The image format or URL implementation might not be compatible with Qwen through OpenRouter
   - API changes or limitations with the free tier access

## Recommended Alternatives

### 1. Claude 3 Vision Models (via OpenRouter)

The script `qwen_success_only.py` demonstrates using Claude 3 Sonnet for vision tasks through OpenRouter.

```bash
python qwen_success_only.py
```

Claude 3 models generally provide excellent vision capabilities and are more likely to work properly through OpenRouter.

### 2. Gemini Pro Vision (via OpenRouter)

The script `gemini_vision.py` demonstrates using Google's Gemini Pro Vision through OpenRouter.

```bash
python gemini_vision.py
```

### 3. Gemini Pro Vision (Direct API)

The most reliable option is to use Gemini directly via Google's API as demonstrated in `gemini_direct.py`:

```bash
python gemini_direct.py
```

**Requirements**:
- Get a Google API key from: https://makersuite.google.com/app/apikey
- Add the key to your `.env` file as `GOOGLE_API_KEY=your_key_here`

### 4. ModelScope for Qwen (Mainland China)

If you specifically need Qwen models, the best approach is to use ModelScope directly as shown in the separate README (`README_QWEN.md`).

## When to Use Each Option

1. **Use Claude 3**: For general purpose vision tasks with the best quality
2. **Use Gemini via OpenRouter**: If you already have an OpenRouter key and want good vision capabilities
3. **Use Gemini Direct**: For the most reliable approach and if you want deeper control
4. **Use ModelScope**: If you specifically need Qwen models or are in mainland China

## Troubleshooting

If you're experiencing issues with vision models:

1. **Verify API keys**: Ensure your API keys are correctly set in the `.env` file
2. **Check image URLs**: Make sure the image URLs are publicly accessible
3. **Try different formats**: If one model fails, try another to isolate if it's model-specific
4. **Review quotas**: Check if you've hit free tier limits on OpenRouter

## Further Development

If you want to continue using Qwen models with OpenRouter:

1. Contact OpenRouter support to verify how Qwen models handle images
2. Try different image formats and encoding methods
3. Consider OpenRouter's paid tier which might have better support

For most use cases, we recommend using Gemini or Claude models as they have proven more reliable for vision tasks. 