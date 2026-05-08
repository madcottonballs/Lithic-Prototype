use std::env;
use crate::Compiler;

fn split_top_level(input: &str, delimiter: char) -> Vec<String> {
    let mut parts: Vec<String> = Vec::new();
    let mut current = String::new();
    let mut angle_depth = 0;
    let mut square_depth = 0;

    for ch in input.chars() {
        match ch {
            '<' => {
                angle_depth += 1;
                current.push(ch);
            }
            '>' => {
                if angle_depth == 0 {
                    println!("Error: Malformed composite type '{}'", input);
                    std::process::exit(1);
                }
                angle_depth -= 1;
                current.push(ch);
            }
            '[' => {
                square_depth += 1;
                current.push(ch);
            }
            ']' => {
                if square_depth == 0 {
                    println!("Error: Malformed composite type '{}'", input);
                    std::process::exit(1);
                }
                square_depth -= 1;
                current.push(ch);
            }
            _ if ch == delimiter && angle_depth == 0 && square_depth == 0 => {
                parts.push(current.trim().to_string());
                current.clear();
            }
            _ => current.push(ch),
        }
    }

    if angle_depth != 0 || square_depth != 0 {
        println!("Error: Malformed composite type '{}'", input);
        std::process::exit(1);
    }

    if !current.trim().is_empty() {
        parts.push(current.trim().to_string());
    }

    parts
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
    if compiler.using_string {
        compiler.target.insert(0, "#include <string>".to_string()); // add iostream include if using std::cout, this is needed for printing to the console in C++
        count += 1;
    }
    if compiler.using_tuple {
        compiler.target.insert(0, "#include <tuple>".to_string());
        count += 1;
    }
    return count;
}
pub fn convert_type(ltcir_type: &str) -> String { // this function converts a ltcir type to it's renamed cpp equivalent
    let trimmed = ltcir_type.trim();

    if trimmed == "array" || trimmed == "tuple" {
        return "void*".to_string();
    }

    if let Some(base_type) = trimmed.strip_suffix("[]") {
        return format!("{}*", convert_type(base_type));
    }

    if let Some(bracket_start) = trimmed.find('[') {
        if trimmed.ends_with(']') {
            let base_type = &trimmed[..bracket_start];
            return format!("{}*", convert_type(base_type));
        }
    }

    if trimmed.starts_with("tuple<") && trimmed.ends_with('>') {
        let inner = &trimmed["tuple<".len()..trimmed.len() - 1];
        let converted_parts: Vec<String> = split_top_level(inner, ',')
            .into_iter()
            .map(|part| convert_type(&part))
            .collect();
        return format!("std::tuple<{}>", converted_parts.join(", "));
    }

    match trimmed {
        "i32" => "i32".to_string(), // use fixed-width integer types from stdint.h for 32-bit integers
        "u32" => "u32".to_string(), // use fixed-width integer types from stdint.h for 32-bit integers
        "i64" => "i64".to_string(), // use fixed-width integer types from stdint.h for 64-bit integers
        "u64" => "u64".to_string(), // use fixed-width integer types from stdint.h for 64-bit integers
        "i16" => "i16".to_string(), // use fixed-width integer types from stdint.h for 16-bit integers
        "u16" => "u16".to_string(), // use fixed-width integer types from stdint.h for 16-bit integers
        "i8" => "i8".to_string(), // use fixed-width integer types from stdint.h for 8-bit integers
        "u8" => "u8".to_string(), // use fixed-width integer types from stdint.h for 8-bit integers
        "string" => "string".to_string(),
        "boolean" => "bool".to_string(),
        "char" => "char".to_string(),
        "ptr" => "void*".to_string(),
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
