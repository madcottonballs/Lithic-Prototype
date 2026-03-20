import re

def process_imports(source_text: str) -> str:
    """Process import statements in the source text and return the modified source text."""
    # Strip block comments so the parser doesn't see stray '/' tokens.
    source_text = re.sub(r"/\*.*?\*/", "", source_text, flags=re.DOTALL)

    lines = source_text.splitlines()
    processed_lines: list[str] = []

    for line in lines:
        stripped_line = line.strip()
        if stripped_line.startswith("import "):
            # Extract the module name
            module_file = stripped_line[len("import "):].strip().strip(";").strip('"').split(".")
            module_name = module_file[0]
            module_ext = module_file[1] if len(module_file) == 2 else ""

            if not module_ext:
                raise Exception(f"Module '{module_name}' does not have a file extension.")

            try:
                with open(f"{module_name}.{module_ext}", "r") as f:
                    module_source = f.read()
            except FileNotFoundError:
                raise Exception(f"Module '{module_name}' not found.")

            # Recursively process imports in the module source
            processed_module_source = process_imports(module_source)

            # Prefix each function definition with the module name.
            for module_line in processed_module_source.splitlines():
                if module_line.strip().startswith("define "):
                    func_name = module_line.strip()[len("define "):].split("(")[0].strip()
                    module_line = module_line.replace(f"define {func_name}", f"define {module_name}.{func_name}")
                processed_lines.append(module_line)
        else:
            processed_lines.append(line)

    return "\n".join(processed_lines)
