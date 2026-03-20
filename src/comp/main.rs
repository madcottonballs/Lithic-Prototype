use std::env;
use std::fs;

/**/
#[derive(Debug)]
struct Token {
    value: String,
    type_: String,
}
impl Token {
    fn new(value: &str, type_: &str) -> Self {
        Token {
            value: value.to_string(),
            type_: type_.to_string(),
        }
    }
}

struct Compiler {
    keywords: Vec<String>,
    type_names: Vec<String>,
}

impl Compiler {
    fn new() -> Self {
        Compiler { 
            keywords: vec![
                "let".into(), 
                "define".into(),
                "ret".into(),
                "add".into(),
                "sub".into(),
                "mul".into(),
                "div".into(),
                "printf".into(),
                "input".into(),
                "inlineC".into(),
                "define".into(),
                "end".into(),
                "call".into(),
                "mov".into(),
                "make_var".into(),
                "exit".into(),
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
            ]

        }
    }
}

fn get_sys_args() -> Vec<String> {
    let args: Vec<String> = env::args().collect();

    if args.len() < 2 {
        println!("Usage: {} <source_file>", args[0]);
        std::process::exit(1);
    }
    return args;
}

fn lexer(source_line: &str) -> Vec<String> {
    // Placeholder lexer implementation
    return source_line.split_whitespace().map(|s| s.to_string()).collect();  // split line into tokens based on whitespace
}

fn parser(intermediate: Vec<String>, compiler: &Compiler) -> Vec<Token> {
    let mut tokens: Vec<Token> = intermediate
        .into_iter()
        .map(|value| Token::new(&value, "generic"))
        .collect(); // convert Vec<String> to Vec<Token> with a generic type

    for token in tokens.iter_mut() {
        if token.type_ != "generic" {
            continue;  // skip tokens that have already been classified
        }
        if token.value.starts_with('"') && token.value.ends_with('"') {
            token.value = token.value.trim_matches('"').to_string();  // remove surrounding quotes
            token.type_ = "string".to_string();
        }
        if token.value.starts_with("$") {
            token.value = token.value.trim_start_matches('$').to_string();  // remove leading $
            token.type_ = "integer".to_string();
        }
        if token.value.starts_with("%") {
            token.value = token.value.trim_start_matches('%').to_string();  // remove leading %
            token.type_ = "variable".to_string();
        }
        if token.value.starts_with("#") {
            token.value = token.value.trim_start_matches('#').to_string();  // remove leading #
            token.type_ = "function".to_string();
        }
        if token.value.starts_with("|") {
            token.value = token.value.trim_start_matches('|').to_string();  // remove leading |
            token.type_ = "boolean".to_string();
        } 
        if token.value == "->" {
            token.type_ = "arrow".to_string();
        }
        if compiler.keywords.contains(&token.value) {
            token.type_ = "keyword".to_string();
        }
        if compiler.type_names.contains(&token.value) {
            token.type_ = "type".to_string();
        }
    }
    return tokens;
}

fn compile_file(source_file: &str) {
    let source_lines: Vec<String> = source_file.lines().map(|line| line.to_string()).collect();  // split source code into lines
    
    let compiler = Compiler::new();  // initialize compiler with keywords and type names
    
    let mut lineidx = 0;
    while lineidx < source_lines.len() {

        let line = &source_lines[lineidx];  // read line, line is &str

        let intermediate = lexer(line); // tokenize line, intermediate is Vec<String>
        let tokens: Vec<Token> = parser(intermediate, &compiler);  // give types, parser should return Vec<Token>

        println!("Line {}: {:?}", lineidx + 1, tokens); // debug
        lineidx += 1;
    }
}

fn main() {
    let args: Vec<String> = get_sys_args();

    let source_file = &args[1];
    let source_code = fs::read_to_string(source_file)
        .expect("Failed to read source file");

    compile_file(&source_code);
}
