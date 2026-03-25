def ltc_print(ltc, tokens, i) -> None:
    t = ltc.t
    if len(tokens[i].args) != 1:
        raise SyntaxError("printf() expects exactly one argument")
    arg = tokens[i].args[0]
    if isinstance(arg, t.integer | t.string | t.boolean | t.char):
        print(arg.val, end="\n")
    elif isinstance(arg, t.array):
        rendered = ", ".join(str(element.val) for element in arg.val)
        print(f"array[{rendered}]", end="\n")
    elif isinstance(arg, t.ltctuple):
        rendered = ", ".join(str(element.val) for element in arg.val)
        print(f"tuple({rendered})", end="\n")
    else:
        raise TypeError(f"Unsupported argument type for printf(): {type(arg).__name__}")
    tokens[i] = t.i32(0)

def ltc_input(tokens, i, ltc) -> None:
    t = ltc.t
    if len(tokens[i].args) != 0:
        raise SyntaxError("input does not take any arguments")
    try:
        tokens[i] = t.string(input())
    except EOFError:
        tokens[i] = t.string("")

def resolve_coredump(tokens, i, ltc) -> None:
    if len(tokens[i].args) != 0:
        raise SyntaxError("coredump does not take any arguments")
    with open("coredump.txt", "w") as f:
        annontations: dict[int, str] = {} # memory annontations keyed by memory address for easier reading of the coredump. This is populated by things like variable declarations that know what memory addresses they are using, and can write those addresses along with variable names and types to the annontations dict. The coredump printing logic then checks this dict when printing each memory address, and if an annotation exists for that address, it prints it along with the memory value.
        f.write("===CORE DUMP===\n")
        
        f.write(f"Stack Pointer: {ltc.sp}\n===============================\n")
        f.write(f"Heap Pointer: {ltc.hp}\n===============================\n")
        annontations[ltc.sp] = "(SP)"
        annontations[ltc.hp] = "(HP)"

        f.write(f"Namespace:\n")
        for i, v in enumerate(ltc.namespace):
            f.write(f"\tFrame {i}:\n")
            for var_name, var_meta in v.items():
                f.write(f"\t\t{var_name}:\n")
                f.write(f"\t\t\ttype: {var_meta['type']}\n")
                f.write(f"\t\t\taddr: {var_meta['addr']}\n")
                if var_meta['type'] == 'array':
                    f.write(f"\t\t\tlength: {var_meta['length']}\n")
                    f.write(f"\t\t\telem_type: {var_meta['elem_type']}\n")
                if var_meta['type'] == 'tuple':
                    f.write(f"\t\t\telem_types: {var_meta['element_types']}\n")
                
                if var_meta['addr'] in annontations:                            
                    annontations[var_meta['addr']] += f" | Start of '{var_name}' of type '{var_meta['type']}'"
                else:
                    annontations[var_meta['addr']] = f"Start of '{var_name}' of type '{var_meta['type']}'"

        f.write(f"===============================\n")
        f.write("Stack Frames:\n")
        for i, v in enumerate(ltc.stack_frames):
            f.write(f"\tStack Frame {i} SP: {v}\n")
            if v in annontations:
                annontations[v] += f" | Stack frame {i} start"
            else:
                annontations[v] = f"Stack frame {i} start"

        f.write(f"===============================\n")
        f.write("Memory:\n")
        for i, v in enumerate(ltc.memory):
            if i in annontations:
                f.write(f"\t[{i}]: {v}  <-- {annontations[i]}\n")
            else:
                f.write(f"\t[{i}]: {v}\n")
    f.close()
