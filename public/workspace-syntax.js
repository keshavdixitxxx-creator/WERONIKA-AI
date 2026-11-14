// Syntax colouring for the Weronika Workspace editor.
//
// A small, dependency-free tokenizer: it never needs the network, never executes the
// code it colours, and always returns exactly the characters it was given (wrapped in
// <span class="tk-…"> elements), so the coloured layer lines up with the text area.

const words = (list) => new Set(list.split(" "));

const JS_KEYWORDS =
  "as async await break case catch class const continue debugger default delete do else enum export extends finally for from function get if implements import in instanceof interface let new of package private protected public return set static super switch this throw try typeof var void while with yield";
const TS_KEYWORDS = `${JS_KEYWORDS} abstract any asserts bigint boolean declare infer is keyof module namespace never number object override readonly satisfies string symbol type unique unknown`;
const JS_BUILTINS =
  "Array Boolean Date Error JSON Map Math Number Object Promise Proxy Reflect RegExp Set String Symbol WeakMap WeakSet console document window globalThis fetch localStorage sessionStorage navigator setTimeout setInterval clearTimeout clearInterval requestAnimationFrame parseInt parseFloat isNaN";
const C_COMMENTS = { line: ["//"], block: [["/*", "*/"]] };

const SPECS = {
  javascript: {
    ...C_COMMENTS,
    strings: "\"'",
    multi: "`",
    regex: true,
    decorators: true,
    keywords: words(JS_KEYWORDS),
    constants: words("true false null undefined NaN Infinity"),
    builtins: words(JS_BUILTINS),
  },
  typescript: {
    ...C_COMMENTS,
    strings: "\"'",
    multi: "`",
    regex: true,
    decorators: true,
    keywords: words(TS_KEYWORDS),
    constants: words("true false null undefined NaN Infinity"),
    builtins: words(JS_BUILTINS),
  },
  python: {
    line: ["#"],
    block: [],
    strings: "\"'",
    triple: true,
    decorators: true,
    keywords: words(
      "and as assert async await break case class continue def del elif else except finally for from global if import in is lambda match nonlocal not or pass raise return try while with yield",
    ),
    constants: words("True False None self cls"),
    builtins: words(
      "abs all any bool bytes callable chr classmethod dict dir divmod enumerate eval exec filter float format frozenset getattr hasattr hash help hex id input int isinstance issubclass iter len list map max min next object oct open ord pow print property range repr reversed round set setattr slice sorted staticmethod str sum super tuple type vars zip Exception ValueError TypeError KeyError IndexError RuntimeError StopIteration",
    ),
  },
  java: {
    ...C_COMMENTS,
    strings: "\"'",
    triple: true,
    decorators: true,
    keywords: words(
      "abstract assert boolean break byte case catch char class const continue default do double else enum extends final finally float for goto if implements import instanceof int interface long native new package private protected public record return sealed short static strictfp super switch synchronized this throw throws transient try var void volatile while yield",
    ),
    constants: words("true false null"),
    builtins: words("String Integer Long Double Boolean Object List Map Set System Math Optional"),
  },
  c: {
    ...C_COMMENTS,
    strings: "\"'",
    preprocessor: true,
    keywords: words(
      "auto break case char const continue default do double else enum extern float for goto if inline int long register restrict return short signed sizeof static struct switch typedef union unsigned void volatile while",
    ),
    constants: words("true false NULL"),
    builtins: words(
      "printf scanf malloc calloc realloc free size_t uint8_t uint16_t uint32_t uint64_t int8_t int16_t int32_t int64_t bool FILE",
    ),
  },
  cpp: {
    ...C_COMMENTS,
    strings: "\"'",
    preprocessor: true,
    keywords: words(
      "alignas alignof auto bool break case catch char class const constexpr const_cast continue decltype default delete do double dynamic_cast else enum explicit export extern final float for friend goto if inline int long mutable namespace new noexcept operator override private protected public register reinterpret_cast return short signed sizeof static static_cast struct switch template this throw try typedef typeid typename union unsigned using virtual void volatile while",
    ),
    constants: words("true false nullptr NULL"),
    builtins: words(
      "std string vector map set cout cin endl size_t unique_ptr shared_ptr make_unique make_shared",
    ),
  },
  csharp: {
    ...C_COMMENTS,
    strings: "\"'",
    preprocessor: true,
    keywords: words(
      "abstract as async await base bool break byte case catch char checked class const continue decimal default delegate do double else enum event explicit extern finally fixed float for foreach get goto if implicit in init int interface internal is lock long namespace new object operator out override params partial private protected public readonly record ref return sbyte sealed set short sizeof stackalloc static string struct switch this throw try typeof uint ulong unchecked unsafe ushort using var virtual void volatile when where while yield",
    ),
    constants: words("true false null"),
    builtins: words("Console String List Dictionary Task Math Guid DateTime"),
  },
  go: {
    ...C_COMMENTS,
    strings: "\"'",
    multi: "`",
    keywords: words(
      "break case chan const continue default defer else fallthrough for func go goto if import interface map package range return select struct switch type var",
    ),
    constants: words("true false nil iota"),
    builtins: words(
      "append cap close complex copy delete imag len make new panic print println real recover bool byte error float32 float64 int int8 int16 int32 int64 rune string uint uint8 uint16 uint32 uint64 uintptr any",
    ),
  },
  rust: {
    ...C_COMMENTS,
    strings: '"',
    keywords: words(
      "as async await break const continue crate dyn else enum extern fn for if impl in let loop match mod move mut pub ref return self Self static struct super trait type unsafe use where while",
    ),
    constants: words("true false"),
    builtins: words(
      "bool char f32 f64 i8 i16 i32 i64 i128 isize str u8 u16 u32 u64 u128 usize String Vec Option Result Some None Ok Err Box",
    ),
  },
  kotlin: {
    ...C_COMMENTS,
    strings: "\"'",
    triple: true,
    decorators: true,
    keywords: words(
      "abstract actual annotation as break by catch class companion const constructor continue crossinline data do else enum expect external final finally for fun get if import in infix init inline inner interface internal is lateinit noinline object open operator out override package private protected public reified return sealed set super suspend tailrec this throw try typealias val var vararg when where while",
    ),
    constants: words("true false null"),
    builtins: words("String Int Long Double Float Boolean Unit Any List Map Set println print"),
  },
  swift: {
    ...C_COMMENTS,
    strings: '"',
    triple: true,
    decorators: true,
    keywords: words(
      "actor any as associatedtype async await break case catch class continue default defer deinit do else enum extension fallthrough fileprivate final for func guard if import in indirect init inout internal is lazy let mutating nonisolated open operator override private protocol public repeat rethrows return self Self some static struct subscript super switch throw throws try typealias var weak where while",
    ),
    constants: words("true false nil"),
    builtins: words("String Int Double Float Bool Array Dictionary Set Optional print"),
  },
  dart: {
    ...C_COMMENTS,
    strings: "\"'",
    triple: true,
    decorators: true,
    keywords: words(
      "abstract as assert async await base break case catch class const continue covariant default deferred do dynamic else enum export extends extension external factory final finally for get hide if implements import in interface is late library mixin new on operator part required rethrow return sealed set show static super switch sync this throw try typedef var void when while with yield",
    ),
    constants: words("true false null"),
    builtins: words("String int double bool num List Map Set Future Stream Widget print"),
  },
  php: {
    line: ["//", "#"],
    block: [["/*", "*/"]],
    strings: "\"'",
    dollar: true,
    keywords: words(
      "abstract and array as break callable case catch class clone const continue declare default do echo else elseif empty enum extends final finally fn for foreach function global goto if implements include include_once instanceof insteadof interface isset list match namespace new or print private protected public readonly require require_once return static switch throw trait try unset use var while xor yield",
    ),
    constants: words("true false null TRUE FALSE NULL"),
    builtins: words(
      "count strlen str_replace array_map array_filter json_encode json_decode var_dump",
    ),
  },
  scala: {
    ...C_COMMENTS,
    strings: "\"'",
    triple: true,
    decorators: true,
    keywords: words(
      "abstract case catch class def do else enum export extends final finally for given if implicit import lazy match new object override package private protected return sealed super then this throw trait try type using val var while with yield",
    ),
    constants: words("true false null"),
    builtins: words(
      "String Int Long Double Boolean Unit Any List Map Set Option Some None println",
    ),
  },
  ruby: {
    line: ["#"],
    block: [],
    strings: "\"'",
    hashNeedsSpace: true,
    keywords: words(
      "alias and begin break case class def defined do else elsif end ensure for if in module next not or redo rescue retry return self super then undef unless until when while yield require require_relative attr_accessor attr_reader attr_writer",
    ),
    constants: words("true false nil"),
    builtins: words("puts print p Array Hash String Integer Float Symbol"),
  },
  shell: {
    line: ["#"],
    block: [],
    strings: "\"'",
    dollar: true,
    hashNeedsSpace: true,
    keywords: words(
      "if then else elif fi for in do done while until case esac function return export local readonly declare unset shift exit break continue source alias",
    ),
    constants: words("true false"),
    builtins: words(
      "echo printf read cd set trap eval exec test pwd ls cat grep sed awk mkdir rm cp mv chmod curl",
    ),
  },
  powershell: {
    line: ["#"],
    block: [["<#", "#>"]],
    strings: "\"'",
    dollar: true,
    ci: true,
    keywords: words(
      "begin break catch class continue data do dynamicparam else elseif end enum exit filter finally for foreach from function if in param process return switch throw trap try until using var while",
    ),
    constants: words("true false null"),
    builtins: words("write-host write-output get-item set-item get-content set-content"),
  },
  batch: {
    line: ["::"],
    block: [],
    strings: '"',
    ci: true,
    keywords: words(
      "echo off on set setlocal endlocal if else for in do goto call exit rem pause exist not defined cd start errorlevel",
    ),
    constants: words(""),
    builtins: words(""),
  },
  sql: {
    line: ["--"],
    block: [["/*", "*/"]],
    strings: "'\"",
    ci: true,
    keywords: words(
      "select from where insert into values update set delete create table alter drop index view join inner left right full outer on as and or not is in like between group by order having limit offset union all distinct primary key foreign references default constraint unique check if exists begin commit rollback transaction case when then else end asc desc",
    ),
    constants: words("null true false"),
    builtins: words(
      "integer int text varchar char boolean date timestamp real float numeric serial count sum avg min max coalesce now",
    ),
  },
  lua: {
    line: ["--"],
    block: [["--[[", "]]"]],
    strings: "\"'",
    keywords: words(
      "and break do else elseif end for function goto if in local not or repeat return then until while",
    ),
    constants: words("true false nil"),
    builtins: words("print pairs ipairs require tostring tonumber type table string math"),
  },
  r: {
    line: ["#"],
    block: [],
    strings: "\"'",
    keywords: words("if else repeat while function for next break in library require return"),
    constants: words("TRUE FALSE NULL NA Inf NaN"),
    builtins: words("c print paste length mean sum seq data.frame list"),
  },
  perl: {
    line: ["#"],
    block: [],
    strings: "\"'",
    dollar: true,
    hashNeedsSpace: true,
    keywords: words(
      "my our local sub if elsif else unless while until for foreach do last next redo return use require package",
    ),
    constants: words("undef"),
    builtins: words("print say die warn push pop shift unshift keys values scalar"),
  },
  elixir: {
    line: ["#"],
    block: [],
    strings: "\"'",
    triple: true,
    decorators: true,
    keywords: words(
      "def defp defmodule defmacro defstruct defprotocol defimpl do end fn if else unless case cond when with for in and or not import alias require use raise rescue try catch after receive",
    ),
    constants: words("true false nil"),
    builtins: words("IO Enum Map List String Kernel"),
  },
  graphql: {
    line: ["#"],
    block: [],
    strings: '"',
    triple: true,
    decorators: true,
    keywords: words(
      "query mutation subscription fragment on type interface union enum input scalar schema extend directive implements",
    ),
    constants: words("true false null"),
    builtins: words("ID String Int Float Boolean"),
  },
  proto: {
    ...C_COMMENTS,
    strings: "\"'",
    keywords: words(
      "syntax package import option message enum service rpc returns repeated optional required oneof map reserved stream extend",
    ),
    constants: words("true false"),
    builtins: words(
      "double float int32 int64 uint32 uint64 sint32 sint64 fixed32 fixed64 bool string bytes",
    ),
  },
};

