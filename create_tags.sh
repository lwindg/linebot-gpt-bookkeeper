#!/bin/bash

echo "========================================="
echo "Creating Git Tags for All Releases"
echo "========================================="
echo ""

# v1.2.0
echo "📌 Creating tag v1.2.0..."
git tag -a v1.2.0 35b19ff -m "Release v1.2.0: Vision API Foundation

Major Features:
- GPT-4 Vision API integration for receipt recognition
- Image download and processing
- Receipt information extraction

Release Date: 2025-11-15"

# v1.3.0
echo "📌 Creating tag v1.3.0..."
git tag -a v1.3.0 8bccc22 -m "Release v1.3.0: Enhanced Classification & Error Handling

Major Features:
- Image compression to reduce Vision API token usage
- Enhanced classification rules
- Improved error handling

Release Date: 2025-11-15"

# v1.5.0
echo "📌 Creating tag v1.5.0..."
git tag -a v1.5.0 f6ee7ce -m "Release v1.5.0: Multi-Item Expense & Receipt Recognition

Major Features:
- Multi-item expense processing from single message
- Complete receipt image recognition
- Update last entry functionality with Vercel KV
- Unified prompt architecture

Release Date: 2025-11-15"

# v1.7.0
echo "📌 Creating tag v1.7.0..."
git tag -a v1.7.0 90c227b -m "Release v1.7.0: Advance Payment & Need-to-Pay Tracking

Major Features:
- Advance payment tracking (money lent to others)
- Need-to-pay tracking (money owed to others)
- Non-collectible advance (gifts/family support)
- Date extraction restoration
- Compound item name preservation
- Comprehensive test suite (21 test cases)

Release Date: 2025-11-19
Status: Ready for Testing"

echo ""
echo "========================================="
echo "✅ All tags created successfully!"
echo "========================================="
echo ""
echo "📋 Local tags:"
git tag -l
echo ""
echo "📤 To push tags to remote, run:"
echo "   git push origin --tags"
echo ""
echo "Or push individually:"
echo "   git push origin v1.2.0"
echo "   git push origin v1.3.0"
echo "   git push origin v1.5.0"
echo "   git push origin v1.7.0"
