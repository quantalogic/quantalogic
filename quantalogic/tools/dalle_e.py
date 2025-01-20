"""LLM Image Generation Tool for creating images using DALL-E or Stable Diffusion via AWS Bedrock."""

import datetime
import json
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Optional

import requests
from loguru import logger
from pydantic import ConfigDict, Field
from tenacity import retry, stop_after_attempt, wait_exponential

from quantalogic.generative_model import GenerativeModel
from quantalogic.tools.tool import Tool, ToolArgument


class ImageProvider(str, Enum):
    """Supported image generation providers."""
    DALLE = "dall-e"
    STABLE_DIFFUSION = "stable-diffusion"

PROVIDER_CONFIGS = {
    ImageProvider.DALLE: {
        "model_name": "dall-e-3",
        "sizes": ["1024x1024", "1024x1792", "1792x1024"],
        "qualities": ["standard", "hd"],
        "styles": ["vivid", "natural"],
    },
    ImageProvider.STABLE_DIFFUSION: {
        #"model_name": "anthropic.claude-3-sonnet-20240229",
        "model_name": "amazon.titan-image-generator-v1",
        "sizes": ["1024x1024"],  # Bedrock SD supported size
        "qualities": ["standard"],  # SD quality is controlled by cfg_scale
        "styles": ["none"],  # Style is controlled through prompting 
    }
}