const EXTENSIONS = {
  py: ["python", "Python"],
  js: ["javascript", "JavaScript"],
  mjs: ["javascript", "JavaScript"],
  cjs: ["javascript", "JavaScript"],
  jsx: ["javascript", "JavaScript JSX"],
  ts: ["typescript", "TypeScript"],
  tsx: ["typescript", "TypeScript JSX"],
  vue: ["markup", "Vue"],
  svelte: ["markup", "Svelte"],
  html: ["markup", "HTML"],
  xml: ["markup", "XML"],
  css: ["css", "CSS"],
  scss: ["css", "SCSS"],
  json: ["json", "JSON"],
  md: ["markdown", "Markdown"],
  txt: ["plain", "Plain Text"],
  toml: ["config", "TOML"],
  yaml: ["config", "YAML"],
  yml: ["config", "YAML"],
  java: ["java", "Java"],
  kt: ["kotlin", "Kotlin"],
  kts: ["kotlin", "Kotlin"],
  cs: ["csharp", "C#"],
  c: ["c", "C"],
  h: ["c", "C Header"],
  cpp: ["cpp", "C++"],
  hpp: ["cpp", "C++ Header"],
  go: ["go", "Go"],
  rs: ["rust", "Rust"],
  rb: ["ruby", "Ruby"],
  php: ["php", "PHP"],
  sql: ["sql", "SQL"],
  sh: ["shell", "Shell Script"],
  bash: ["shell", "Shell Script"],
  swift: ["swift", "Swift"],
  dart: ["dart", "Dart"],
  lua: ["lua", "Lua"],
  r: ["r", "R"],
  scala: ["scala", "Scala"],
  graphql: ["graphql", "GraphQL"],
  proto: ["proto", "Protocol Buffers"],
  ex: ["elixir", "Elixir"],
  exs: ["elixir", "Elixir"],
  pl: ["perl", "Perl"],
  ps1: ["powershell", "PowerShell"],
  bat: ["batch", "Batch"],
};

