# 🌊 Quantalogic Flow Examples

Welcome to the **Quantalogic Flow Examples** repository! 🚀 This comprehensive collection showcases practical, real-world applications of Quantalogic Flow, demonstrating how to build powerful AI workflows with minimal code.

## 🎯 What is Quantalogic Flow?

**Quantalogic Flow** is a cutting-edge framework specifically designed for AI Engineering projects. It transforms complex AI workflows into simple, maintainable Python code by providing:

### 🔧 Core Capabilities
- **🤖 LLM Integration**: Seamlessly incorporate Large Language Models into your workflows
- **🎨 Template System**: Create consistent, reusable patterns with Jinja2 templates
- **🧩 Function Composition**: Combine simple Python functions into powerful workflows
- **⚙️ YAML Configuration**: Configure complex AI pipelines through intuitive YAML files
- **🔄 Orchestration**: Manage multiple AI components with intelligent flow control
- **📊 Monitoring**: Built-in tools for workflow optimization and debugging

### 🌟 Why Choose Quantalogic Flow?
- **Rapid Development**: Transform ideas into working AI systems in minutes
- **Maintainable Code**: Clean, readable workflows that scale with your project
- **Flexible Architecture**: Adapt to any AI use case from chatbots to complex pipelines
- **Production Ready**: Built-in error handling, retry logic, and monitoring

📚 **Learn More**: [Complete Documentation](./quantalogic/flow/flow_yaml.md) | [API Reference](../README.md)

## 📂 Example Projects Overview

Explore our curated collection of examples, each demonstrating different aspects of Quantalogic Flow:

---

### 📚 1. Analyze Paper
**🎯 Purpose**: Unlock the power of academic paper analysis!  
Extract key insights, summaries, and research findings from academic papers with AI-powered analysis.

**🔍 What's Inside**:
- [analyze_paper.py](./analyze_paper/analyze_paper.py): Intelligent paper analysis engine 🧠
- [README.md](./analyze_paper/README.md): Complete usage guide 📖
- **Features**: Citation extraction, summary generation, key finding identification

**💡 Use Cases**: Research assistance, literature reviews, academic writing support

[🚀 Explore Analyze Paper](./analyze_paper/README.md)

---

### 📄 2. PDF to Markdown Converter
**🎯 Purpose**: Transform PDFs into beautiful, editable Markdown!  
Perfect for researchers, writers, and content creators who need clean, structured text formats.

**🛠️ What's Inside**:
- [pdf_to_markdown.py](./pdf_to_markdown/pdf_to_markdown.py): Advanced conversion engine 🔧
- Example transformations: See the magic in action! ✨
- [README.md](./pdf_to_markdown/README.md): Conversion mastery guide 🔓
- **Features**: Layout preservation, table extraction, image handling

**💡 Use Cases**: Document digitization, content migration, research workflows

[🚀 Discover PDF to Markdown](./pdf_to_markdown/README.md)

---

### 📖 3. Simple Story Generator
**� Purpose**: Unleash your creative storytelling potential!  
Generate engaging, multi-chapter stories with AI-powered narrative creation and quality validation.

**📚 What's Inside**:
- [story_generator_agent.py](./simple_story_generator/story_generator_agent.py): Story creation factory 🏭
- [External template version](./simple_story_generator/story_generator_agent_external_template.py): Template-based creativity 🎨
- `templates/`: Reusable story components 📝
- **Features**: Genre-specific generation, chapter loops, quality checks

**💡 Use Cases**: Creative writing, content generation, educational storytelling

[🚀 Create Stories Now](./simple_story_generator/README.md)

---

### 📚 4. Advanced Story Generator
**� Purpose**: Master complex narrative generation!  
Build sophisticated stories with advanced workflow patterns, conditional logic, and dynamic content adaptation.

**💫 What's Inside**:
- [story_generator_agent.py](./story_generator/story_generator_agent.py): Advanced narrative architect 🏗️
- **Features**: Dynamic character development, plot branching, style adaptation
- **Patterns**: Conditional workflows, loop optimization, context management

**💡 Use Cases**: Interactive fiction, game narratives, complex storytelling

[🚀 Build Advanced Stories](./story_generator/README.md)

---

### 🤔 5. Questions and Answers Generator
**🎯 Purpose**: Transform content into educational assessments!  
Extract facts from markdown files and generate comprehensive questionnaires with quality validation.

**🔍 What's Inside**:
- Fact extraction from markdown content 📊
- Intelligent question generation 🧠
- Quality evaluation and validation ✅
- **Features**: Pydantic data validation, CLI interface, educational content automation

**💡 Use Cases**: Educational content creation, assessment generation, knowledge testing

[🚀 Explore Q&A Generator](./questions_and_answers/README.md)

---

### 📚 6. Tutorial Generator
**🎯 Purpose**: Transform raw content into polished tutorials!  
Convert markdown files into structured, engaging tutorials with minimal effort. Perfect for educators and technical writers.

