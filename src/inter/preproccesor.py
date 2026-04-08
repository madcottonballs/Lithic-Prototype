import re

def process_imports(source_text: str, ltc) -> str:
    """Process import statements in the source text and return the modified source text."""
    # Strip block comments so the parser doesn't see stray '/' tokens.
    source_text = re.sub(r"/\*.*?\*/", "", source_text, flags=re.DOTALL)

    lines = source_text.splitlines()
    processed_lines: list[str] = []
    for line in lines:
        ltc.current_stmt = line.strip() # for better error messages in the case of an error during import processing
        
        stripped_line = line.strip()
        if stripped_line.startswith("import "):
            # Extract the module name
            stripped_line = ltc.helper.strip_comments(stripped_line, ltc) # strip comments from the import line as well, in case there are any
            import_stmt = ltc.tokenizer.import_lexer(stripped_line, ltc)
            module_name = import_stmt.module_name
            module_ext = import_stmt.module_ext
            module_alias = import_stmt.alias or module_name

            try:
                with open(f"{module_name}.{module_ext}", "r") as f:
                    module_source = f.read()
            except FileNotFoundError:
                try: # try to check if it's in the stdlib directory
                    with open(f"{ltc.STDLIB_PATH}\\{module_name}.{module_ext}", "r") as f:
                        module_source = f.read()
                except FileNotFoundError:
                    ltc.error(f"Module {module_name}.{module_ext} not found. Tried checking stdlib under: '{ltc.STDLIB_PATH}\\{module_name}.{module_ext}', but also couldn't find it.")

            # Recursively process imports in the module source
            processed_module_source = process_imports(module_source, ltc)

            # Prefix each function definition with the module name.
            for module_line in processed_module_source.splitlines():
                if module_line.strip().startswith("define "):
                    func_name = module_line.strip()[len("define "):].split("(")[0].strip()
                    module_line = module_line.replace(f"define {func_name}", f"define {module_alias}.{func_name}")
                processed_lines.append(module_line)
            
            # stores aliases for usage with dot operators
            ltc.aliases.append(module_alias)
        else:
            processed_lines.append(line)

    return "\n".join(processed_lines)