/** Language id and display name for a workspace path. */
export function languageForPath(path) {
  const name = String(path || "");
  const dot = name.lastIndexOf(".");
  const extension = dot >= 0 ? name.slice(dot + 1).toLowerCase() : "";
  const [id, label] = EXTENSIONS[extension] || ["plain", "Plain Text"];
  return { id, name: label, extension };
}

export function escapeHtml(text) {
  return String(text).replace(/[&<>]/g, (char) =>
    char === "&" ? "&amp;" : char === "<" ? "&lt;" : "&gt;",
  );
}

function span(type, text) {
  if (!text) return "";
  return type ? `<span class="tk-${type}">${escapeHtml(text)}</span>` : escapeHtml(text);
}

const IDENTIFIER = /[\p{L}_$][\p{L}\p{N}_$]*/uy;
const NUMBER =
  /0[xX][\da-fA-F_]+|0[bB][01_]+|0[oO][0-7_]+|\d[\d_]*(?:\.\d[\d_]*)?(?:[eE][+-]?\d+)?[a-zA-Z%]*/y;
const OPERATORS = "+-*/%=<>!&|^~?:;,.()[]{}@#\\";
const REGEX_AFTER = new Set([
  "",
  "(",
  ",",
  "=",
  ":",
  "[",
  "!",
  "&",
  "|",
  "?",
  "{",
  "}",
  ";",
  "+",
  "-",
  "*",
  "%",
  "<",
  ">",
  "~",
  "^",
  "return",
  "typeof",
  "case",
  "in",
  "of",
  "delete",
  "void",
  "throw",
  "new",
  "yield",
  "await",
]);

