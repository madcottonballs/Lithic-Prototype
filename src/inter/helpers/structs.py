def _field_info(ltc, struct_name: str, field_name: str) -> tuple[object, str]:
    struct_def = ltc.structs[struct_name]
    field_info = struct_def["fields"][field_name]
    if isinstance(field_info, dict):
        return field_info, field_info["kind"]
    return field_info, field_info

def _field_size(ltc, field_info) -> int:
    if isinstance(field_info, dict):
        if field_info["kind"] != "array":
            ltc.error(f"Unsupported structured field metadata kind '{field_info['kind']}'")
        elem_type = field_info["elem_type"]
        length = field_info["length"]
        if elem_type in ltc.structs:
            return get_struct_size(ltc, elem_type) * length
        return ltc.helper.get_ltc_type_size(elem_type, ltc) * length
    if field_info in ltc.structs:
        return get_struct_size(ltc, field_info)
    return ltc.helper.get_ltc_type_size(field_info, ltc)

def _empty_field_value(ltc, field_info):
    if isinstance(field_info, dict):
        if field_info["kind"] != "array":
            ltc.error(f"Unsupported structured field metadata kind '{field_info['kind']}'")
        elem_type = field_info["elem_type"]
        length = field_info["length"]
        elements = []
        for _ in range(length):
            if elem_type in ltc.structs:
                elements.append(create_struct_instance(ltc, elem_type))
            else:
                elements.append(ltc.helper.recieve_empty_form(ltc, elem_type))
        return ltc.t.array(elements, ltc, arrayType=elem_type, parse=False)
    if field_info in ltc.structs:
        return create_struct_instance(ltc, field_info)
    return ltc.helper.recieve_empty_form(ltc, field_info)

def get_struct_size(ltc, struct_name: str, _seen: set | None = None) -> int:
    if struct_name not in ltc.structs:
        ltc.error(f"Unknown struct type: {struct_name}")
    if _seen is None:
        _seen = set()
    if struct_name in _seen:
        ltc.error(f"Recursive struct definition detected for '{struct_name}'")
    _seen.add(struct_name)

    struct_def = ltc.structs[struct_name]
    fields = struct_def["fields"]
    order = struct_def["order"]
    total = 0
    for field_name in order:
        field_info = fields[field_name]
        if isinstance(field_info, dict) and field_info["kind"] == "array":
            if field_info["elem_type"] == "string":
                ltc.error(f"Struct field '{field_name}' uses dynamic element type 'string', which is not supported in memory layout yet")
        elif field_info == "string":
            ltc.error(f"Struct field '{field_name}' uses dynamic type '{field_info}', which is not supported in memory layout yet")
        total += _field_size(ltc, field_info)

    _seen.remove(struct_name)
    return total

def create_struct_instance(ltc, struct_name: str):
    if struct_name not in ltc.structs:
        ltc.error(f"Unknown struct type: {struct_name}")
    struct_def = ltc.structs[struct_name]
    fields = struct_def["fields"]
    order = struct_def["order"]
    defaults = struct_def.get("defaults", {})

    values: dict[str, object] = {}
    for field_name in order:
        field_info = fields[field_name]
        if field_name in defaults:
            values[field_name] = defaults[field_name]
        else:
            values[field_name] = _empty_field_value(ltc, field_info)
    return ltc.t.struct_instance(values, ltc, struct_name=struct_name)

def write_struct_to_memory(ltc, struct_name: str, struct_obj, memidx: int | None = None) -> None:
    if struct_name not in ltc.structs:
        ltc.error(f"Unknown struct type: {struct_name}")
    struct_def = ltc.structs[struct_name]
    fields = struct_def["fields"]
    order = struct_def["order"]
    base_addr = ltc.sp if memidx is None else memidx
    offset = 0

    for field_name in order:
        field_info = fields[field_name]
        field_value = struct_obj.val.get(field_name)

        if field_value is None:
            field_value = _empty_field_value(ltc, field_info)

        if isinstance(field_info, dict):
            if field_info["kind"] != "array":
                ltc.error(f"Unsupported structured field metadata kind '{field_info['kind']}'")
            if not isinstance(field_value, ltc.t.array):
                ltc.error(f"Struct array field '{field_name}' must be assigned an array value")
            field_value.parse(ltc)
            if field_value.arrayType != field_info["elem_type"]:
                ltc.error(
                    f"Struct array field '{field_name}' expects element type '{field_info['elem_type']}', got '{field_value.arrayType}'"
                )
            if field_value.get_size() != field_info["length"]:
                ltc.error(
                    f"Struct array field '{field_name}' expects length {field_info['length']}, got {field_value.get_size()}"
                )
            ltc.helper.load_to_mem(ltc, field_value, input_type="array", memidx=base_addr + offset)
        else:
            if field_info in ltc.structs:
                write_struct_to_memory(ltc, field_info, field_value, memidx=base_addr + offset)
            else:
                ltc.helper.load_to_mem(ltc, field_value, input_type=field_info, memidx=base_addr + offset)
        offset += _field_size(ltc, field_info)

    if memidx is None:
        ltc.sp = base_addr + offset
    struct_obj.inmemory = True
    struct_obj.memloc = base_addr
    ltc.helper.memory_bounds_check(ltc)

