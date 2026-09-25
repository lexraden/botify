#!/usr/bin/env python3
"""Check that .env contains all non-comment variables from .env.example.
Also warn about variables with empty values.
"""
import os
import sys

def load_example(path):
    """Return set of variable names from .env.example (ignoring comments and blank lines)."""
    vars_set = set()
    with open(path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            if '#' in line:
                line = line.split('#', 1)[0].strip()
            if '=' in line:
                var = line.split('=', 1)[0].strip()
                vars_set.add(var)
    return vars_set

def load_env_dict(path):
    """Return dict of variable names to values from .env (if exists)."""
    if not os.path.isfile(path):
        return {}
    env_dict = {}
    with open(path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            if '#' in line:
                line = line.split('#', 1)[0].strip()
            if '=' in line:
                var, val = line.split('=', 1)
                var = var.strip()
                val = val.strip()
                env_dict[var] = val
    return env_dict

def main():
    example_path = os.path.join(os.path.dirname(__file__), '..', 'backend', '.env.example')
    env_path = os.path.join(os.path.dirname(__file__), '..', '.env')
    example_vars = load_example(example_path)
    env_dict = load_env_dict(env_path)
    env_vars = set(env_dict.keys())
    missing = example_vars - env_vars
    if missing:
        print("Missing environment variables in .env:")
        for var in sorted(missing):
            print(f"  {var}")
        sys.exit(1)
    else:
        print("All environment variables from .env.example are present in .env.")
        # Check for empty values
        empty_vars = [var for var, val in env_dict.items() if val == ""]
        if empty_vars:
            print("Warning: The following variables are empty in .env:")
            for var in sorted(empty_vars):
                print(f"  {var}")
        sys.exit(0)

if __name__ == '__main__':
    main()