// A name that follows one of these keywords is a type, even when "(" comes next.
const TYPE_AFTER = new Set([
  "class",
  "interface",
  "struct",
  "enum",
  "trait",
  "extends",
  "implements",
  "new",
  "type",
  "namespace",
  "protocol",
  "extension",
  "impl",
  "record",
  "object",
  "defmodule",
]);

function endOfQuoted(text, start, quote, multiline) {
  let index = start + 1;
  while (index < text.length) {
    const char = text[index];
    if (char === "\\") {
      index += 2;
      continue;
    }
    if (char === quote) return index + 1;
    if (char === "\n" && !multiline) return index;
    index += 1;
  }
  return text.length;
}

function endOfRegex(text, start) {
  let index = start + 1;
  let inClass = false;
  while (index < text.length) {
    const char = text[index];
    if (char === "\n") return -1;
    if (char === "\\") {
      index += 2;
      continue;
    }
    if (char === "[") inClass = true;
    else if (char === "]") inClass = false;
    else if (char === "/" && !inClass) {
      index += 1;
      while (index < text.length && /[a-z]/i.test(text[index])) index += 1;
      return index;
    }
    index += 1;
  }
  return -1;
}

function nextSignificant(text, index) {
  while (index < text.length && (text[index] === " " || text[index] === "\t")) index += 1;
  return text[index] || "";
}

