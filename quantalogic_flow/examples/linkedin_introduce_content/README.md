# Viral LinkedIn Post Generator with Quantalogic Flow

This example demonstrates how to use the `quantalogic_flow` framework to transform a markdown tutorial or software introduction into a viral, platform-optimized LinkedIn post. The workflow leverages LLMs for content analysis, strategy, writing, cleaning, and formatting, and provides a CLI for easy use.

## Features
- **Content Analysis:** Extracts type, topic, audience, and key points from your markdown.
- **Viral Strategy:** Suggests hooks, value propositions, hashtags, and engagement tactics tailored for LinkedIn.
- **Post Generation:** Crafts a LinkedIn post using best practices for virality and engagement.
- **Cleaning & Formatting:** Refines and formats the post for LinkedIn's platform requirements.
- **Clipboard & File Output:** Optionally copies the result to your clipboard and saves it as a `.linkedin.md` file.
- **Rich CLI:** Interactive, with intent prompting and progress feedback.

## Usage

### 1. Install Requirements
```bash
uv pip install -r requirements.txt
```

### 2. Prepare Your Markdown
Create a markdown file (e.g., `input.md`) with your tutorial or introduction content.

### 3. Run the CLI
```bash
python linkedin_introduce_content.py create-post input.md --copy
```

#### Options
- `--analysis-model`   : LLM for content analysis (default: gemini/gemini-2.0-flash)
- `--writing-model`    : LLM for post writing (default: openrouter/deepseek/deepseek-r1)
- `--cleaning-model`   : LLM for cleaning (default: gemini/gemini-2.0-flash)
- `--formatting-model` : LLM for formatting (default: gemini/gemini-2.0-flash)
- `--copy/--no-copy`   : Copy result to clipboard (default: True)
- `--intent/-i`        : Specify the post's intent/focus (optional, will prompt if omitted)
- `--mock-analysis`    : Use mock analysis for testing (no LLM calls)

### 4. Output
- The generated LinkedIn post is displayed in the terminal (with rich formatting).
- The post is saved as `<input>.linkedin.md`.
- If `--copy` is enabled, the post is copied to your clipboard.

## Workflow Overview
1. **Read Markdown** → 2. **Analyze Content** → 3. **Viral Strategy** → 4. **Generate Post** → 5. **Clean** → 6. **Format** → 7. **Save** → 8. **Copy to Clipboard**

## Example
```bash
python linkedin_introduce_content.py create-post input.md --copy --intent "Drive signups for our new tool"
```

## Requirements
See `requirements.txt` for all dependencies.

## Notes
- The workflow uses Loguru for logging and Rich for beautiful CLI output.
- All LLM calls are handled via the quantalogic_flow workflow engine.
- For best results, use high-quality markdown input and specify your intent.

---

**Author:** [Your Name]
**License:** MIT
