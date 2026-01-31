#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "google-generativeai>=0.7.0",
#     "pillow>=10.0.0",
# ]
# ///
"""
Generate images using Google's Nano Banana Pro (Gemini 3 Pro Image) API.

Usage:
    uv run generate_image.py --prompt "your image description" --filename "output.png" [--resolution 1K|2K|4K] [--api-key KEY] [--model MODEL] [--api-endpoint URL]

Multi-image editing (up to 14 images):
    uv run generate_image.py --prompt "combine these images" --filename "output.png" -i img1.png -i img2.png -i img3.png
"""

import argparse
import os
import sys
from pathlib import Path


DEFAULT_MODEL = os.environ.get("OPENCLAW_GEMINI_IMAGE_MODEL") or os.environ.get("GEMINI_IMAGE_MODEL") or "gemini-3-pro-image"
DEFAULT_API_ENDPOINT = os.environ.get("OPENCLAW_GEMINI_API_ENDPOINT") or os.environ.get("GEMINI_API_ENDPOINT")


def get_api_key(provided_key: str | None) -> str | None:
    """Get API key from argument first, then environment."""
    if provided_key:
        return provided_key
    return os.environ.get("GEMINI_API_KEY") or os.environ.get("OPENCLAW_LOCAL_GEMINI_KEY")


def get_api_endpoint(provided_endpoint: str | None) -> str | None:
    """Get API endpoint from argument first, then environment."""
    if provided_endpoint:
        return provided_endpoint
    return DEFAULT_API_ENDPOINT


def get_model_name(provided_model: str | None) -> str:
    """Get model name from argument first, then environment."""
    if provided_model:
        return provided_model
    return DEFAULT_MODEL


