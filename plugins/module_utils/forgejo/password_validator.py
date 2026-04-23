import re
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class PasswordPolicy:
    """
    Spiegelt Forgejos app.ini [security]-Sektion wider.
    Defaults entsprechen dem Forgejo-Standard.
    """

    min_length: int = 6
    # Komplexitäts-Flags: "lower", "upper", "digit", "spec"
    complexity: list[str] = field(
        default_factory=lambda: ["lower", "upper", "digit", "spec"]
    )


@dataclass
class PasswordValidationResult:
    valid: bool
    errors: list[str] = field(default_factory=list)

    def __bool__(self):
        return self.valid


class ForgejoPasswordValidator:
    """
    Validiert Passwörter gegen Forgejo's IsComplexEnough()-Logik.

    Quelle: services/password/password.go (Forgejo/Gitea)
    Komplexitäts-Flags: lower, upper, digit, spec
    """

    # Exakt die Zeichenklassen aus Forgejos Quellcode
    _LOWER = re.compile(r"[a-z]")
    _UPPER = re.compile(r"[A-Z]")
    _DIGIT = re.compile(r"[0-9]")
    # Forgejo definiert "spec" als alle druckbaren Non-Alphanumeric ASCII-Zeichen
    _SPECIAL = re.compile(r"[^\w]|_")

    _CHECKERS = {
        "lower": (_LOWER, "The password must contain at least one lower-case letter."),
        "upper": (_UPPER, "The password must contain at least one uppercase letter."),
        "digit": (
            _DIGIT,
            "The password needs to contain at least one numeric character.",
        ),
        "spec": (
            _SPECIAL,
            "The password needs to contain at least one special character.",
        ),
    }

    def __init__(self, policy: Optional[PasswordPolicy] = None):
        self.policy = policy or PasswordPolicy()

    def validate(self, password: str) -> PasswordValidationResult:
        errors = []

        if len(password) < self.policy.min_length:
            errors.append(
                f"Password needs to be at least {self.policy.min_length} characters long."
            )

        for flag in self.policy.complexity:
            pattern, description = self._CHECKERS.get(flag, (None, None))
            if pattern and not pattern.search(password):
                errors.append(description)

        return PasswordValidationResult(valid=not errors, errors=errors)

    def validate_or_raise(self, password: str) -> None:
        result = self.validate(password)
        if not result:
            raise ValueError(f"Invalid password: {'; '.join(result.errors)}")
