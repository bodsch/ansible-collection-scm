"""
molecule.py

Utility helpers for Molecule/Testinfra pytest test suites.

This module provides:

- Inventory/host helpers for Testinfra + Molecule
- A variable loader that merges role defaults/vars, OS-specific vars, and scenario vars
- A Jinja2-based renderer that resolves Ansible-style variables in Python tests
  (multi-pass rendering, env lookup support, safe handling of Ansible `!unsafe` raw strings,
  and optional masking of embedded Go templates)

Rationale (high-level):
Modern Ansible versions tightened templating behavior for untrusted inputs. In pure-Python
tests (outside Ansible's full variable manager), rendering via Ansible's internal templar
is brittle. This module renders with Jinja2 directly while preserving key Ansible behaviors
needed in Molecule tests.

Typical usage:
- import and use the `get_vars(host)` pytest fixture in your molecule scenario tests
- call `local_facts(host, "myfact")` to read ansible_local facts

Note:
- Embedded Go templates (e.g., Alertmanager `{{ template "..." . }}`) collide with Jinja2.
  This module can mask them to a placeholder to avoid TemplateSyntaxError.
"""

from __future__ import annotations

import json
import os
import re
from collections.abc import Mapping as AbcMapping
from collections.abc import Sequence as AbcSequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

import pytest
import testinfra.utils.ansible_runner
from ansible.parsing.dataloader import DataLoader
from jinja2 import ChainableUndefined
from jinja2.exceptions import TemplateSyntaxError
from jinja2.nativetypes import NativeEnvironment


class RawString(str):
    """
    Marker type for strings that must not be processed by the Jinja renderer.

    In Ansible YAML, `!unsafe` (or `!raw`) is used to mark a string as "do not template".
    When parsed by Ansible's YAML loader, such values often become "unsafe proxy" strings.
    This module converts them into `RawString` which preserves the "do not template"
    semantics via the `__UNSAFE__` attribute.
    """

    __UNSAFE__ = True


def pp_json(json_thing: Any, sort: bool = True, indents: int = 2) -> None:
    """
    Pretty-print JSON for debugging.

    Args:
        json_thing: Either a JSON string or a Python object that can be serialized.
        sort: Sort keys in the output.
        indents: Indentation level.
    """
    if isinstance(json_thing, str):
        print(json.dumps(json.loads(json_thing), sort_keys=sort, indent=indents))
    else:
        print(json.dumps(json_thing, sort_keys=sort, indent=indents))


def local_facts(host: Any, fact: Optional[str] = None) -> Dict[str, Any]:
    """
    Read `ansible_local` facts from the target host.

    Args:
        host: Testinfra host fixture (ansible backend).
        fact: Optional key within `ansible_local` to return.

    Returns:
        If `fact` is provided and exists, returns the sub-dict for that fact.
        Otherwise returns an empty dict.
    """
    setup = host.ansible("setup")
    ansible_facts = setup.get("ansible_facts", {}) if isinstance(setup, dict) else {}
    ansible_local = (
        ansible_facts.get("ansible_local", {})
        if isinstance(ansible_facts, dict)
        else {}
    )

    if isinstance(ansible_local, dict) and fact:
        value = ansible_local.get(fact, {})
        return value if isinstance(value, dict) else {}
    return {}


def infra_hosts(host_name: Optional[str] = None) -> List[str]:
    """
    Resolve the list of testinfra hosts from the Molecule inventory.

    Args:
        host_name: Optional group/host pattern (defaults to "all").

    Returns:
        A list of hosts that match the pattern.
    """
    pattern = host_name or "all"
    return testinfra.utils.ansible_runner.AnsibleRunner(
        os.environ["MOLECULE_INVENTORY_FILE"]
    ).get_hosts(pattern)