function tokenizeGeneric(text, spec) {
  const out = [];
  const size = text.length;
  let index = 0;
  let previous = "";
  while (index < size) {
    const char = text[index];
    if (char === " " || char === "\t" || char === "\n" || char === "\r") {
      let end = index + 1;
      while (end < size && /\s/.test(text[end])) end += 1;
      out.push(text.slice(index, end));
      index = end;
      continue;
    }

    let matched = false;
    for (const [open, close] of spec.block || []) {
      if (!text.startsWith(open, index)) continue;
      const found = text.indexOf(close, index + open.length);
      const end = found < 0 ? size : found + close.length;
      out.push(span("c", text.slice(index, end)));
      index = end;
      matched = true;
      break;
    }
    if (matched) continue;
    for (const mark of spec.line || []) {
      if (!text.startsWith(mark, index)) continue;
      if (spec.hashNeedsSpace && mark === "#" && index > 0 && !/\s/.test(text[index - 1])) continue;
      const found = text.indexOf("\n", index);
      const end = found < 0 ? size : found;
      out.push(span("c", text.slice(index, end)));
      index = end;
      matched = true;
      break;
    }
    if (matched) continue;

    if (spec.triple && (char === '"' || char === "'") && text.startsWith(char.repeat(3), index)) {
      const found = text.indexOf(char.repeat(3), index + 3);
      const end = found < 0 ? size : found + 3;
      out.push(span("s", text.slice(index, end)));
      index = end;
      previous = "string";
      continue;
    }
    if (spec.multi && spec.multi.includes(char)) {
      const end = endOfQuoted(text, index, char, true);
      out.push(span("s", text.slice(index, end)));
      index = end;
      previous = "string";
      continue;
    }
    if (spec.strings && spec.strings.includes(char)) {
      const end = endOfQuoted(text, index, char, false);
      out.push(span("s", text.slice(index, end)));
      index = end;
      previous = "string";
      continue;
    }
    if (spec.regex && char === "/" && REGEX_AFTER.has(previous)) {
      const end = endOfRegex(text, index);
      if (end > 0) {
        out.push(span("r", text.slice(index, end)));
        index = end;
        previous = "string";
        continue;
      }
    }
    if ((char >= "0" && char <= "9") || (char === "." && /\d/.test(text[index + 1] || ""))) {
      NUMBER.lastIndex = char === "." ? index + 1 : index;
      const match = NUMBER.exec(text);
      if (match) {
        const end = NUMBER.lastIndex;
        out.push(span("n", text.slice(index, end)));
        index = end;
        previous = "number";
        continue;
      }
    }
    if (spec.decorators && char === "@" && /[\p{L}_]/u.test(text[index + 1] || "")) {
      let end = index + 1;
      while (end < size && /[\p{L}\p{N}_.]/u.test(text[end])) end += 1;
      out.push(span("v", text.slice(index, end)));
      index = end;
      previous = "identifier";
      continue;
    }
    if (spec.dollar && char === "$") {
      let end = index + 1;
      if (text[end] === "{") {
        const found = text.indexOf("}", end);
        end = found < 0 || text.slice(end, found).includes("\n") ? end : found + 1;
      } else {
        while (end < size && /[\p{L}\p{N}_]/u.test(text[end])) end += 1;
      }
      if (end > index + 1) {
        out.push(span("v", text.slice(index, end)));
        index = end;
        previous = "identifier";
        continue;
      }
    }
    if (spec.preprocessor && char === "#") {
      const lineStart = text.lastIndexOf("\n", index - 1) + 1;
      if (!text.slice(lineStart, index).trim()) {
        let end = index + 1;
        while (end < size && /[a-z]/i.test(text[end])) end += 1;
        out.push(span("k", text.slice(index, end)));
        index = end;
        previous = "keyword";
        continue;
      }
    }

    IDENTIFIER.lastIndex = index;
    const identifier = IDENTIFIER.exec(text);
    if (identifier) {
      const word = identifier[0];
      const end = index + word.length;
      const key = spec.ci ? word.toLowerCase() : word;
      let type = "";
      if (previous === "." && !spec.ci) type = nextSignificant(text, end) === "(" ? "f" : "a";
      else if (spec.keywords.has(key)) type = "k";
      else if (spec.constants.has(key)) type = "b";
      else if (TYPE_AFTER.has(previous)) type = "t";
      else if (nextSignificant(text, end) === "(") type = "f";
      else if (spec.builtins.has(key)) type = "b";
      else if (/^[A-Z][A-Z0-9_]+$/.test(word)) type = "b";
      else if (/^[A-Z]/.test(word)) type = "t";
      out.push(span(type, word));
      index = end;
      previous = type === "k" ? word : "identifier";
      continue;
    }

    out.push(OPERATORS.includes(char) ? span("o", char) : escapeHtml(char));
    previous = char;
    index += 1;
  }
  return out.join("");
}

