"""DALL-E Image Generation Tool for creating images using DALL-E via AWS Bedrock."""

import datetime
import json
from pathlib import Path
from typing import Any, Dict, Optional

import aiohttp
import aiofiles
from loguru import logger
from pydantic import ConfigDict, Field
from tenacity import retry, stop_after_attempt, wait_exponential

from quantalogic.generative_model import GenerativeModel
from quantalogic.tools.tool import Tool, ToolArgument


DALLE_CONFIG = {
    "model_name": "dall-e-3",
    "sizes": ["1024x1024", "1024x1792", "1792x1024"],
    "qualities": ["standard", "hd"],
    "styles": ["vivid", "natural"],
}


class LLMImageGenerationTool(Tool):
    """Tool for generating images using DALL-E."""

    model_config = ConfigDict(arbitrary_types_allowed=True, extra="allow")

    name: str = Field(default="dalle_image_generation_tool")
    description: str = Field(
        default=(
            "Generate images using DALL-E 3. Simple to use with smart defaults:\n"
            "1. Write a clear prompt describing your image\n"
            "2. Choose image format: square(1024x1024), portrait(1024x1792), landscape(1792x1024)\n"
            "3. Pick quality: standard(fast) or hd(detailed)\n"
            "4. Select style: vivid(dramatic) or natural(realistic)\n"
            "\nAll images are saved locally with metadata."
        )
    )
    arguments: list = Field(
        default=[
            ToolArgument(
                name="prompt",
                arg_type="string",
                description=(
                    "Describe what you want to see in the image. Include:\n"
                    "- Main subject or scene\n"
                    "- Style and mood\n"
                    "- Important details\n"
                    "- Colors or lighting\n"
                    "\nKeep it clear and specific"
                ),
                required=True,
                example="A peaceful Japanese garden with a red maple tree, stone lanterns, and a koi pond at sunset",
            ),
            ToolArgument(
                name="size",
                arg_type="string",
                description=(
                    "Image dimensions:\n"
                    "- 1024x1024: Square (social media)\n"
                    "- 1024x1792: Portrait (mobile)\n"
                    "- 1792x1024: Landscape (desktop)"
                ),
                required=False,
                default="1024x1024",
                example="1024x1024",
            ),
            ToolArgument(
                name="quality",
                arg_type="string",
                description=(
                    "Image quality:\n"
                    "- standard: Faster, good for drafts\n"
                    "- hd: Detailed, best for final use"
                ),
                required=False,
                default="standard",
                example="standard",
            ),
            ToolArgument(
                name="style",
                arg_type="string",
                description=(
                    "Visual style:\n"
                    "- vivid: Bold and dramatic\n"
                    "- natural: Subtle and realistic"
                ),
                required=False,
                default="vivid",
                example="vivid",
            ),
        ]
    )

    model_name: str = Field(default=DALLE_CONFIG["model_name"])
    output_dir: Path = Field(default=Path("generated_images"))
    generative_model: Optional[GenerativeModel] = Field(default=None)

    def model_post_init(self, __context):
        """Initialize after model creation."""
        if self.generative_model is None:
            self.generative_model = GenerativeModel(model=self.model_name)
            logger.debug(f"Initialized LLMImageGenerationTool with model: {self.model_name}")

        # Create output directory if it doesn't exist
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def _validate_params(self, size: str, quality: str, style: str) -> None:
        """Validate DALL-E parameters."""
        if size not in DALLE_CONFIG["sizes"]:
            raise ValueError(f"Invalid size. Must be one of: {DALLE_CONFIG['sizes']}")
        if quality not in DALLE_CONFIG["qualities"]:
            raise ValueError(f"Invalid quality. Must be one of: {DALLE_CONFIG['qualities']}")
        if style not in DALLE_CONFIG["styles"]:
            raise ValueError(f"Invalid style. Must be one of: {DALLE_CONFIG['styles']}")

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    async def _save_image(self, image_url: str, filename: str) -> Path:
        """Download and save image locally with retry logic."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(image_url, timeout=30) as response:
                    response.raise_for_status()
                    image_data = await response.read()

            file_path = self.output_dir / filename
            async with aiofiles.open(file_path, mode='wb') as f:
                await f.write(image_data)

            logger.info(f"Image saved successfully at: {file_path}")
            return file_path

        except Exception as e:
            logger.error(f"Error saving image: {e}")
            raise

    async def _save_metadata(self, metadata: Dict[str, Any]) -> None:
        """Save image metadata to JSON file."""
        try:
            metadata_path = self.output_dir / f"{metadata['filename']}.json"
            async with aiofiles.open(metadata_path, mode='w') as f:
                await f.write(json.dumps(metadata, indent=2))
            logger.info(f"Metadata saved successfully at: {metadata_path}")
        except Exception as e:
            logger.error(f"Error saving metadata: {e}")
            raise

    async def async_execute(
        self,
        prompt: str,
        size: str = "1024x1024",
        quality: str = "standard",
        style: str = "vivid",
    ) -> str:
        """Execute the tool to generate an image using DALL-E.

        Args:
            prompt: Text description of the image to generate
            size: Size of the generated image
            quality: Quality level for DALL-E
            style: Style preference for DALL-E

        Returns:
            Path to the locally saved image
        """
        try:
            # Validate parameters
            self._validate_params(size, quality, style)
            
            params = {
                "model": self.model_name,
                "size": size,
                "quality": quality,
                "style": style,
                "response_format": "url",
            }

            # Generate image
            logger.info(f"Generating DALL-E image with params: {params}")
            response = await self.generative_model.async_generate_image(prompt=prompt, params=params)

            # Extract image data from response
            if not response.data:
                raise ValueError("No image data in response")

            image_data = response.data[0]  # First image from the response
            image_url = str(image_data.get("url", ""))
            revised_prompt = str(image_data.get("revised_prompt", prompt))

            if not image_url:
                raise ValueError("No image URL in response")

            # Save image locally
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"dalle_{timestamp}.png"
            local_path = await self._save_image(image_url, filename)

            # Save metadata
            metadata = {
                "filename": str(filename),
                "prompt": str(prompt),
                "revised_prompt": str(revised_prompt),
                "model": str(response.model),
                "created": str(response.created or ""),
                "parameters": {k: str(v) for k, v in {**params, "prompt": prompt}.items()},
                "image_url": str(image_url),
                "local_path": str(local_path),
            }
            await self._save_metadata(metadata)

            logger.info(f"Image generated and saved at: {local_path}")
            return str(metadata)

        except Exception as e:
            logger.error(f"Error generating DALL-E image: {e}")
            raise Exception(f"Error generating DALL-E image: {e}") from e


if __name__ == "__main__":
    # Example usage
    import asyncio

    async def main():
        tool = LLMImageGenerationTool()
        prompt = "A serene Japanese garden with a red maple tree"
        image_path = await tool.async_execute(prompt=prompt)
        print(f"Image saved at: {image_path}")

    asyncio.run(main())