def base_directory() -> tuple[Path, Path]:
    """
    Determine role root and scenario root for a Molecule test run.

    Returns:
        role_dir: Role root directory (contains defaults/, vars/, tasks/, ...)
        scenario_dir: Molecule scenario directory (contains group_vars/, etc.)
    """
    cwd = Path.cwd()

    # If pytest runs inside molecule/<scenario>/tests, group_vars exists one level up
    if (cwd / "group_vars").is_dir():
        return (cwd / "../..").resolve(), cwd.resolve()

    scenario = os.environ.get("MOLECULE_SCENARIO_NAME", "default")
    return cwd.resolve(), (cwd / "molecule" / scenario).resolve()


def _normalize_os(distribution: str) -> Optional[str]:
    """
    Normalize distro identifiers to role var file naming conventions.

    Args:
        distribution: host.system_info.distribution (testinfra)

    Returns:
        A normalized string used for vars/<os>.yml|yaml or None if unsupported.
    """
    d = (distribution or "").strip().lower()
    if d in ("debian", "ubuntu"):
        return "debian"
    if d in ("arch", "artix"):
        return f"{d}linux"
    return None


def _load_vars_file(loader: DataLoader, file_base: Path) -> Dict[str, Any]:
    """
    Load a YAML vars file by basename (without extension).

    The loader supports Ansible vault/encrypted files if configured.

    Args:
        loader: Ansible DataLoader.
        file_base: Path without extension, e.g. role_dir/'defaults'/'main'.

    Returns:
        A dict with loaded variables, or {} if the file does not exist.
    """
    for ext in ("yml", "yaml"):
        p = file_base.with_suffix(f".{ext}")
        if not p.is_file():
            continue

        data = loader.load_from_file(str(p))
        if data is None:
            return {}
        if not isinstance(data, dict):
            raise TypeError(f"{p} must be a mapping/dict, got {type(data)}")
        return data

    return {}


def _load_ansible_filters_PLD() -> Dict[str, Any]:
    """
    Load Ansible built-in Jinja2 filters without instantiating the full Templar.

    Iterates over ansible.plugins.filter submodules, calls FilterModule().filters()
    on each, and returns a flat dict of {filter_name: callable}.

    Only filter modules that expose a `FilterModule` class with a `.filters()` method
    are loaded. Import failures are silently skipped (e.g., filters with C extensions
    not available in the test environment).

    Returns:
        Dict mapping filter name to callable, ready for NativeEnvironment.filters.update().
    """
    import importlib
    import pkgutil

    import ansible.plugins.filter as _ansible_filter_pkg

    filters: Dict[str, Any] = {}

    for finder, module_name, _ in pkgutil.iter_modules(_ansible_filter_pkg.__path__):
        fqn = f"ansible.plugins.filter.{module_name}"
        try:
            mod = importlib.import_module(fqn)
            filter_class = getattr(mod, "FilterModule", None)
            if filter_class is None:
                continue
            loaded = filter_class().filters()
            if isinstance(loaded, dict):
                filters.update(loaded)
        except Exception as e:  # noqa: BLE001
            # Skip filters with missing deps (e.g. ipaddr needs netaddr)
            print(f"ERROR: {e}")
            pass

    return filters


def _load_ansible_filters() -> Dict[str, Any]:
    """
    Load Ansible built-in Jinja2 filters and register them under both their short name
    and their FQCN alias (ansible.builtin.<name>), matching Ansible's templar behavior.
    """
    import importlib
    import pkgutil

    import ansible.plugins.filter as _ansible_filter_pkg

    filters: Dict[str, Any] = {}

    for _, module_name, _ in pkgutil.iter_modules(_ansible_filter_pkg.__path__):
        fqn = f"ansible.plugins.filter.{module_name}"
        try:
            mod = importlib.import_module(fqn)
            filter_class = getattr(mod, "FilterModule", None)
            if filter_class is None:
                continue
            loaded = filter_class().filters()
            if not isinstance(loaded, dict):
                continue
            filters.update(loaded)
            # Register FQCN aliases: ansible.builtin.<filter_name>
            for name, func in loaded.items():
                filters[f"ansible.builtin.{name}"] = func
        except Exception:  # noqa: BLE001
            pass

    return filters


