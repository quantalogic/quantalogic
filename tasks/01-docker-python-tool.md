Implement a python interpreter tool called python_tool that takes a python script as input and returns the output of the script.

Example:

<python_tool>
<install_command>
pip install rich
pip install requests
</install_command>
<script>
print("Hello, World!")
print("This is a python interpreter tool.")
</script>
<version>3.12</version>
</python_tool>

The interpreter should be able to run the script and return the output on the command line.

It will use docker to run the interpreter.