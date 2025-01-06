import os

from litellm import completion

# Set your API key
os.environ["OPENAI_API_KEY"] = "your_api_key_here"

# Call the model with an image URL
response = completion(
    model="ollama/llama3.2-vision:latest",
    messages=[
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "What’s in this image?"},
                {"type": "image_url", "image_url": {"url": "https://upload.wikimedia.org/wikipedia/commons/thumb/d/dd/Gfp-wisconsin-madison-the-nature-boardwalk.jpg/2560px-Gfp-wisconsin-madison-the-nature-boardwalk.jpg"}}
            ]
        }
    ]
)

print(f"Image Analysis Response: {response.choices[0].message.content}")
