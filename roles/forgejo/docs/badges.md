## badges
```yaml
forgejo_badges:
  enabled: true                                   # Enable repository badges (via shields.io or a similar generator)
  generator_url_template: !unsafe "https://img.shields.io/badge/{{.label}}-{{.text}}-{{.color}}" # Template for the badge generator.
```