class LLMImageGenerationTool(Tool):
    """Tool for generating images using DALL-E or Stable Diffusion."""

    model_config = ConfigDict(arbitrary_types_allowed=True, extra="allow")

    name: str = Field(default="llm_image_generation_tool")
    description: str = Field(
        default=(
            "Generate images using DALL-E or Stable Diffusion. "
            "Supports different sizes, styles, and quality settings."
        )
    )
    arguments: list = Field(
        default=[
            ToolArgument(
                name="prompt",
                arg_type="string",
                description="Text description of the image to generate",
                required=True,
                example="A serene Japanese garden with a red maple tree",
            ),
            ToolArgument(
                name="provider",
                arg_type="string",
                description="Image generation provider (dall-e or stable-diffusion)",
                required=False,
                default="dall-e",
                example="dall-e",
            ),
            ToolArgument(
                name="size",
                arg_type="string",
                description="Size of the generated image",
                required=False,
                default="1024x1024",
                example="1024x1024",
            ),
            ToolArgument(
                name="quality",
                arg_type="string",
                description="Quality level for DALL-E",
                required=False,
                default="standard",
                example="standard",
            ),
            ToolArgument(
                name="style",
                arg_type="string",
                description="Style preference for DALL-E",
                required=False,
                default="vivid",
                example="vivid",
            ),
            ToolArgument(
                name="negative_prompt",
                arg_type="string",
                description="What to avoid in the image (Stable Diffusion only)",
                required=False,
                default="",
                example="blurry, low quality",
            ),
            ToolArgument(
                name="cfg_scale",
                arg_type="string",
                description="Classifier Free Guidance scale (Stable Diffusion only)",
                required=False,
                default="7.5",
                example="7.5",
            ),
        ]
    )

    provider: ImageProvider = Field(default=ImageProvider.DALLE)
    model_name: str = Field(default=PROVIDER_CONFIGS[ImageProvider.DALLE]["model_name"])
    output_dir: Path = Field(default=Path("generated_images"))
    generative_model: Optional[GenerativeModel] = Field(default=None)

    def model_post_init(self, __context):
        """Initialize after model creation."""
        if self.generative_model is None:
            self.generative_model = GenerativeModel(model=self.model_name)
            logger.debug(f"Initialized LLMImageGenerationTool with model: {self.model_name}")
        
        # Create output directory if it doesn't exist
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def _validate_dalle_params(self, size: str, quality: str, style: str) -> None:
        """Validate DALL-E specific parameters."""
        if size not in PROVIDER_CONFIGS[ImageProvider.DALLE]["sizes"]:
            raise ValueError(f"Invalid size for DALL-E. Must be one of: {PROVIDER_CONFIGS[ImageProvider.DALLE]['sizes']}")
        if quality not in PROVIDER_CONFIGS[ImageProvider.DALLE]["qualities"]:
            raise ValueError(f"Invalid quality for DALL-E. Must be one of: {PROVIDER_CONFIGS[ImageProvider.DALLE]['qualities']}")
        if style not in PROVIDER_CONFIGS[ImageProvider.DALLE]["styles"]:
            raise ValueError(f"Invalid style for DALL-E. Must be one of: {PROVIDER_CONFIGS[ImageProvider.DALLE]['styles']}")

    def _validate_sd_params(self, size: str, cfg_scale: float) -> None:
        """Validate Stable Diffusion specific parameters."""
        if size not in PROVIDER_CONFIGS[ImageProvider.STABLE_DIFFUSION]["sizes"]:
            raise ValueError(f"Invalid size for Stable Diffusion. Must be one of: {PROVIDER_CONFIGS[ImageProvider.STABLE_DIFFUSION]['sizes']}")
        if not 1.0 <= cfg_scale <= 20.0:
            raise ValueError("cfg_scale must be between 1.0 and 20.0")

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    def _save_image(self, image_url: str, filename: str) -> Path:
        """Download and save image locally with retry logic."""
        try:
            response = requests.get(image_url, timeout=30)
            response.raise_for_status()
            
            file_path = self.output_dir / filename
            file_path.write_bytes(response.content)
            logger.info(f"Image saved successfully at: {file_path}")
            return file_path
            
        except Exception as e:
            logger.error(f"Error saving image: {e}")
            raise

    def _save_metadata(self, metadata: Dict[str, Any]) -> None:
        """Save image metadata to JSON file."""
        try:
            metadata_path = self.output_dir / f"{metadata['filename']}.json"
            with open(metadata_path, 'w') as f:
                json.dump(metadata, f, indent=2)
            logger.info(f"Metadata saved successfully at: {metadata_path}")
        except Exception as e:
            logger.error(f"Error saving metadata: {e}")
            raise

    def execute(
        self,
        prompt: str,
        provider: str = "dall-e",
        size: str = "1024x1024",
        quality: str = "standard",
        style: str = "vivid",
        negative_prompt: str = "",
        cfg_scale: str = "7.5",
    ) -> str:
        """Execute the tool to generate an image based on the prompt.
        
        Args:
            prompt: Text description of the image to generate
            provider: Provider to use (dall-e or stable-diffusion)
            size: Size of the generated image
            quality: Quality level for DALL-E
            style: Style preference for DALL-E
            negative_prompt: What to avoid in the image (Stable Diffusion only)
            cfg_scale: Classifier Free Guidance scale (Stable Diffusion only)
            
        Returns:
            Path to the locally saved image
        """
        try:
            provider_enum = ImageProvider(provider.lower())
            
            # Convert cfg_scale to float only if it's not empty and we're using Stable Diffusion
            cfg_scale_float = float(cfg_scale) if cfg_scale and provider_enum == ImageProvider.STABLE_DIFFUSION else None
            
            # Validate parameters based on provider
            if provider_enum == ImageProvider.DALLE:
                self._validate_dalle_params(size, quality, style)
                params = {
                    "model": PROVIDER_CONFIGS[provider_enum]["model_name"],
                    "size": size,
                    "quality": quality,
                    "style": style,
                    "response_format": "url"
                }
            else:  # Stable Diffusion
                if cfg_scale_float is None:
                    cfg_scale_float = 7.5  # Default value
                self._validate_sd_params(size, cfg_scale_float)
                params = {
                    "model": PROVIDER_CONFIGS[provider_enum]["model_name"],
                    "negative_prompt": negative_prompt,
                    "cfg_scale": cfg_scale_float,
                    "size": size,
                    "response_format": "url"
                }

            # Generate image
            logger.info(f"Generating image with {provider} using params: {params}")
            response = self.generative_model.generate_image(
                prompt=prompt,
                params=params
            )

            # Extract image data from response
            if not response.data:
                raise ValueError("No image data in response")
            
            image_data = response.data[0]  # First image from the response
            image_url = str(image_data.get("url", ""))
            revised_prompt = str(image_data.get("revised_prompt", prompt))
            
            if not image_url:
                raise ValueError("No image URL in response")

            # Save image locally
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{provider}_{timestamp}.png"
            local_path = self._save_image(image_url, filename)

            # Save metadata
            metadata = {
                "filename": str(filename),
                "prompt": str(prompt),
                "revised_prompt": str(revised_prompt),
                "provider": str(provider),
                "model": str(response.model),
                "created": str(response.created or ""),
                "parameters": {k: str(v) for k, v in {**params, "prompt": prompt}.items()},
                "image_url": str(image_url),
                "local_path": str(local_path)
            }
            self._save_metadata(metadata)

            logger.info(f"Image generated and saved at: {local_path}")
            return str(local_path)

        except Exception as e:
            logger.error(f"Error generating image with {provider}: {e}")
            raise Exception(f"Error generating image with {provider}: {e}") from e


if __name__ == "__main__":
    # Example usage
    tool = LLMImageGenerationTool()
    prompt = "A serene Japanese garden with a red maple tree"
    image_path = tool.execute(prompt=prompt)
    print(f"Image saved at: {image_path}")
