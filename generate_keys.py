"""
AURA TACTICAL VISION // KEY GENERATOR (ADMIN TOOL)
Generate cryptographically signed license keys to sell or give to users.
"""

import sys
from license_manager import generate_cryptographic_key, verify_cryptographic_signature

def main():
    print("=" * 60)
    print("   AURA TACTICAL VISION // COMMERCIAL KEY GENERATOR")
    print("=" * 60)
    print("Master Built-in Keys:")
    print("  -> AURA-VIP-2026-LIFETIME   [LIFETIME]")
    print("  -> AURA-5DAY-VIP-ACCESS    [5-DAY TRIAL]")
    print("  -> AURA-PRO-FOUNDER-PASS   [FOUNDER]")
    print("=" * 60)
    
    count = 5
    print(f"\nGenerated 5 Valid 5-Day VIP Trial Keys:")
    for i in range(1, count + 1):
        key = generate_cryptographic_key(tier="5DAY")
        is_valid = verify_cryptographic_signature(key)
        status = "[VALID]" if is_valid else "[INVALID]"
        print(f"  {i}. {key}   {status}")

    print(f"\nGenerated 5 Valid Cryptographic Lifetime License Keys:")
    for i in range(1, count + 1):
        key = generate_cryptographic_key(tier="LIFETIME")
        is_valid = verify_cryptographic_signature(key)
        status = "[VALID]" if is_valid else "[INVALID]"
        print(f"  {i}. {key}   {status}")

    print("\nGenerated 5 Valid 30-Day Subscription Keys:")
    for i in range(1, count + 1):
        key = generate_cryptographic_key(tier="SUB")
        is_valid = verify_cryptographic_signature(key)
        status = "[VALID]" if is_valid else "[INVALID]"
        print(f"  {i}. {key}   {status}")

    print("\n" + "=" * 60)
    print("These keys are signed and accepted by the loader instantly!")
    print("=" * 60)

if __name__ == "__main__":
    main()
