import importlib

__all__ = [
    "CLanguageHandler",
    "CppLanguageHandler",
    "GoLanguageHandler",
    "JavaLanguageHandler",
    "JavaScriptLanguageHandler",
    "PythonLanguageHandler",
    "RustLanguageHandler",
    "ScalaLanguageHandler",
    "TypeScriptLanguageHandler",
]

def __getattr__(name):
    """Lazily import language handlers when they are first requested."""
    if name in __all__:
        module_map = {
            "CLanguageHandler": "c_handler",
            "CppLanguageHandler": "cpp_handler",
            "GoLanguageHandler": "go_handler",
            "JavaLanguageHandler": "java_handler",
            "JavaScriptLanguageHandler": "javascript_handler",
            "PythonLanguageHandler": "python_handler",
            "RustLanguageHandler": "rust_handler",
            "ScalaLanguageHandler": "scala_handler",
            "TypeScriptLanguageHandler": "typescript_handler",
        }
        
        module_name = module_map[name]
        module = importlib.import_module(f".{module_name}", package=__package__)
        return getattr(module, name)
    
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")