def main():
    parser = argparse.ArgumentParser(
        description="Generate images using Nano Banana Pro (Gemini 3 Pro Image)"
    )
    parser.add_argument(
        "--prompt", "-p",
        required=True,
        help="Image description/prompt"
    )
    parser.add_argument(
        "--filename", "-f",
        required=True,
        help="Output filename (e.g., sunset-mountains.png)"
    )
    parser.add_argument(
        "--input-image", "-i",
        action="append",
        dest="input_images",
        metavar="IMAGE",
        help="Input image path(s) for editing/composition. Can be specified multiple times (up to 14 images)."
    )
    parser.add_argument(
        "--resolution", "-r",
        choices=["1K", "2K", "4K"],
        default="1K",
        help="Output resolution: 1K (default), 2K, or 4K"
    )
    parser.add_argument(
        "--api-key", "-k",
        help="Gemini API key (overrides GEMINI_API_KEY env var)"
    )
    parser.add_argument(
        "--api-endpoint",
        help="Override Gemini API endpoint (e.g., http://127.0.0.1:8045)"
    )
    parser.add_argument(
        "--model",
        help=f"Model name (default: {DEFAULT_MODEL})"
    )

    args = parser.parse_args()

    # Get API key
    api_key = get_api_key(args.api_key)
    if not api_key:
        print("Error: No API key provided.", file=sys.stderr)
        print("Please either:", file=sys.stderr)
        print("  1. Provide --api-key argument", file=sys.stderr)
        print("  2. Set GEMINI_API_KEY environment variable", file=sys.stderr)
        sys.exit(1)

    model_name = get_model_name(args.model)
    api_endpoint = get_api_endpoint(args.api_endpoint)

    # Import here after checking API key to avoid slow import on error
    import google.generativeai as genai
    from google.generativeai import types
    from PIL import Image as PILImage

    # Initialise client
    if api_endpoint:
        genai.configure(
            api_key=api_key,
            transport="rest",
            client_options={"api_endpoint": api_endpoint},
        )
    else:
        genai.configure(api_key=api_key)
    model = genai.GenerativeModel(model_name)

    # Set up output path
    output_path = Path(args.filename)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Load input images if provided (up to 14 supported by Nano Banana Pro)
    input_images = []
    output_resolution = args.resolution
    if args.input_images:
        if len(args.input_images) > 14:
            print(f"Error: Too many input images ({len(args.input_images)}). Maximum is 14.", file=sys.stderr)
            sys.exit(1)

        max_input_dim = 0
        for img_path in args.input_images:
            try:
                img = PILImage.open(img_path)
                input_images.append(img)
                print(f"Loaded input image: {img_path}")

                # Track largest dimension for auto-resolution
                width, height = img.size
                max_input_dim = max(max_input_dim, width, height)
            except Exception as e:
                print(f"Error loading input image '{img_path}': {e}", file=sys.stderr)
                sys.exit(1)

        # Auto-detect resolution from largest input if not explicitly set
        if args.resolution == "1K" and max_input_dim > 0:  # Default value
            if max_input_dim >= 3000:
                output_resolution = "4K"
            elif max_input_dim >= 1500:
                output_resolution = "2K"
            else:
                output_resolution = "1K"
            print(f"Auto-detected resolution: {output_resolution} (from max input dimension {max_input_dim})")

    # Build contents (images first if editing, prompt only if generating)
    prompt = args.prompt
    if output_resolution:
        prompt = f"{prompt}\n\nOutput resolution: {output_resolution}."
    if input_images:
        contents = [*input_images, prompt]
        img_count = len(input_images)
        print(f"Processing {img_count} image{'s' if img_count > 1 else ''} with resolution {output_resolution}...")
    else:
        contents = prompt
        print(f"Generating image with resolution {output_resolution}...")

    try:
        response = model.generate_content(
            contents,
            generation_config=types.GenerationConfig(response_mime_type="image/png"),
        )

        # Process response and convert to PNG
        image_saved = False
        parts = []
        if getattr(response, "parts", None):
            parts.extend(response.parts)
        if getattr(response, "candidates", None):
            for candidate in response.candidates:
                content = getattr(candidate, "content", None)
                if content and getattr(content, "parts", None):
                    parts.extend(content.parts)

        last_error: Exception | None = None
        for part in parts:
            # Prefer inline_data: some SDK parts include empty text even when inline_data is present.
            if getattr(part, "inline_data", None) is not None:
                # Convert inline data to PIL Image and save as PNG
                from io import BytesIO

                # inline_data.data is already bytes, not base64
                image_data = part.inline_data.data
                if not image_data:
                    continue
                if isinstance(image_data, str):
                    # If it's a string, it might be base64
                    import base64
                    image_data = base64.b64decode(image_data)

                try:
                    image = PILImage.open(BytesIO(image_data))

                    # Ensure RGB mode for PNG (convert RGBA to RGB with white background if needed)
                    if image.mode == 'RGBA':
                        rgb_image = PILImage.new('RGB', image.size, (255, 255, 255))
                        rgb_image.paste(image, mask=image.split()[3])
                        rgb_image.save(str(output_path), 'PNG')
                    elif image.mode == 'RGB':
                        image.save(str(output_path), 'PNG')
                    else:
                        image.convert('RGB').save(str(output_path), 'PNG')
                    image_saved = True
                    break
                except Exception as e:
                    last_error = e
                    continue
            elif getattr(part, "text", None):
                print(f"Model response: {part.text}")

        if image_saved:
            full_path = output_path.resolve()
            print(f"\nImage saved: {full_path}")
            # OpenClaw parses MEDIA tokens and will attach the file on supported providers.
            print(f"MEDIA: {full_path}")
        else:
            print("Error: No image was generated in the response.", file=sys.stderr)
            if last_error is not None:
                print(f"Last error: {last_error}", file=sys.stderr)
            if getattr(response, "candidates", None):
                print(response.candidates, file=sys.stderr)
            sys.exit(1)

    except Exception as e:
        print(f"Error generating image: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
