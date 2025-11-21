# Release Notes

This directory contains all release notes for the linebot-gpt-bookkeeper project.

## 📁 Directory Structure

```
docs/releases/
├── README.md                         # This file
├── RELEASE_TAGGING_GUIDE.md         # Git tagging and release guide
├── RELEASE_NOTES_v1.2.0.md          # v1.2.0 release notes
├── RELEASE_NOTES_v1.3.0.md          # v1.3.0 release notes
├── RELEASE_NOTES_v1.5.0.md          # v1.5.0 release notes
├── RELEASE_NOTES_v1.7.0.md          # v1.7.0 release notes
├── RELEASE_NOTES_v1.8.0.md          # v1.8.0 release notes (detailed)
└── RELEASE_NOTES_v1.8.0_GITHUB.md   # v1.8.0 GitHub release (summary)
```

## 📝 Release Notes Content

Each release note includes:
- Detailed feature descriptions
- Technical implementation details
- Complete commit history
- Development statistics
- Comprehensive testing guide
- Usage examples
- Installation instructions
- Known limitations

## 📋 Release History

| Version | Release Date | Status | Key Features |
|---------|-------------|--------|--------------|
| [v1.2.0](./RELEASE_NOTES_v1.2.0.md) | 2025-11-15 | Stable | Vision API Foundation |
| [v1.3.0](./RELEASE_NOTES_v1.3.0.md) | 2025-11-15 | Stable | Enhanced Classification |
| [v1.5.0](./RELEASE_NOTES_v1.5.0.md) | 2025-11-15 | Stable | Multi-Item Expense |
| [v1.7.0](./RELEASE_NOTES_v1.7.0.md) | 2025-11-19 | Stable | Advance Payment Tracking |
| [v1.8.0](./RELEASE_NOTES_v1.8.0.md) | 2025-11-21 | Testing | Multi-Currency Bookkeeping |

## 🚀 Creating a Release

See [RELEASE_TAGGING_GUIDE.md](./RELEASE_TAGGING_GUIDE.md) for complete instructions on:
- Creating git tags
- Pushing tags to GitHub
- Creating GitHub releases

## 🔖 Quick Commands

```bash
# Create all tags (from project root)
./create_tags.sh

# Push all tags
git push origin --tags

# Push specific tag
git push origin v1.7.0
```

---

**Last Updated**: 2025-11-21
