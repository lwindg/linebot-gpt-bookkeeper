# Release Notes

This directory contains all release notes for the linebot-gpt-bookkeeper project.

## 📁 Directory Structure

```
docs/releases/
├── README.md                           # This file
├── RELEASE_TAGGING_GUIDE.md           # Git tagging and release guide
│
├── RELEASE_NOTES_v1.2.0.md            # Full release notes
├── RELEASE_NOTES_v1.2.0_GitHub.md     # GitHub-optimized version
│
├── RELEASE_NOTES_v1.3.0.md            # Full release notes
├── RELEASE_NOTES_v1.3.0_GitHub.md     # GitHub-optimized version
│
├── RELEASE_NOTES_v1.5.0.md            # Full release notes
├── RELEASE_NOTES_v1.5.0_GitHub.md     # GitHub-optimized version
│
├── RELEASE_NOTES_v1.7.0.md            # Full release notes
└── RELEASE_NOTES_v1.7.0_GitHub.md     # GitHub-optimized version
```

## 📝 File Types

### Full Release Notes (`RELEASE_NOTES_vX.X.X.md`)
Complete documentation including:
- Detailed feature descriptions
- Technical implementation details
- Complete commit history
- Development statistics
- Comprehensive testing guide

**Use for**: Internal reference, detailed technical review

### GitHub-Optimized (`RELEASE_NOTES_vX.X.X_GitHub.md`)
Concise versions suitable for GitHub releases:
- Key features and highlights
- Quick usage examples
- Installation instructions
- Known limitations
- What's coming next

**Use for**: Publishing GitHub releases, public-facing documentation

## 📋 Release History

| Version | Release Date | Status | Key Features |
|---------|-------------|--------|--------------|
| [v1.2.0](./RELEASE_NOTES_v1.2.0.md) | 2025-11-15 | Stable | Vision API Foundation |
| [v1.3.0](./RELEASE_NOTES_v1.3.0.md) | 2025-11-15 | Stable | Enhanced Classification |
| [v1.5.0](./RELEASE_NOTES_v1.5.0.md) | 2025-11-15 | Stable | Multi-Item Expense |
| [v1.7.0](./RELEASE_NOTES_v1.7.0.md) | 2025-11-19 | Pre-release | Advance Payment Tracking |

## 🚀 Creating a Release

See [RELEASE_TAGGING_GUIDE.md](./RELEASE_TAGGING_GUIDE.md) for complete instructions on:
- Creating git tags
- Pushing tags to GitHub
- Creating GitHub releases
- Using GitHub-optimized release notes

## 🔖 Quick Commands

```bash
# Create all tags (from project root)
../create_tags.sh

# Push all tags
git push origin --tags

# Push specific tag
git push origin v1.7.0
```

---

**Last Updated**: 2025-11-19
