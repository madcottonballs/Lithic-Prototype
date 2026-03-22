use std::env;
use Compiler;

pub fn c_type_to_formatter(ltcir_type: &str) -> &str {
    match ltcir_type {
        "int" => "%d",
        "short" => "%hd",
        "unsigned short" => "%hu",
        "unsigned int" => "%u",
        "long long" => "%lld",
        "unsigned long long" => "%llu",
        "char" => "%c",
        "char*" => "%s",
        "_Bool" => "%d", // we'll print booleans as integers (0 or 1)
        _ => {
            println!("Error: Unknown C type '{}' for printf formatter", ltcir_type);
            std::process::exit(1);
        }
    }
}
pub fn resolve_includes(compiler: &mut Compiler) -> usize{ // this function will add necessary includes at the top of the generated C code based on what features are used in the source code, it will return the number of includes added, this is needed to determine where to insert function prototypes later
    let mut count = 0;
    if compiler.using_stdlib {
        compiler.target.insert(0, "#include <stdlib.h>".to_string()); // add stdio.h include if not using stdlib, this is needed for printf and other standard library functions
        count += 1;
    }
    if compiler.using_stdio {
        compiler.target.insert(0, "#include <stdio.h>".to_string()); // add stdio.h include if not using stdlib, this is needed for printf and other standard library functions
        count += 1;
    }
    if compiler.using_stdint {
        compiler.target.insert(0, "#include <stdint.h>".to_string()); // add stdint.h include if using fixed-width integer types like int32_t, this is needed for the corresponding printf formatters
        count += 1;
    }
    if compiler.using_iostream {
        compiler.target.insert(0, "#include <iostream>".to_string()); // add iostream include if using std::cout, this is needed for printing to the console in C++
        count += 1;
    }
    return count;
}
pub fn convert_type(ltcir_type: &str) -> &str {
    match ltcir_type {
        "i32" => "i32", // use fixed-width integer types from stdint.h for 32-bit integers
        "u32" => "u32", // use fixed-width integer types from stdint.h for 32-bit integers
        "i64" => "i64", // use fixed-width integer types from stdint.h for 64-bit integers
        "u64" => "u64", // use fixed-width integer types from stdint.h for 64-bit integers
        "i16" => "i16", // use fixed-width integer types from stdint.h for 16-bit integers
        "u16" => "u16", // use fixed-width integer types from stdint.h for 16-bit integers
        "i8" => "i8", // use fixed-width integer types from stdint.h for 8-bit integers
        "u8" => "u8", // use fixed-width integer types from stdint.h for 8-bit integers
        "string" => "char*",
        "boolean" => "_Bool",
        "char" => "char",
        _ => {
            println!("Error: Unknown type '{}'", ltcir_type);
            std::process::exit(1);
        }
    }
}

pub fn get_sys_args() -> Vec<String> {
    let args: Vec<String> = env::args().collect();

    if args.len() < 2 {
        println!("Usage: {} <source_file>", args[0]);
        std::process::exit(1);
    }
    return args;
}

pub fn format_param_list(params_combined: &Vec<String>) -> String {
    if params_combined.is_empty() {
        "void".to_string()
    } else {
        params_combined.join(", ")
    }
}
