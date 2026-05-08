mod parser;
use parser::Token;
mod helper;
use helper::get_sys_args;
mod compiler;
use compiler::compile_file;
use std::collections::HashMap;
use std::fs;

/*
MISSING/BUGS:
    variables of type u8 or i8 are being printed as if theyre cpp unsigned char type because of how cpp prints ints

IMPORTANT 

run a test using the command "python "src\comp\test.py""

to add new functions, add the keyword to compiler.keywords

tokens is a Vec<Token>
the Token class has 
    .value attribute (String)
        type prefixes (like | or $ or %) are NOT included in the .value attribute
        type prefixes for text data types are NOT removed ("hello world" is stored as a rust String " \"hello world\" ")
        ex: $20 is stored as "20"
    ._type attribute (String)
        ._type is resolved in parser.parser()
        ._type can be:
            generic
                means unclassified
            string
                double quoted text
            char
                single quoted text
            integer
                defined with a $ sign
            variable
                defined with a % sign
            function
                defined with a # sign
            boolean
                defined with a | sign
            arrow
                defined by .value being a "->"
            keyword
                defined by having .value be a String in compiler.keywords
            type
                defined by having .value be a String in compiler.type_names

*/


struct Compiler {
    keywords: Vec<String>,
    type_names: Vec<String>,
    target: Vec<String>,
    variable_types: HashMap<String, String>,
    using_stdlib: bool,
    using_stdio: bool,
    using_stdint: bool,
    using_iostream: bool,
    using_string: bool,
}

impl Compiler {
    fn new() -> Self {
        return Compiler { 
            keywords: vec![
                "let".into(), 
                "define".into(),
                "ret".into(),
                
                "add".into(),
                "sub".into(),
                "mult".into(),
                "div".into(),
                
                "print".into(),
                "printf".into(),
                "input".into(),
                "flush".into(),
                
                "inlinecpp".into(),
                "inlineasm".into(),

                "define".into(),
                "end".into(),
                "call".into(),
                
                "mov".into(),
                "make_var".into(),
                
                "exit".into(),
                
                "equal".into(),
                "greater".into(),
                "less".into(),
                "and".into(),
                "or".into(),
                "not".into(),

                "typeof".into(),

                "malloc".into(),
                "get_at".into(),
                "set_at".into(),
                "free".into(),
                "loc".into(),
                
                "if".into(),
                "ifnot".into(),
                "while".into(),
                "{".into(),
                "}".into(),

                ],
            type_names: vec![
                "i32".into(),
                "u32".into(),
                "i64".into(),
                "u64".into(),
                "i16".into(),
                "u16".into(),
                "i8".into(),
                "u8".into(),
                "string".into(),
                "boolean".into(),
                "char".into(),
                "ptr".into(),
            ],
            target: Vec::new(),
            variable_types: HashMap::new(),
            using_stdlib: false,
            using_stdio: false,
            using_stdint: true,
            using_iostream: false,
            using_string: true,
        }
    }
}

fn resolve_typeof_type(token: &Token, compiler: &Compiler) -> String {
    // this resolves the typeof ltcir function
    match token.type_.as_str() {
        "variable" => compiler
            .variable_types
            .get(&token.value)
            .cloned()
            .unwrap_or_else(|| {
                println!("Error: Cannot resolve type of undeclared variable '{}'", token.value);
                std::process::exit(1);
            }),
        "string" => "string".to_string(),
        "i32" => "i32".to_string(),
        "i64" => "i64".to_string(),
        "i16" => "i16".to_string(),
        "i8" => "i8".to_string(),
        "u64" => "u64".to_string(),
        "u32" => "u32".to_string(),
        "u16" => "u16".to_string(),
        "u8" => "u8".to_string(),
        "boolean" => "boolean".to_string(),
        "char" => "char".to_string(),
        "ptr" => "ptr".to_string(),
        _ => {
            println!(
                "Error: 'typeof' does not support token '{}' of parser type '{}'",
                token.value,
                token.type_
            );
            std::process::exit(1);
        }
    }
}


fn lexer(source_line: &str) -> Vec<String> {
    let mut tokens: Vec<String> = Vec::new();
    let mut current = String::new();
    let mut in_double_quote = false;
    let mut in_single_quote = false;

    for ch in source_line.chars() {
        if in_double_quote {
            current.push(ch);
            if ch == '"' {
                in_double_quote = false;
                tokens.push(current.clone());
                current.clear();
            }
            continue;
        }

        if in_single_quote {
            current.push(ch);
            if ch == '\'' {
                in_single_quote = false;
                tokens.push(current.clone());
                current.clear();
            }
            continue;
        }

        match ch {
            '"' => {
                if !current.is_empty() {
                    tokens.push(current.clone());
                    current.clear();
                }
                current.push(ch);
                in_double_quote = true;
            }
            '\'' => {
                if !current.is_empty() {
                    tokens.push(current.clone());
                    current.clear();
                }
                current.push(ch);
                in_single_quote = true;
            }
            c if c.is_whitespace() => {
                if !current.is_empty() {
                    tokens.push(current.clone());
                    current.clear();
                }
            }
            _ => current.push(ch),
        }
    }

    if !current.is_empty() {
        tokens.push(current);
    }

    tokens
}

fn check_file_ext(source_file_parts: &Vec<&str>) {
    let file_extension: &str = source_file_parts.last().unwrap_or(&""); // get file extension, this should be the last element of the source_file_parts vector, if there is no extension, use an empty string
    if file_extension != "ltcir" {
        println!("Error: Source file must have .ltcir extension");
        std::process::exit(1);
    } // check file extension, if it's not .ltcir, print error message and exit
}

fn main() {
    let args: Vec<String> = get_sys_args(); // get command line arguments, this should return a Vec<String> where the first element is the program name and the second element is the source file name

    let source_file: &str = &args[1]; // get source file name from command line arguments, this should be the second element of the args vector
    
    let source_file_parts: Vec<&str> = source_file.split('.').collect();  // split source file name by '.', this will be used to check file extension and get file name without extension
    
    check_file_ext(&source_file_parts);

    let output_file_name: String = if source_file_parts.len() > 1 {   source_file_parts[..source_file_parts.len() - 1].join(".")  } else {String::new()}; // get file name without extension, this will be used for output file name
    
    let source_code = fs::read_to_string(source_file)
        .expect("Failed to read source file"); // read source file into a string, this will be the input to the compiler
    
    // start compilation, this should return a Vec<String> where each string is a line of C code
    let target_code = compile_file(&source_code);

    // Write the generated C code to an output file with the same name but .c extension
    let output_file_name = format!("{}.cpp", output_file_name);
    fs::write(&output_file_name, target_code.join("\n"))
        .expect("Failed to write output file");
}
