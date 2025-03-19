import asyncio
from loguru import logger
from quantalogic.tools.rag_tool.ocr_pdf_markdown import PDFToMarkdownConverter

async def main():
    # Initialize the converter with default settings
    converter = PDFToMarkdownConverter(
        model="gemini/gemini-2.0-flash",  # Using the default model
        custom_system_prompt=(
            "Convert this Code Civil page to clean Markdown. "
            "Preserve the legal structure, article numbers, and formatting. "
            "Use appropriate Markdown headers for different sections. "
            "Ensure proper formatting of legal references and citations."
        )
    )
    
    # Path to your PDF file
    pdf_path = "docs/test/Code_Civil.pdf"
    
    # Test 1: Convert first 2 pages only (pages start from 1)
    logger.info("Converting first 2 pages...")
    markdown_content = await converter.convert_pdf(
        pdf_path=pdf_path,
        select_pages=[1, 2]  # Convert pages 1 and 2
    )
    print("\n=== First 2 Pages ===")
    print(markdown_content[:500] + "...\n")  # Show first 500 characters
    
    # Test 2: Convert and save to file
    output_path = "docs/test/Code_Civil_output.md"
    logger.info("Converting and saving full document...")
    saved_path = await converter.convert_and_save(
        pdf_path=pdf_path,
        output_md=output_path
    )
    print(f"\nFull document saved to: {saved_path}")

if __name__ == "__main__":
    asyncio.run(main())