function tokenizeJson(text) {
  const out = [];
  const size = text.length;
  let index = 0;
  while (index < size) {
    const char = text[index];
    if (char === '"') {
      const end = endOfQuoted(text, index, '"', false);
      let after = end;
      while (after < size && /\s/.test(text[after])) after += 1;
      out.push(span(text[after] === ":" ? "a" : "s", text.slice(index, end)));
      index = end;
      continue;
    }
    if (char === "-" || (char >= "0" && char <= "9")) {
      NUMBER.lastIndex = char === "-" ? index + 1 : index;
      if (NUMBER.exec(text)) {
        out.push(span("n", text.slice(index, NUMBER.lastIndex)));
        index = NUMBER.lastIndex;
        continue;
      }
    }
    if (text.startsWith("//", index)) {
      const found = text.indexOf("\n", index);
      const end = found < 0 ? size : found;
      out.push(span("c", text.slice(index, end)));
      index = end;
      continue;
    }
    IDENTIFIER.lastIndex = index;
    const identifier = IDENTIFIER.exec(text);
    if (identifier) {
      const word = identifier[0];
      out.push(span(word === "true" || word === "false" || word === "null" ? "b" : "", word));
      index += word.length;
      continue;
    }
    out.push("{}[],:".includes(char) ? span("o", char) : escapeHtml(char));
    index += 1;
  }
  return out.join("");
}

const CSS_VALUE =
  /\/\*[\s\S]*?(?:\*\/|$)|"(?:\\.|[^"\\\n])*"?|'(?:\\.|[^'\\\n])*'?|#[\da-fA-F]{3,8}\b|-?\d*\.?\d+(?:[a-zA-Z%]+)?|!important|[\p{L}_-][\p{L}\p{N}_-]*(?=\()|[$@]?[\p{L}_-][\p{L}\p{N}_-]*|[\s\S]/uy;

function cssValueTokens(text) {
  const out = [];
  CSS_VALUE.lastIndex = 0;
  let match;
  while (CSS_VALUE.lastIndex < text.length && (match = CSS_VALUE.exec(text))) {
    const token = match[0];
    if (token.startsWith("/*")) out.push(span("c", token));
    else if (token[0] === '"' || token[0] === "'") out.push(span("s", token));
    else if (token[0] === "#" && token.length > 1) out.push(span("n", token));
    else if (/^-?\d*\.?\d/.test(token)) out.push(span("n", token));
    else if (token === "!important") out.push(span("k", token));
    else if (token[0] === "$" || token[0] === "@" || token.startsWith("--"))
      out.push(span("v", token));
    else if (text[CSS_VALUE.lastIndex] === "(" && /[\p{L}_-]/u.test(token[0]))
      out.push(span("f", token));
    else if (/^[\p{L}_-]/u.test(token)) out.push(span("b", token));
    else out.push(";:,(){}".includes(token) ? span("o", token) : escapeHtml(token));
  }
  return out.join("");
}