@dataclass(frozen=True, slots=True)
class VarsRenderConfig:
    """
    Configuration for variable rendering.

    Attributes:
        passes: Maximum number of render passes (supports vars referencing vars).
        skip_keys: Keys excluded from recursive rendering (facts are data, not templates).
        allow_unresolved_env_var: Env var controlling whether unresolved templates are allowed.
        go_template_placeholder: Placeholder string used to replace Go-template occurrences.
        go_template_replace_entire_value: If True, a string containing a Go-template becomes the
            placeholder. If False, only the matched segments are replaced.
    """

    passes: int = 8
    skip_keys: frozenset[str] = frozenset({"ansible_facts"})
    allow_unresolved_env_var: str = "ANSIBLE_TEST_ALLOW_UNRESOLVED_TEMPLATES"
    go_template_placeholder: str = "GO-TEMPLATE"
    go_template_replace_entire_value: bool = True


class VarsRenderer:
    """
    Render a merged variable dictionary similar to Ansible role variables.

    Key features:
    - Multi-pass rendering to resolve chained variables
    - Minimal `lookup('env', ...)` and `query('env', ...)` support (allowlist: env only)
    - Honors Ansible `!unsafe` semantics via `RawString` (do not template)
    - Optional masking of embedded Go templates to avoid Jinja2 parsing errors
    """

    # Detect any Jinja-ish markers (cheap pre-check)
    _jinja_marker = re.compile(r"({{.*?}}|{%-?.*?-%}|{#.*?#})", re.S)

    # Detect common Go-template constructs used by Alertmanager / Prometheus tooling
    _go_template = re.compile(
        r"""
        {{\s*
            (?:
                \.\s+                    # {{ . }}        – bare context dot (e.g. "pass context")
              | \.[A-Za-z_]\w*           # {{.field}}     – field/method access (e.g. {{.label}})
              | template\s+"[^"]+"\s+\.  # {{ template "name" . }}
              | define\s+"[^"]+"         # {{ define "name" }}
              | block\s+"[^"]+"          # {{ block "name" }}
              | end                      # {{ end }}
            )
        \s*}}
        """,
        re.VERBOSE,
    )

    def __init__(self, config: VarsRenderConfig = VarsRenderConfig()) -> None:
        self._config = config

    @property
    def config(self) -> VarsRenderConfig:
        """Renderer configuration."""
        return self._config

    def make_env(self) -> NativeEnvironment:
        """
        Build the Jinja2 environment with Ansible built-in filters registered.

        Loads filter plugins directly from ansible.plugins.filter (no Templar/VariableManager).
        Falls back gracefully if a filter module cannot be imported.
        """
        env = NativeEnvironment(undefined=ChainableUndefined, autoescape=False)

        # --- lookup / query globals (unchanged) ---
        def _lookup(plugin: str, term: Any, *rest: Any, **kwargs: Any) -> Any:
            if plugin != "env":
                raise ValueError(
                    f"lookup('{plugin}', ...) not supported in tests (allowlist: env)"
                )
            if isinstance(term, (list, tuple)):
                vals = [os.environ.get(str(t), "") for t in term]
                return vals[0] if kwargs.get("wantlist") is False else vals
            return os.environ.get(str(term), "")

        def _query(plugin: str, term: Any, *rest: Any, **kwargs: Any) -> List[Any]:
            kwargs["wantlist"] = True
            res = _lookup(plugin, term, *rest, **kwargs)
            return res if isinstance(res, list) else [res]

        env.globals["lookup"] = _lookup
        env.globals["query"] = _query

        # --- Register Ansible filter plugins ---
        env.filters.update(_load_ansible_filters())

        return env

    def strip_unsafe(self, obj: Any) -> Any:
        """
        Convert Ansible unsafe proxy strings into plain strings while preserving raw semantics.

        If the object is a string and has `__UNSAFE__ == True`, it is wrapped in `RawString`.
        """
        if obj is None or isinstance(obj, (bool, int, float)):
            return obj

        if isinstance(obj, str):
            if getattr(obj, "__UNSAFE__", False):
                return RawString(str(obj))
            return obj

        if isinstance(obj, AbcMapping):
            return {str(k): self.strip_unsafe(v) for k, v in obj.items()}

        if isinstance(obj, AbcSequence) and not isinstance(
            obj, (str, bytes, bytearray)
        ):
            return [self.strip_unsafe(v) for v in obj]

        return obj

    def mask_go_templates(self, obj: Any) -> Any:
        """
        Replace Go-template fragments with a placeholder to avoid Jinja2 parsing errors.

        This is intended for configs where Go templates are embedded inside Ansible variables.
        """
        if obj is None or isinstance(obj, (bool, int, float)):
            return obj

        if isinstance(obj, str):
            if not self._go_template.search(obj):
                return obj

            if self.config.go_template_replace_entire_value:
                return self.config.go_template_placeholder

            return self._go_template.sub(self.config.go_template_placeholder, obj)

        if isinstance(obj, AbcMapping):
            return {str(k): self.mask_go_templates(v) for k, v in obj.items()}

        if isinstance(obj, AbcSequence) and not isinstance(
            obj, (str, bytes, bytearray)
        ):
            return [self.mask_go_templates(v) for v in obj]

        return obj

    def find_unrendered_templates(self, obj: Any, prefix: str = "") -> List[str]:
        """
        Find unresolved template markers in a nested structure.

        Args:
            obj: Arbitrary nested structure.
            prefix: Path prefix for diagnostics.

        Returns:
            List of dotted paths to values that still contain template markers.
        """
        found: List[str] = []

        if isinstance(obj, str):
            if self._jinja_marker.search(obj):
                found.append(prefix or "<root>")
            return found

        if isinstance(obj, AbcMapping):
            for k, v in obj.items():
                key = str(k)
                found.extend(
                    self.find_unrendered_templates(
                        v, f"{prefix}.{key}" if prefix else key
                    )
                )
            return found

        if isinstance(obj, AbcSequence) and not isinstance(
            obj, (str, bytes, bytearray)
        ):
            for i, v in enumerate(obj):
                found.extend(self.find_unrendered_templates(v, f"{prefix}[{i}]"))
            return found

        return found

    def render_obj(self, env: NativeEnvironment, obj: Any, ctx: Dict[str, Any]) -> Any:
        """
        Render a nested object using the given context.

        Rules:
        - Raw/unsafe strings are returned as-is
        - Strings without template markers are returned as-is
        - Strings containing Go templates are masked before rendering to avoid syntax errors
        - Other strings are rendered via Jinja2
        """
        if isinstance(obj, str):
            # honor Ansible unsafe/raw semantics: never template these strings
            if getattr(obj, "__UNSAFE__", False):
                return str(obj)

            if not self._jinja_marker.search(obj):
                return obj

            # Mask Go templates proactively (they look like {{ ... }} but are not Jinja)
            if self._go_template.search(obj):
                if self.config.go_template_replace_entire_value:
                    return self.config.go_template_placeholder
                obj = self._go_template.sub(self.config.go_template_placeholder, obj)

            try:
                tmpl = env.from_string(obj)
                return tmpl.render(**ctx)
            except TemplateSyntaxError:
                # Fallback: if parsing fails and the string contains Go template tokens,
                # ensure we never crash the test run.
                if self._go_template.search(obj):
                    return self.config.go_template_placeholder
                raise

        if isinstance(obj, AbcMapping):
            out: Dict[str, Any] = {}
            for k, v in obj.items():
                ks = str(k)
                if ks in self.config.skip_keys:
                    out[ks] = v
                else:
                    out[ks] = self.render_obj(env, v, ctx)
            return out

        if isinstance(obj, list):
            return [self.render_obj(env, v, ctx) for v in obj]

        if isinstance(obj, tuple):
            return tuple(self.render_obj(env, v, ctx) for v in obj)

        return obj

    def render_all(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Render a variable dict in multiple passes until stable or until max passes.

        Args:
            data: Merged variable dictionary.

        Returns:
            Rendered dictionary.

        Raises:
            AssertionError: If unresolved templates remain and the allow env var is not set.
            TypeError: If rendering results in a non-dict top-level structure.
        """
        env = self.make_env()

        current: Dict[str, Any] = data
        last_leftovers: Optional[List[str]] = None

        for _ in range(max(1, self.config.passes)):
            rendered = self.render_obj(env, current, current)
            if not isinstance(rendered, dict):
                raise TypeError(
                    f"Rendered vars are not a dict anymore: {type(rendered)}"
                )

            leftovers = self.find_unrendered_templates(rendered)
            if not leftovers:
                return rendered

            if leftovers == last_leftovers:
                current = rendered
                break

            last_leftovers = leftovers
            current = rendered

        if os.environ.get(self.config.allow_unresolved_env_var, "0") != "1":
            leftovers = self.find_unrendered_templates(current)
            if leftovers:
                raise AssertionError(
                    "Unresolved templates after rendering:\n- " + "\n- ".join(leftovers)
                )

        return current


DEFAULT_RENDERER = VarsRenderer()


def render_all_vars(data: Dict[str, Any], passes: int = 8) -> Dict[str, Any]:
    """
    Backwards-compatible wrapper for rendering vars.

    Args:
        data: merged variable dict
        passes: override max passes for this call

    Returns:
        rendered dict
    """
    renderer = VarsRenderer(config=VarsRenderConfig(passes=passes))
    return renderer.render_all(data)


@pytest.fixture()
def get_vars(host: Any) -> Dict[str, Any]:
    """
    Pytest fixture that returns a fully merged and rendered Ansible variable dict.

    Merge order:
      1) defaults/main.(yml|yaml)
      2) vars/main.(yml|yaml)
      3) vars/<os>. (yml|yaml) for supported OS families
      4) molecule/<scenario>/group_vars/all/vars.(yml|yaml)

    Additionally inject:
      - ansible_facts from `setup`
      - convenience keys: ansible_system, ansible_architecture

    Rendering:
      - converts Ansible unsafe proxy strings to RawString (never templated)
      - masks embedded Go templates to avoid Jinja2 TemplateSyntaxError
      - runs multi-pass Jinja2 rendering until stable
    """
    role_dir, scenario_dir = base_directory()

    loader = DataLoader()
    loader.set_basedir(str(role_dir))

    distribution = getattr(host.system_info, "distribution", "") or ""
    os_id = _normalize_os(distribution)

    merged: Dict[str, Any] = {}
    merged.update(_load_vars_file(loader, role_dir / "defaults" / "main"))
    merged.update(_load_vars_file(loader, role_dir / "vars" / "main"))

    if os_id:
        merged.update(_load_vars_file(loader, role_dir / "vars" / os_id))

    merged.update(_load_vars_file(loader, scenario_dir / "group_vars" / "all" / "vars"))

    setup = host.ansible("setup")
    facts = setup.get("ansible_facts", {}) if isinstance(setup, dict) else {}
    if isinstance(facts, dict):
        merged["ansible_facts"] = facts
        merged.setdefault(
            "ansible_system", facts.get("system") or facts.get("ansible_system")
        )
        merged.setdefault(
            "ansible_architecture",
            facts.get("architecture") or facts.get("ansible_architecture"),
        )

    # Preprocess special cases before rendering
    merged = DEFAULT_RENDERER.strip_unsafe(merged)
    merged = DEFAULT_RENDERER.mask_go_templates(merged)

    return DEFAULT_RENDERER.render_all(merged)
