
class bcolors:
    # Textfarben (normal)
    BLACK = '\033[30m'
    RED = '\033[31m'
    GREEN = '\033[32m'
    YELLOW = '\033[33m'
    BLUE = '\033[34m'
    MAGENTA = '\033[35m'
    CYAN = '\033[36m'
    WHITE = '\033[37m'
    # Textfarben (bright)
    BRIGHT_BLACK = '\033[90m'
    BRIGHT_RED = '\033[91m'
    BRIGHT_GREEN = '\033[92m'
    BRIGHT_YELLOW = '\033[93m'
    BRIGHT_BLUE = '\033[94m'
    BRIGHT_MAGENTA = '\033[95m'
    BRIGHT_CYAN = '\033[96m'
    BRIGHT_WHITE = '\033[97m'
    # dark
    DARK_BLUE = '\033[38;5;17m'
    DARK_GREEN = '\033[38;5;22m'
    DARK_RED = '\033[38;5;52m'
    DARK_TEAL = '\033[38;5;58m'
    DARK_MAGENTA = '\033[38;5;94m'
    DARK_GRAY = '\033[38;5;233m'
    # Hintergrundfarben (normal)
    BG_BLACK = '\033[40m'
    BG_RED = '\033[41m'
    BG_GREEN = '\033[42m'
    BG_YELLOW = '\033[43m'
    BG_BLUE = '\033[44m'
    BG_MAGENTA = '\033[45m'
    BG_CYAN = '\033[46m'
    BG_WHITE = '\033[47m'
    # Hintergrundfarben (bright)
    BG_BRIGHT_BLACK = '\033[100m'
    BG_BRIGHT_RED = '\033[101m'
    BG_BRIGHT_GREEN = '\033[102m'
    BG_BRIGHT_YELLOW = '\033[103m'
    BG_BRIGHT_BLUE = '\033[104m'
    BG_BRIGHT_MAGENTA = '\033[105m'
    BG_BRIGHT_CYAN = '\033[106m'
    BG_BRIGHT_WHITE = '\033[107m'
    # Styles
    RESET = '\033[0m'
    BOLD = '\033[1m'
    FAINT = '\033[2m'
    ITALIC = '\033[3m'
    UNDERLINE = '\033[4m'
    REVERSE = '\033[7m'
    STRIKETHROUGH = '\033[9m'
    #
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    DEBUG = '\033[1m\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

    @staticmethod
    def color(text: str, *codes: str) -> str:
        """
        Kombiniert beliebig viele ANSI-Codes und hängt am Ende RESET an.
        """
        prefix = "".join(codes)
        return f"{prefix}{text}{bcolors.RESET}"

    # Beispiel-Helfer
    @classmethod
    def error(cls, text: str) -> str:
        return cls.color(text, cls.BRIGHT_RED, cls.BOLD)

    @classmethod
    def success(cls, text: str) -> str:
        return cls.color(text, cls.BRIGHT_GREEN)

    @classmethod
    def warning(cls, text: str) -> str:
        return cls.color(text, cls.BRIGHT_YELLOW, cls.UNDERLINE)

    @classmethod
    def info(cls, text: str) -> str:
        return cls.color(text, cls.CYAN)

    @classmethod
    def highlight(cls, text: str) -> str:
        return cls.color(text, cls.BG_BRIGHT_YELLOW, cls.BLACK)

    @classmethod
    def header(cls, text: str) -> str:
        return cls.color(text, cls.HEADER)

    @classmethod
    def fail(cls, text: str) -> str:
        return cls.color(text, cls.FAIL)

    @classmethod
    def bold(cls, text: str) -> str:
        return cls.color(text, cls.BOLD)

    @classmethod
    def green(cls, text: str) -> str:
        return cls.color(text, cls.GREEN)

    @classmethod
    def dark_green(cls, text: str) -> str:
        return cls.color(text, cls.DARK_GREEN)

    @classmethod
    def dark_red(cls, text: str) -> str:
        return cls.color(text, cls.DARK_RED)

    # usw. für andere Level…
    @staticmethod
    def fg256(code: int) -> str:
        return f"\033[38;5;{code}m"

    @staticmethod
    def bg256(code: int) -> str:
        return f"\033[48;5;{code}m"

    @staticmethod
    def color256(text: str, fg: int = None, bg: int = None) -> str:
        seq = ""
        if fg is not None:
            seq += bcolors.fg256(fg)
        if bg is not None:
            seq += bcolors.bg256(bg)
        return f"{seq}{text}{bcolors.RESET}"