**✨ What's Inside**:
- [create_tutorial.py](./create_tutorial/create_tutorial.py): Tutorial creation powerhouse 🏭
- Jinja2 templates: Professional, consistent output 📝
- LLM-powered content structuring and refinement 🤖
- Real-time progress tracking 📊
- **Features**: Content analysis, structure optimization, quality enhancement

**💡 Use Cases**: Educational content, technical documentation, training materials

[🚀 Discover Tutorial Generator](./create_tutorial/README.md)

---

## 🚀 Quick Start Guide

### Prerequisites
- **Python 3.12+**
- **UV package manager** (recommended for dependency management)
- **API Keys**: OpenAI, Anthropic, or other LLM providers

### Installation
```bash
# Clone the repository
git clone https://github.com/your-repo/quantalogic-flow
cd quantalogic-flow/examples

# Install dependencies with UV
uv install

# Or with pip
pip install -r requirements.txt
```

### Running Examples
Each example is self-contained and can be run directly:

```bash
# Run any example with UV
./simple_story_generator/story_generator_agent.py

# Or with Python
python simple_story_generator/story_generator_agent.py
```

---

## 🎯 Learning Path

### 🌱 **Beginner Level**
1. **[Simple Story Generator](./simple_story_generator/README.md)** - Learn basic workflow creation
2. **[PDF to Markdown](./pdf_to_markdown/README.md)** - Understand data transformation
3. **[Analyze Paper](./analyze_paper/README.md)** - Explore LLM integration

### 🌿 **Intermediate Level**
4. **[Questions and Answers](./questions_and_answers/README.md)** - Master structured data handling
5. **[Tutorial Generator](./create_tutorial/README.md)** - Build complex content workflows

### 🌳 **Advanced Level**
6. **[Advanced Story Generator](./story_generator/README.md)** - Implement sophisticated flow control

---

## 📊 Examples Comparison

| Example | Complexity | LLM Nodes | Templates | Loops | Use Case |
|---------|------------|-----------|-----------|--------|----------|
| Analyze Paper | ⭐⭐ | 2 | No | No | Research |
| PDF to Markdown | ⭐⭐ | 1 | Yes | No | Document Processing |
| Simple Story Generator | ⭐⭐⭐ | 3 | Yes | Yes | Creative Writing |
| Q&A Generator | ⭐⭐⭐ | 2 | No | No | Education |
| Tutorial Generator | ⭐⭐⭐⭐ | 4 | Yes | Yes | Content Creation |
| Advanced Story Generator | ⭐⭐⭐⭐⭐ | 4 | Yes | Yes | Complex Narratives |

---

## 🛠️ What You'll Learn

### 🔧 **Core Concepts**
- **Node Types**: LLM, Template, Function, and Validation nodes
- **Workflow Patterns**: Sequential, conditional, and loop-based flows
- **Context Management**: Passing data between workflow steps
- **Error Handling**: Robust error management and recovery

### 🎨 **Advanced Techniques**
- **Template Integration**: Using Jinja2 for dynamic content generation
- **Conditional Logic**: Building intelligent decision trees
- **Loop Control**: Implementing iterative processes
- **Observer Pattern**: Monitoring workflow execution

### 🚀 **Best Practices**
- **Code Organization**: Structuring workflows for maintainability
- **Performance Optimization**: Efficient LLM usage and caching
- **Testing Strategies**: Validating workflow behavior
- **Production Deployment**: Scaling workflows for real-world use

---

## 🤝 Community & Support

### 📖 **Documentation**
- [Complete API Reference](../README.md)
- [YAML Configuration Guide](../flow_yaml.md)
- [Best Practices](../docs/best-practices.md)

### 💬 **Get Help**
- [GitHub Issues](https://github.com/your-repo/quantalogic-flow/issues)
- [Community Discussions](https://github.com/your-repo/quantalogic-flow/discussions)
- [Discord Server](https://discord.gg/quantalogic)

### 🏆 **Contributing**
We welcome contributions! Check out our [Contributing Guide](../CONTRIBUTING.md) to get started.

---

## � Each Example Includes

Every example project comes with comprehensive documentation:

- **�🛠️ Installation Instructions**: Step-by-step setup guide
- **🚀 Usage Examples**: Real-world usage scenarios
- **📊 Architecture Diagrams**: Visual workflow representations
- **🤔 Troubleshooting Guide**: Common issues and solutions
- **💡 Best Practices**: Expert tips and recommendations
- **🔧 Configuration Options**: Customization parameters
- **📈 Performance Tips**: Optimization strategies

---

## 🎉 Ready to Start?

Choose your adventure based on your experience level:

**👶 New to AI Workflows?** Start with [Simple Story Generator](./simple_story_generator/README.md)  
**🧠 Experienced Developer?** Jump to [Advanced Story Generator](./story_generator/README.md)  
**📚 Educator or Writer?** Try [Tutorial Generator](./create_tutorial/README.md)  
**🔬 Researcher?** Explore [Analyze Paper](./analyze_paper/README.md)  

Remember: The best way to learn is by doing! 🌟 Pick an example that interests you and start building. Each project is designed to teach you something new while creating something useful.

**Happy coding!** 🚀✨
