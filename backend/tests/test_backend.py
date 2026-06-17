import unittest
from datetime import datetime, timedelta, timezone
from app.encoding import Base62Encoder

try:
    from app.schemas import URLShortenRequest
    HAS_SCHEMAS = True
except ImportError:
    HAS_SCHEMAS = False

class TestURLShortenerBackend(unittest.TestCase):
    
    # --- 1. Base62 Encoder & Decoder Tests ---
    def test_base62_encoding_decoding(self):
        test_cases = [
            0,
            1,
            61,
            62,
            1000,
            999999,
            56800235583,  # Max limit for 6-char token (62^6 - 1)
            123456789012345
        ]
        
        for number in test_cases:
            with self.subTest(num=number):
                encoded = Base62Encoder.encode(number)
                decoded = Base62Encoder.decode(encoded)
                self.assertEqual(number, decoded, f"Failed for {number}")
                
    def test_base62_invalid_characters(self):
        invalid_tokens = ["abc-123", "token_1", "  ", "ab!", "L7x$"]
        for token in invalid_tokens:
            with self.subTest(token=token):
                with self.assertRaises(ValueError):
                    Base62Encoder.decode(token)
                    
    def test_base62_negative_numbers(self):
        with self.assertRaises(ValueError):
            Base62Encoder.encode(-1)


    # --- 2. Request Validation Schema Tests ---
    @unittest.skipIf(not HAS_SCHEMAS, "Pydantic schemas not loaded")
    def test_url_validation_success(self):
        valid_urls = [
            "http://example.com",
            "https://example.com/some/path?query=1",
            "https://sub.domain.co.uk:8080/path"
        ]
        for url in valid_urls:
            with self.subTest(url=url):
                req = URLShortenRequest(long_url=url)
                self.assertEqual(req.validate_url(), url)
                
    @unittest.skipIf(not HAS_SCHEMAS, "Pydantic schemas not loaded")
    def test_url_validation_failure(self):
        invalid_urls = [
            "ftp://example.com",
            "just_a_string",
            "www.example.com",
            "https:example.com"
        ]
        for url in invalid_urls:
            with self.subTest(url=url):
                req = URLShortenRequest(long_url=url)
                with self.assertRaises(ValueError):
                    req.validate_url()
                    
    @unittest.skipIf(not HAS_SCHEMAS, "Pydantic schemas not loaded")
    def test_url_expiration_future(self):
        future_time = datetime.now(timezone.utc) + timedelta(days=1)
        req = URLShortenRequest(long_url="https://example.com", expires_at=future_time)
        self.assertEqual(req.expires_at, future_time)

if __name__ == '__main__':
    unittest.main()
