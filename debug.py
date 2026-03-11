import main
def print_tree(tokens, layers):  # debug
    # Pretty-prints the current AST/tree state with tab indentation.

    # Single-node handling.
    if isinstance(tokens, function):
        print("\t" * layers + "FUNCTION: " + tokens.val)
        for arg in tokens.args:
            print_tree(arg, layers + 1)
        return
    if isinstance(tokens, main.AST.string):
        print("\t" * layers + '"' + tokens.val + '"')
        return
    if isinstance(tokens, main.dword):
        print("\t" * layers + str(tokens.val))
        return
    if isinstance(tokens, main.string):
        print("\t" * layers + '"' + tokens.val + '"')
        return
    elif isinstance(tokens, main.add):
        print("\t" * layers + "AST.add")
        print_tree(tokens.node1, layers)
        print_tree(tokens.node2, layers)
        return
    elif isinstance(tokens, main.mult):
        print("\t" * layers + "AST.mult")
        print_tree(tokens.node1, layers)
        print_tree(tokens.node2, layers)
        return
    elif isinstance(tokens, main.sub):
        print("\t" * layers + "AST.sub")
        print_tree(tokens.node1, layers)
        print_tree(tokens.node2, layers)
        return
    elif isinstance(tokens, main.div):
        print("\t" * layers + "AST.div")
        print_tree(tokens.node1, layers)
        print_tree(tokens.node2, layers)
        return
    elif isinstance(tokens, main.token):
        print("\t" * layers + "AST.token: " + tokens.val)
        return

    # A AST.sub-expression contains another list/tree.
    if isinstance(tokens, main.subexp):
        print_tree(tokens.val, layers + 1)
        return
    
    i = 0
    # List handling.
    while i < len(tokens):
        if isinstance(tokens[i], main.dword):
            print("\t" * layers, tokens[i].val)

        elif isinstance(tokens[i], main.add):
            print("\t" * layers + "AST.add")
            print_tree(tokens[i].node1, layers)
            print_tree(tokens[i].node2, layers)

        elif isinstance(tokens[i], main.sub):
            print("\t" * layers + "AST.sub")
            print_tree(tokens[i].node1, layers)
            print_tree(tokens[i].node2, layers)

        elif isinstance(tokens[i], main.mult):
            print("\t" * layers + "AST.mult")
            print_tree(tokens[i].node1, layers)
            print_tree(tokens[i].node2, layers)

        elif isinstance(tokens[i], main.div):
            print("\t" * layers + "AST.div")
            print_tree(tokens[i].node1, layers)
            print_tree(tokens[i].node2, layers)

        elif isinstance(tokens[i], main.subexp):
            print_tree(tokens[i].val, layers + 1)
        elif isinstance(tokens[i], function):
            print("\t" * layers + "FUNCTION: " + tokens[i].val)
            for arg in tokens[i].args:
                print_tree(arg, layers + 1)
            return
        elif isinstance(tokens[i], main.string):
            print("\t" * layers + '"' + tokens[i].val + '"')
            return
        elif isinstance(tokens[i], main.token):
            print("\t" * layers + "AST.token: " + tokens[i].val)
            return

        i += 1