def read_struct_from_memory(ltc, struct_name: str, addr: int):
    if struct_name not in ltc.structs:
        ltc.error(f"Unknown struct type: {struct_name}")
    struct_def = ltc.structs[struct_name]
    fields = struct_def["fields"]
    order = struct_def["order"]
    values: dict[str, object] = {}
    offset = 0
    for field_name in order:
        field_info = fields[field_name]
        if isinstance(field_info, dict):
            if field_info["kind"] != "array":
                ltc.error(f"Unsupported structured field metadata kind '{field_info['kind']}'")
            elem_type = field_info["elem_type"]
            length = field_info["length"]
            elements = []
            elem_addr = addr + offset
            if elem_type in ltc.structs:
                elem_size = get_struct_size(ltc, elem_type)
                for index in range(length):
                    elements.append(read_struct_from_memory(ltc, elem_type, elem_addr + (index * elem_size)))
            else:
                elem_size = ltc.helper.get_ltc_type_size(elem_type, ltc)
                for index in range(length):
                    elements.append(ltc.helper.read_ltc_type_from_mem(ltc.memory, elem_addr + (index * elem_size), elem_type, ltc))
            array_obj = ltc.t.array(elements, ltc, arrayType=elem_type, parse=False)
            array_obj.size = length
            array_obj.inmemory = True
            array_obj.memloc = elem_addr
            values[field_name] = array_obj
        elif field_info in ltc.structs:
            nested = read_struct_from_memory(ltc, field_info, addr + offset)
            values[field_name] = nested
        else:
            values[field_name] = ltc.helper.read_ltc_type_from_mem(ltc.memory, addr + offset, field_info, ltc)
        offset += _field_size(ltc, field_info)
    struct_obj = ltc.t.struct_instance(values, ltc, struct_name=struct_name)
    struct_obj.inmemory = True
    struct_obj.memloc = addr
    return struct_obj

def update_struct_field_in_memory(ltc, struct_name: str, field_name: str, new_value, struct_addr: int) -> None:
    """Updates a specific field of a struct instance in memory. This is used for assignment to struct fields.
    \nIt calculates the correct memory offset for the field and writes the new value to that location.
    \nArgs are error checked in this function.
    \nargs: \n- struct_name: the name of the struct type \n- field_name: the name of the field to update \n- new_value: the new object to write \n- struct_addr: the base memory address of the struct instance to update"""
    if struct_name not in ltc.structs:
        ltc.error(f"Unknown struct type: {struct_name}")
    struct_def = ltc.structs[struct_name]
    fields = struct_def["fields"]
    order = struct_def["order"]
    if field_name not in fields:
        ltc.error(f"Struct '{struct_name}' has no field named '{field_name}'")
    field_info = fields[field_name]

    offset = 0
    for fname in order:
        if fname == field_name:
            break
        offset += _field_size(ltc, fields[fname])

    if isinstance(field_info, dict):
        if field_info["kind"] != "array":
            ltc.error(f"Unsupported structured field metadata kind '{field_info['kind']}'")
        if not isinstance(new_value, ltc.t.array):
            ltc.error(f"Struct array field '{field_name}' must be assigned an array value")
        new_value.parse(ltc)
        if new_value.arrayType != field_info["elem_type"]:
            ltc.error(
                f"Struct array field '{field_name}' expects element type '{field_info['elem_type']}', got '{new_value.arrayType}'"
            )
        if new_value.get_size() != field_info["length"]:
            ltc.error(
                f"Struct array field '{field_name}' expects length {field_info['length']}, got {new_value.get_size()}"
            )
        ltc.helper.load_to_mem(ltc, new_value, input_type="array", memidx=struct_addr + offset)
    elif field_info in ltc.structs:
        write_struct_to_memory(ltc, field_info, new_value, memidx=struct_addr + offset)
    else:
        ltc.helper.load_to_mem(ltc, new_value, input_type=field_info, memidx=struct_addr + offset)

def read_struct_field_from_memory(ltc, struct_name: str, field_name: str, struct_addr: int) -> object:
    if struct_name not in ltc.structs:
        ltc.error(f"Unknown struct type: {struct_name}")
    struct_def = ltc.structs[struct_name]
    fields = struct_def["fields"]
    order = struct_def["order"]
    if field_name not in fields:
        ltc.error(f"Struct '{struct_name}' has no field named '{field_name}'")
    field_info = fields[field_name]

    offset = 0
    for fname in order:
        if fname == field_name:
            break
        offset += _field_size(ltc, fields[fname])

    if isinstance(field_info, dict):
        if field_info["kind"] != "array":
            ltc.error(f"Unsupported structured field metadata kind '{field_info['kind']}'")
        elem_type = field_info["elem_type"]
        length = field_info["length"]
        elements = []
        elem_addr = struct_addr + offset
        if elem_type in ltc.structs:
            elem_size = get_struct_size(ltc, elem_type)
            for index in range(length):
                elements.append(read_struct_from_memory(ltc, elem_type, elem_addr + (index * elem_size)))
        else:
            elem_size = ltc.helper.get_ltc_type_size(elem_type, ltc)
            for index in range(length):
                elements.append(ltc.helper.read_ltc_type_from_mem(ltc.memory, elem_addr + (index * elem_size), elem_type, ltc))
        array_obj = ltc.t.array(elements, ltc, arrayType=elem_type, parse=False)
        array_obj.size = length
        array_obj.inmemory = True
        array_obj.memloc = elem_addr
        return array_obj
    if field_info in ltc.structs:
        return read_struct_from_memory(ltc, field_info, struct_addr + offset)
    else:
        return ltc.helper.read_ltc_type_from_mem(ltc.memory, struct_addr + offset, field_info, ltc)
