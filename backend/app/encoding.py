class Base62Encoder:
    # Alphabet containing a-z, A-Z, 0-9 in order
    ALPHABET = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    BASE = 62

    @classmethod
    def encode(cls, num: int) -> str:
        """Encodes a 64-bit integer into a Base62 string."""
        if num < 0:
            raise ValueError("Number must be a non-negative integer.")
        if num == 0:
            return cls.ALPHABET[0]
        
        digits = []
        while num > 0:
            num, rem = divmod(num, cls.BASE)
            digits.append(cls.ALPHABET[rem])
            
        return "".join(reversed(digits))

    @classmethod
    def decode(cls, token: str) -> int:
        """Decodes a Base62 string back into a 64-bit integer."""
        num = 0
        for char in token:
            try:
                idx = cls.ALPHABET.index(char)
            except ValueError:
                raise ValueError(f"Invalid character '{char}' in Base62 token.")
            num = num * cls.BASE + idx
        return num
