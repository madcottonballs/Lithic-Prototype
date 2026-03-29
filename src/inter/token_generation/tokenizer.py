"""Initial entry point for text input. This file is responsible for converting raw source text into a list of tokens."""
def lexer(source_text: str):
    # Build a token list from raw source characters.
    tokens: list = [""]
    inside_quote = False
    active_quote = None

    for _, current_char in enumerate(source_text):
        token_index = len(tokens) - 1

        if inside_quote:
            tokens[token_index] += current_char
            # Close only when we hit the same quote type we opened with.
            if current_char == active_quote:
                inside_quote = False
                active_quote = None
            continue

        match current_char:
            case '+'|'-'|'*'|'/'|'('|')'|'{'|'}'|'['|']'|','|';'|'='|'!'|'>'|'<'|'^'|'$'|'#'|'&'|'?'|':':
                tokens.append(current_char)
                tokens.append('')
            case '"'|"'":
                inside_quote = True
                active_quote = current_char
                # Start quoted literal token, keeping opening quote.
                tokens.append(current_char)
            case ' ':
                tokens.append('')
            case _:
                # For any other character, we build on the existing token.
                tokens[token_index] += current_char

    # deletes empty tokens from the list, which are created by the lexer when it encounters spaces.
    token_index = 0
    while token_index < len(tokens):
        if tokens[token_index] == str():  # if token is empty
            del tokens[token_index]
        else:
            token_index += 1

    return tokens

class import_statement:
    def __init__(self, module_name: str, module_ext: str, alias: str | None = None):
        self.module_name = module_name
        self.module_ext = module_ext
        self.alias = alias

def import_lexer(source_line: str, ltc) -> list[str]:
    """A specialized lexer for import statements, which splits on ';' and has the 'as' syntax."""
    tokens = lexer(source_line)
    
    if 'as' in tokens:
        as_index = tokens.index('as')
        if as_index == 0 or as_index == len(tokens) - 1:
            ltc.error("Syntax error in import statement: 'as' cannot be the first or last token.")
        if tokens[as_index + 1][0] != '"' or tokens[as_index + 1][-1] != '"':
            ltc.error("Syntax error in import statement: alias must be a string literal.")
        
        alias = tokens[as_index + 1].strip('"')

        del tokens[as_index:as_index + 2]  # Remove 'as' and alias from tokens
    else:
        alias = None

    if tokens[0] != 'import':
        ltc.error("Syntax error in import statement: must start with 'import'.")
    
    if tokens[1][0] != '"' or tokens[1][-1] != '"':
        ltc.error("Syntax error in import statement: module name must be a string literal.")
    module_file = tokens[1].strip('"').split('.')
    if len(module_file) != 2:
        ltc.error("Syntax error in import statement: module name must include a file extension.")
    module_name, module_ext = module_file

    return_obj = import_statement(module_name, module_ext, alias)

    return return_obj