function tokenizeCss(text) {
  // Statement by statement: what precedes "{" is a selector or at-rule, and inside a
  // block "name: value;" is a declaration. Nested SCSS blocks follow the same rule.
  const out = [];
  const size = text.length;
  let index = 0;
  let depth = 0;
  while (index < size) {
    const char = text[index];
    if (/\s/.test(char)) {
      let end = index + 1;
      while (end < size && /\s/.test(text[end])) end += 1;
      out.push(text.slice(index, end));
      index = end;
      continue;
    }
    if (text.startsWith("/*", index)) {
      const found = text.indexOf("*/", index + 2);
      const end = found < 0 ? size : found + 2;
      out.push(span("c", text.slice(index, end)));
      index = end;
      continue;
    }
    if (text.startsWith("//", index)) {
      const found = text.indexOf("\n", index);
      const end = found < 0 ? size : found;
      out.push(span("c", text.slice(index, end)));
      index = end;
      continue;
    }
    if (char === "{" || char === "}") {
      depth = Math.max(0, depth + (char === "{" ? 1 : -1));
      out.push(span("o", char));
      index += 1;
      continue;
    }
    if (char === ";") {
      out.push(span("o", char));
      index += 1;
      continue;
    }
    // Read one statement head up to "{", ";" or "}" (strings and comments are skipped over).
    let end = index;
    let colon = -1;
    while (end < size) {
      const current = text[end];
      if (current === '"' || current === "'") {
        end = endOfQuoted(text, end, current, false);
        continue;
      }
      if (current === "/" && text[end + 1] === "*") {
        const found = text.indexOf("*/", end + 2);
        end = found < 0 ? size : found + 2;
        continue;
      }
      if (current === "{" || current === ";" || current === "}") break;
      if (current === ":" && colon < 0) colon = end;
      end += 1;
    }
    const head = text.slice(index, end);
    const isBlock = text[end] === "{";
    if (head.startsWith("@")) {
      const name = /^@[\p{L}_-]+/u.exec(head);
      const nameLength = name ? name[0].length : 1;
      out.push(span("k", head.slice(0, nameLength)), cssValueTokens(head.slice(nameLength)));
    } else if (!isBlock && depth > 0 && colon >= 0) {
      const property = text.slice(index, colon);
      out.push(
        span(/^\s*(?:\$|--)/.test(property) ? "v" : "a", property),
        span("o", ":"),
        cssValueTokens(text.slice(colon + 1, end)),
      );
    } else if (isBlock || depth === 0) {
      out.push(span("t", head));
    } else {
      out.push(cssValueTokens(head));
    }
    index = end;
  }
  return out.join("");
}

const TAG_NAME = /[\p{L}_][\p{L}\p{N}_:.-]*/uy;
const ATTRIBUTE_NAME = /[^\s"'<>/=]+/y;

function tokenizeMarkup(text) {
  const out = [];
  const size = text.length;
  let index = 0;
  while (index < size) {
    const open = text.indexOf("<", index);
    if (open < 0) {
      out.push(markupText(text.slice(index)));
      break;
    }
    if (open > index) out.push(markupText(text.slice(index, open)));
    if (text.startsWith("<!--", open)) {
      const found = text.indexOf("-->", open + 4);
      const end = found < 0 ? size : found + 3;
      out.push(span("c", text.slice(open, end)));
      index = end;
      continue;
    }
    let cursor = open + 1;
    let closing = false;
    if (text[cursor] === "/") {
      closing = true;
      cursor += 1;
    }
    if (text[cursor] === "!" || text[cursor] === "?") cursor += 1;
    TAG_NAME.lastIndex = cursor;
    const name = TAG_NAME.exec(text);
    if (!name) {
      out.push(escapeHtml("<"));
      index = open + 1;
      continue;
    }
    out.push(span("o", text.slice(open, cursor)), span("t", name[0]));
    cursor += name[0].length;
    const tag = name[0].toLowerCase();
    let selfClosed = false;
    // Attributes up to the closing ">".
    while (cursor < size && text[cursor] !== ">") {
      const char = text[cursor];
      if (/\s/.test(char)) {
        let end = cursor + 1;
        while (end < size && /\s/.test(text[end])) end += 1;
        out.push(text.slice(cursor, end));
        cursor = end;
      } else if (char === '"' || char === "'") {
        const end = endOfQuoted(text, cursor, char, true);
        out.push(span("s", text.slice(cursor, end)));
        cursor = end;
      } else if (char === "=") {
        out.push(span("o", "="));
        cursor += 1;
      } else if (char === "/") {
        selfClosed = text[cursor + 1] === ">";
        out.push(span("o", "/"));
        cursor += 1;
      } else if (char === "<") {
        break; // a new tag started before this one was closed
      } else {
        ATTRIBUTE_NAME.lastIndex = cursor;
        const attribute = ATTRIBUTE_NAME.exec(text);
        const value = attribute ? attribute[0] : char;
        out.push(span(text[cursor - 1] === "=" ? "s" : "a", value));
        cursor += value.length;
      }
    }
    if (text[cursor] === ">") {
      out.push(span("o", ">"));
      cursor += 1;
    }
    index = cursor;
    if (!closing && !selfClosed && (tag === "script" || tag === "style")) {
      const lower = text.toLowerCase();
      const close = lower.indexOf(`</${tag}`, index);
      const end = close < 0 ? size : close;
      const inner = text.slice(index, end);
      out.push(tag === "script" ? tokenizeGeneric(inner, SPECS.javascript) : tokenizeCss(inner));
      index = end;
    }
  }
  return out.join("");
}

function markupText(text) {
  return text
    .split(/(&[#\w]+;)/)
    .map((part, index) => (index % 2 ? span("b", part) : escapeHtml(part)))
    .join("");
}

const MARKDOWN_INLINE =
  /(`[^`\n]+`)|(\*\*[^*\n]+\*\*|__[^_\n]+__)|(\*[^*\s][^*\n]*\*|_[^_\s][^_\n]*_)|(\[[^\]\n]+\])(\([^)\n]+\))/g;

function markdownInline(line) {
  let out = "";
  let last = 0;
  MARKDOWN_INLINE.lastIndex = 0;
  let match;
  while ((match = MARKDOWN_INLINE.exec(line))) {
    out += escapeHtml(line.slice(last, match.index));
    if (match[1]) out += span("s", match[1]);
    else if (match[2]) out += span("e", match[2]);
    else if (match[3]) out += span("i", match[3]);
    else out += span("t", match[4]) + span("a", match[5]);
    last = match.index + match[0].length;
  }
  return out + escapeHtml(line.slice(last));
}

function tokenizeMarkdown(text) {
  let fenced = false;
  return text
    .split("\n")
    .map((line) => {
      if (/^\s*(```|~~~)/.test(line)) {
        fenced = !fenced;
        return span("o", line);
      }
      if (fenced) return span("s", line);
      if (/^#{1,6}\s/.test(line)) return span("h", line);
      if (/^\s*>/.test(line)) return span("c", line);
      if (/^\s*(?:[-*_]\s*){3,}$/.test(line)) return span("o", line);
      const list = /^(\s*)([-*+]|\d+[.)])(\s+)/.exec(line);
      if (list) {
        return (
          escapeHtml(list[1]) +
          span("k", list[2]) +
          list[3] +
          markdownInline(line.slice(list[0].length))
        );
      }
      return markdownInline(line);
    })
    .join("\n");
}

