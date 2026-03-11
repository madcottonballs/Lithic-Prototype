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
            case '+'|'-'|'*'|'/'|'('|')'|'{'|'}'|'['|']'|','|';'|'='|'!'|'>'|'<'|'^'|'$'|'#'|'&'|'?'|':'|'.':
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
