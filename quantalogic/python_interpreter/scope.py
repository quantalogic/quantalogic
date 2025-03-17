# quantalogic/utils/scope.py
class Scope:
    def __init__(self, env_stack):
        self.env_stack = env_stack

    def __enter__(self):
        self.env_stack.append({})

    def __exit__(self, exc_type, exc_value, traceback):
        self.env_stack.pop()