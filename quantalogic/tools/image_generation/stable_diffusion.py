"""Stable Diffusion Image Generation Tool using AWS Bedrock."""

import base64
import datetime
import json
import os
from pathlib import Path
from typing import Any, Dict, Optional

import boto3
from loguru import logger
from pydantic import BaseModel, ConfigDict, Field

from quantalogic.tools.tool import Tool, ToolArgument


class BedrockStabilityConfig(BaseModel):
    """Configuration for Stable Diffusion XL on AWS Bedrock."""
    
    model_id: str = Field(
        default="stability.stable-diffusion-xl-v1",
        description="The Stability AI model to use"
    )
    cfg_scale: float = Field(
        default=7.0,
        ge=0,
        le=35,
        description="How strictly the diffusion process adheres to the prompt"
    )
    steps: int = Field(
        default=50,
        ge=10,
        le=150,
        description="Number of diffusion steps"
    )
    seed: Optional[int] = Field(
        default=None,
        description="Random seed for reproducibility"
    )
    style_preset: str = Field(
        default="photographic",
        description="The style preset to use"
    )
    width: int = Field(
        default=1024,
        description="Image width"
    )
    height: int = Field(
        default=1024,
        description="Image height"
    )


STABLE_DIFFUSION_CONFIG = {
    "models": [
        "stability.stable-diffusion-xl-v1",
        "stability.stable-diffusion-xl-v0",
        "stability.stable-diffusion-v1"
    ],
    "sizes": [(1024, 1024), (1152, 896), (896, 1152), (1280, 1024), (1536, 1024)],
    "styles": [
        "photographic",
        "digital-art",
        "cinematic",
        "anime",
        "comic-book",
        "pixel-art",
        "enhance",
        "fantasy-art",
        "line-art",
        "analog-film",
        "neon-punk",
        "isometric",
        "low-poly",
        "origami",
        "modeling-compound",
        "3d-model",
        "tile-texture"
    ]
}


