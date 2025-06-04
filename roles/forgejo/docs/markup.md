## markup
```yaml
forgejo_markup:
  mermaid_max_source_characters: ""               # 5000
  filepreview_max_lines: ""                       # 50
  sanitizer: []
  #  - id: 1
  #    element: span
  #    allow_attr: class
  #    regexp: ^(info|warning|error)$
  #  - id: 2
  #    element: div
  #    allow_attr: class
  #    regexp: ^(info|warning|error)$
  asciidoc:
    enabled: ""                                   # false
    file_extensions: []                           # [.adoc, .asciidoc]
    render_command: ""                            # "asciidoc --out-file=- -"
    is_input_file: ""                             # false
    render_content_mode: ""                       # sanitized
```