const CONFIG_VALUE =
  /("(?:\\.|[^"\\])*"|'[^']*')|(#.*$)|(\b(?:true|false|null|yes|no|on|off)\b)|(-?\b\d[\d_.:TZ+-]*\b)/gi;

function configValue(text) {
  let out = "";
  let last = 0;
  CONFIG_VALUE.lastIndex = 0;
  let match;
  while ((match = CONFIG_VALUE.exec(text))) {
    out += escapeHtml(text.slice(last, match.index));
    out += span(match[1] ? "s" : match[2] ? "c" : match[3] ? "b" : "n", match[0]);
    last = match.index + match[0].length;
  }
  return out + escapeHtml(text.slice(last));
}

function tokenizeConfig(text) {
  return text
    .split("\n")
    .map((line) => {
      if (/^\s*#/.test(line)) return span("c", line);
      const section = /^(\s*)(\[\[?[^\]\n]*\]\]?)(.*)$/.exec(line);
      if (section) return escapeHtml(section[1]) + span("t", section[2]) + configValue(section[3]);
      const pair = /^(\s*(?:-\s+)?)([\p{L}\p{N}_."'-]+)(\s*[:=])(\s|$)/u.exec(line);
      if (pair) {
        return (
          escapeHtml(pair[1]) +
          span("a", pair[2]) +
          span("o", pair[3]) +
          pair[4] +
          configValue(line.slice(pair[0].length))
        );
      }
      return configValue(line);
    })
    .join("\n");
}

/** Above this size the editor shows plain text so typing stays instant. */
export const HIGHLIGHT_LIMIT = 200_000;

/** Return HTML for `text` coloured as `languageId` (see languageForPath). */
export function highlightCode(text, languageId) {
  const source = String(text ?? "");
  if (source.length > HIGHLIGHT_LIMIT) return escapeHtml(source);
  try {
    if (languageId === "json") return tokenizeJson(source);
    if (languageId === "css") return tokenizeCss(source);
    if (languageId === "markup") return tokenizeMarkup(source);
    if (languageId === "markdown") return tokenizeMarkdown(source);
    if (languageId === "config") return tokenizeConfig(source);
    const spec = SPECS[languageId];
    return spec ? tokenizeGeneric(source, spec) : escapeHtml(source);
  } catch {
    return escapeHtml(source); // colouring must never get in the way of editing
  }
}