class StableDiffusionTool(Tool):
    """Tool for generating images using Stable Diffusion XL on AWS Bedrock."""

    model_config = ConfigDict(arbitrary_types_allowed=True, extra="allow")

    name: str = Field(default="stable_diffusion_tool")
    description: str = Field(
        default=(
            "Generate high-quality images using Stable Diffusion XL on AWS Bedrock. Features:\n"
            "1. Multiple model versions available\n"
            "2. Various artistic style presets\n"
            "3. Configurable image dimensions\n"
            "4. Fine control over generation parameters\n"
            "\nImages are saved locally with metadata."
        )
    )
    arguments: list = Field(
        default=[
            ToolArgument(
                name="prompt",
                arg_type="string",
                description=(
                    "Describe what you want in the image. Tips:\n"
                    "- Be specific about subject, style, lighting\n"
                    "- Use artistic terms and descriptive adjectives\n"
                    "- Mention camera details for photographic looks\n"
                    "- Include mood and atmosphere descriptions"
                ),
                required=True,
                example="A majestic red dragon perched on a crystal mountain peak at sunset, hyperrealistic digital art, dramatic lighting, detailed scales, 8k",
            ),
            ToolArgument(
                name="negative_prompt",
                arg_type="string",
                description="Describe what you don't want in the image",
                required=False,
                default="ugly, deformed, noisy, blurry, distorted, low quality",
                example="ugly, deformed, noisy, blurry, distorted, low quality, duplicate, morbid, mutilated, poorly drawn face",
            ),
            ToolArgument(
                name="model_id",
                arg_type="string",
                description="The Stability AI model version to use",
                required=False,
                default="stability.stable-diffusion-xl-v1",
                example="stability.stable-diffusion-xl-v1",
            ),
            ToolArgument(
                name="size",
                arg_type="string",
                description=(
                    "Image dimensions (width x height). Available options:\n"
                    "1024x1024, 1152x896, 896x1152, 1280x1024, 1536x1024"
                ),
                required=False,
                default="1024x1024",
                example="1024x1024",
            ),
            ToolArgument(
                name="style",
                arg_type="string",
                description=(
                    "Visual style preset. Options:\n"
                    "photographic, digital-art, cinematic, anime, comic-book,\n"
                    "pixel-art, enhance, fantasy-art, line-art, analog-film,\n"
                    "neon-punk, isometric, low-poly, origami, modeling-compound,\n"
                    "3d-model, tile-texture"
                ),
                required=False,
                default="photographic",
                example="digital-art",
            ),
            ToolArgument(
                name="cfg_scale",
                arg_type="float",
                description="How closely to follow the prompt (0-35). Lower = more creative, higher = more precise.",
                required=False,
                default="7.0",
                example="7.0",
            ),
            ToolArgument(
                name="steps",
                arg_type="int",
                description="Number of denoising steps (10-150). More steps = more detail but slower.",
                required=False,
                default="50",
                example="50",
            ),
            ToolArgument(
                name="seed",
                arg_type="int",
                description="Random seed for reproducible results. Leave empty for random results.",
                required=False,
                default=None,
                example="42",
            ),
        ]
    )

    output_dir: Path = Field(default=Path("generated_images"))
    bedrock_client: Any = Field(default=None)

    def model_post_init(self, __context):
        """Initialize after model creation."""
        # Create output directory
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Initialize AWS Bedrock client
        self.bedrock_client = boto3.client(
            service_name='bedrock-runtime',
            aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
            aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
            region_name=os.getenv('AWS_REGION', 'us-east-1')
        )
        logger.debug(f"Initialized StableDiffusionTool with Bedrock client")

    def _validate_params(
        self,
        model_id: str,
        size: str,
        style: str,
        cfg_scale: float,
        steps: int,
        seed: Optional[int],
    ) -> None:
        """Validate Stable Diffusion parameters."""
        if model_id not in STABLE_DIFFUSION_CONFIG["models"]:
            raise ValueError(f"Invalid model_id. Must be one of: {STABLE_DIFFUSION_CONFIG['models']}")
        
        width, height = map(int, size.split('x'))
        if (width, height) not in STABLE_DIFFUSION_CONFIG["sizes"]:
            raise ValueError(f"Invalid size. Must be one of: {[f'{w}x{h}' for w, h in STABLE_DIFFUSION_CONFIG['sizes']]}")
        
        if style not in STABLE_DIFFUSION_CONFIG["styles"]:
            raise ValueError(f"Invalid style. Must be one of: {STABLE_DIFFUSION_CONFIG['styles']}")
        
        if not 0 <= cfg_scale <= 35:
            raise ValueError("cfg_scale must be between 0 and 35")
        
        if not 10 <= steps <= 150:
            raise ValueError("steps must be between 10 and 150")
        
        if seed is not None and not isinstance(seed, int):
            raise ValueError("seed must be an integer or None")

    async def _save_metadata(self, metadata: Dict[str, Any], filepath: Path) -> None:
        """Save image metadata to JSON file."""
        try:
            metadata_path = filepath.with_suffix('.json')
            with open(metadata_path, 'w') as f:
                json.dump(metadata, f, indent=2)
            logger.info(f"Metadata saved successfully at: {metadata_path}")
        except Exception as e:
            logger.error(f"Error saving metadata: {e}")
            raise

    async def async_execute(
        self,
        prompt: str,
        negative_prompt: str = "ugly, deformed, noisy, blurry, distorted, low quality",
        model_id: str = "stability.stable-diffusion-xl-v1",
        size: str = "1024x1024",
        style: str = "photographic",
        cfg_scale: float = 7.0,
        steps: int = 50,
        seed: Optional[int] = None,
    ) -> str:
        """Execute the tool to generate an image using Stable Diffusion.

        Args:
            prompt: Text description of the image to generate
            negative_prompt: Text description of what to avoid in the image
            model_id: The Stability AI model version to use
            size: Size of the generated image (width x height)
            style: Style preset to use
            cfg_scale: How closely to follow the prompt (0-35)
            steps: Number of denoising steps (10-150)
            seed: Random seed for reproducible results

        Returns:
            Path to the locally saved image
        """
        try:
            # Validate parameters
            self._validate_params(model_id, size, style, cfg_scale, steps, seed)
            
            # Parse size into width and height
            width, height = map(int, size.split('x'))
            
            # Prepare request body
            request_body = {
                "text_prompts": [
                    {"text": prompt, "weight": 1.0},
                    {"text": negative_prompt, "weight": -1.0}
                ],
                "cfg_scale": cfg_scale,
                "steps": steps,
                "width": width,
                "height": height,
                "style_preset": style
            }
            
            if seed is not None:
                request_body["seed"] = seed

            # Generate image
            logger.info(f"Generating image with params: {request_body}")
            response = self.bedrock_client.invoke_model(
                modelId=model_id,
                body=json.dumps(request_body)
            )

            # Parse response
            response_body = json.loads(response['body'].read())
            if 'artifacts' not in response_body or not response_body['artifacts']:
                raise ValueError("No image data in response")

            # Get image data
            image_data = response_body['artifacts'][0]['base64']

            # Save image
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"sd_{timestamp}.png"
            file_path = self.output_dir / filename

            # Save image from base64
            with open(file_path, "wb") as f:
                f.write(base64.b64decode(image_data))

            logger.info(f"Image saved successfully at: {file_path}")

            # Save metadata
            metadata = {
                "filename": filename,
                "timestamp": timestamp,
                "model_id": model_id,
                "prompt": prompt,
                "negative_prompt": negative_prompt,
                "size": size,
                "style": style,
                "cfg_scale": cfg_scale,
                "steps": steps,
                "seed": seed,
                "local_path": str(file_path),
            }
            await self._save_metadata(metadata, file_path)

            return str(file_path)

        except Exception as e:
            logger.error(f"Error generating image: {e}")
            raise


if __name__ == "__main__":
    import asyncio

    async def main():
        tool = StableDiffusionTool()
        result = await tool.async_execute(
            prompt="A majestic red dragon perched on a crystal mountain peak at sunset",
            style="digital-art",
            cfg_scale=7.0,
            steps=50,
        )
        print(f"Generated image saved at: {result}")

    asyncio.run(main())
