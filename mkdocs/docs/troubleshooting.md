# Troubleshooting Guide

This guide helps you solve common issues with QuantaLogic. Follow our systematic approach to identify and fix problems quickly.

## Diagnostic Process

1. **Identify the Issue**
   - What were you trying to do?
   - What happened instead?
   - Any error messages?

2. **Check Prerequisites**
   - Python version
   - Required packages
   - API keys
   - Docker status (if using code tools)

3. **Review Logs**
   - Enable detailed logging
   - Check event monitoring
   - Analyze error patterns

## Common Issues

### Installation Problems

#### Python Version Mismatch
```text
Error: Python 3.12 or later is required
```

**Solution:**
1. Check your Python version:
```bash
python --version
```
2. Install/upgrade Python:
```bash
# macOS
brew install python@3.12

# Linux
sudo apt update
sudo apt install python3.12

# Windows
# Download from python.org
```

#### Package Conflicts
```text
Error: Dependency conflicts detected
```

**Solution:**
1. Create a fresh virtual environment:
```bash
python -m venv .venv
source .venv/bin/activate
```
2. Install with clean dependencies:
```bash
pip install --no-cache-dir quantalogic
```

### API Key Issues

#### Missing API Key
```text
ValueError: DEEPSEEK_API_KEY environment variable is not set
```

**Solution:**
1. Set the API key:
```bash
export DEEPSEEK_API_KEY="your-api-key"
```
2. Verify it's set:
```bash
echo $DEEPSEEK_API_KEY
```

#### Invalid API Key
```text
Error: Authentication failed
```

**Solution:**
1. Check key validity in provider dashboard
2. Ensure no whitespace in key
3. Try regenerating the key

### Docker Issues

#### Permission Denied
```text
Error: permission denied while trying to connect to the Docker daemon socket
```

**Solution:**
1. Add user to docker group:
```bash
sudo usermod -aG docker $USER
```
2. Log out and back in
3. Verify:
```bash
docker ps
```

#### Container Errors
```text
Error: container failed to start
```

**Solution:**
1. Check Docker status:
```bash
docker info
```
2. Clean up Docker:
```bash
docker system prune
```
3. Verify disk space:
```bash
df -h
```

### Memory Issues

#### Memory Full
```text
Error: memory_full event triggered
```

**Solution:**
1. Enable memory monitoring:
```python
agent.event_emitter.on(
    ["memory_full", "memory_compacted"],
    console_print_events
)
```
2. Adjust memory settings:
```python
agent = Agent(
    model_name="deepseek/deepseek-chat",
    memory_limit="2G"
)
```

#### Performance Degradation
```text
Warning: Task execution time exceeding normal limits
```

**Solution:**
1. Monitor memory usage
2. Implement batch processing
3. Use memory optimization:
```python
agent.compact_memory()
```

### Tool Execution Issues

#### Tool Not Found
```text
Error: Tool 'XYZ' not found
```

**Solution:**
1. Verify tool installation:
```python
print(agent.available_tools)
```
2. Install missing tools:
```python
from quantalogic.tools import RequiredTool
agent.add_tool(RequiredTool())
```

#### Tool Execution Failed
```text
Error: Tool execution failed: [specific error]
```

**Solution:**
1. Enable detailed logging:
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```
2. Check tool prerequisites
3. Verify input parameters

## Best Practices

### 1. Error Prevention
- Always verify API keys before starting
- Use virtual environments
- Keep dependencies updated
- Monitor system resources

### 2. Debugging
- Enable comprehensive logging
- Monitor all relevant events
- Use step-by-step execution
- Check system requirements

### 3. Performance
- Clean up unused resources
- Implement proper error handling
- Use batch processing when possible
- Monitor memory usage

## Getting Help

If you're still stuck:

1. **Search Documentation**
   - Check this troubleshooting guide
   - Review relevant examples
   - Read tool documentation

2. **Community Resources**
   - Search GitHub Issues
   - Check Stack Overflow
   - Join Discord community

3. **Support Channels**
   - Open GitHub issue
   - Contact support team
   - Share detailed error logs

## Reporting Bugs

When reporting issues:

1. **Provide Context**
   - Python version
   - QuantaLogic version
   - Operating system
   - Full error message

2. **Share Reproduction Steps**
   - Minimal code example
   - Input data (if relevant)
   - Expected vs actual result

3. **Include Logs**
   - Error messages
   - Event monitoring output
   - System information

## Next Steps

- Review [Best Practices](best-practices/agent-design.md)
- Learn about [Monitoring](examples/event-monitoring.md)
- Check [API Reference](api/agent.md)
